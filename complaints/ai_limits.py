import hashlib
import json
import os
from decimal import Decimal, ROUND_UP
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    AIMonthlyBudget,
    AIUsageLog,
    UserProfile,
    UserPremiumMembership,
    WorkerProfile,
    WorkerSubscription,
)


# =========================================================
# CONFIG
# =========================================================

DEFAULT_MONTHLY_BUDGET_INR = Decimal(
    os.environ.get(
        "AI_MONTHLY_BUDGET_INR",
        "100.00",
    )
)

FREE_BUDGET_PERCENT = Decimal(
    os.environ.get(
        "AI_FREE_BUDGET_PERCENT",
        "30",
    )
)

USD_TO_INR = Decimal(
    os.environ.get(
        "AI_USD_TO_INR",
        "90.00",
    )
)

GEMINI_INPUT_USD_PER_MILLION = Decimal(
    os.environ.get(
        "GEMINI_INPUT_USD_PER_MILLION",
        "0.30",
    )
)

GEMINI_OUTPUT_USD_PER_MILLION = Decimal(
    os.environ.get(
        "GEMINI_OUTPUT_USD_PER_MILLION",
        "2.50",
    )
)

COST_SAFETY_MULTIPLIER = Decimal(
    os.environ.get(
        "AI_COST_SAFETY_MULTIPLIER",
        "2.00",
    )
)

CACHE_MINUTES = int(
    os.environ.get(
        "AI_DUPLICATE_CACHE_MINUTES",
        "10",
    )
)


CITIZEN_EXACT_CACHE_MINUTES = int(
    os.environ.get(
        "AI_CITIZEN_EXACT_CACHE_MINUTES",
        "1440",
    )
)

AI_CACHE_VERSION = (
    os.environ.get(
        "AI_CACHE_VERSION",
        "",
    )
    .strip()
)


# =========================================================
# FEATURE CREDIT / RESERVATION RULES
# =========================================================

AI_FEATURES = {
    "complaint_analysis": {
        "credits": 1,
        "reserve_inr": Decimal(
            os.environ.get(
                "AI_RESERVE_COMPLAINT_ANALYSIS_INR",
                "0.25",
            )
        ),
    },
    "translation": {
        "credits": 1,
        "reserve_inr": Decimal("0.25"),
    },
    "category_suggestion": {
        "credits": 1,
        "reserve_inr": Decimal("0.20"),
    },
    "detailed_analysis": {
        "credits": 2,
        "reserve_inr": Decimal("0.50"),
    },
    "worker_summary": {
        "credits": 2,
        "reserve_inr": Decimal("0.50"),
    },
    "worker_checklist": {
        "credits": 2,
        "reserve_inr": Decimal("0.50"),
    },
    "worker_reply": {
        "credits": 1,
        "reserve_inr": Decimal("0.25"),
    },
    "photo_analysis": {
        "credits": 5,
        "reserve_inr": Decimal("1.50"),
    },
    "help_chat": {
        "credits": 1,
        "reserve_inr": Decimal("0.30"),
    },
}


PLAN_RULES = {
    "free": {
        "label": "Free Citizen",
        "credit_limit": 3,
        "period": "lifetime",
        "daily_limit": 3,
        "premium": False,
    },
    "citizen_premium": {
        "label": "Citizen Premium",
        "credit_limit": 60,
        "period": "monthly",
        "daily_limit": 20,
        "premium": True,
    },
    "worker_free": {
        "label": "Free Worker",
        "credit_limit": 3,
        "period": "lifetime",
        "daily_limit": 3,
        "premium": False,
    },
    "worker_pro": {
        "label": "Worker Pro",
        "credit_limit": 150,
        "period": "monthly",
        "daily_limit": 40,
        "premium": True,
    },
}


# =========================================================
# EXCEPTIONS
# =========================================================

class AIRequestBlocked(Exception):
    def __init__(
        self,
        code,
        message,
        http_status=429,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# =========================================================
# DATE HELPERS
# =========================================================

def _local_now():
    return timezone.localtime(
        timezone.now()
    )


def _day_start():
    now = _local_now()
    return now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _month_start():
    now = _local_now()
    return now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _worker_ai_cycle_start(subscription):
    """Return the start of the worker's current rolling 30-day AI cycle."""
    now = timezone.now()

    anchor = (
        subscription.started_at
        or subscription.current_period_start
        or subscription.created_at
        or now
    )

    # Razorpay can report a future current_start while a mandate is only
    # authenticated. Never allow a future anchor to reset usage incorrectly.
    if anchor > now:
        anchor = subscription.started_at or subscription.created_at or now

    elapsed = max((now - anchor).total_seconds(), 0)
    cycle_seconds = 30 * 24 * 60 * 60
    completed_cycles = int(elapsed // cycle_seconds)

    return anchor + timedelta(days=30 * completed_cycles)


# =========================================================
# PLAN
# =========================================================

def get_ai_plan(user):
    """
    Return the user's current AI plan.

    Citizen Premium is valid only while the paid 30-day membership
    is active. UserProfile.is_premium is kept in sync for the
    existing theme entitlement UI.
    """

    worker = (
        WorkerProfile.objects
        .filter(user=user)
        .first()
    )

    if worker:

        subscription = (
            WorkerSubscription.objects
            .filter(worker=worker)
            .first()
        )

        if (
            subscription
            and subscription.is_premium_active
        ):
            key = "worker_pro"
            period_start = _worker_ai_cycle_start(
                subscription
            )
            premium_until = (
                subscription.current_period_end
            )

            plan = {
                **PLAN_RULES[key],
                "credit_limit": subscription.ai_credits_per_cycle,
                "label": subscription.plan_label,
                "period": "monthly",
            }
        else:
            key = "worker_free"
            period_start = None
            premium_until = None
            plan = PLAN_RULES[key]

        return {
            "key": key,
            **plan,
            "period_start": period_start,
            "premium_until": premium_until,
        }

    profile, created = (
        UserProfile.objects
        .get_or_create(user=user)
    )

    membership, created = (
        UserPremiumMembership.objects
        .get_or_create(user=user)
    )

    if (
        membership.status == "active"
        and not membership.is_active
    ):
        membership.status = "expired"
        membership.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    membership_active = (
        membership.is_active
    )

    if (
        profile.is_premium
        != membership_active
    ):
        profile.is_premium = (
            membership_active
        )
        profile.save(
            update_fields=[
                "is_premium",
                "updated_at",
            ]
        )

    if membership_active:
        key = "citizen_premium"
        period_start = (
            membership.current_period_start
            or _month_start()
        )
        premium_until = (
            membership.current_period_end
        )
    else:
        key = "free"
        period_start = None
        premium_until = None

    return {
        "key": key,
        **PLAN_RULES[key],
        "period_start": period_start,
        "premium_until": premium_until,
    }


def _credit_query(user, plan):
    qs = AIUsageLog.objects.filter(
        user=user,
        plan=plan["key"],
        status__in=[
            "reserved",
            "success",
        ],
    )

    if plan["period"] == "monthly":
        period_start = (
            plan.get("period_start")
            or _month_start()
        )

        qs = qs.filter(
            created_at__gte=period_start
        )

    return qs

def get_ai_credit_status(user):
    plan = get_ai_plan(user)

    used = (
        _credit_query(
            user,
            plan,
        )
        .aggregate(
            total=Sum("credit_cost")
        )
        .get("total")
        or 0
    )

    remaining = max(
        plan["credit_limit"] - used,
        0,
    )

    return {
        "plan": plan["key"],
        "plan_label": plan["label"],
        "is_premium": plan["premium"],
        "period": plan["period"],
        "credit_limit": plan["credit_limit"],
        "credits_used": used,
        "credits_remaining": remaining,
        "daily_limit": plan["daily_limit"],
        "premium_until": plan.get("premium_until"),
    }


# =========================================================
# REQUEST HASH / DUPLICATE PROTECTION
# =========================================================

def build_request_hash(
    user_id,
    feature,
    payload,
):
    hash_payload = {
        "user_id": user_id,
        "feature": feature,
        "payload": payload,
    }

    # Keep current hashes backward-compatible unless a cache
    # version is explicitly configured. Set AI_CACHE_VERSION
    # later when a prompt/schema change should invalidate old
    # saved AI results.
    if AI_CACHE_VERSION:
        hash_payload[
            "cache_version"
        ] = AI_CACHE_VERSION

    canonical = json.dumps(
        hash_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def get_cached_success(
    user,
    feature,
    request_hash,
    max_age_minutes=CACHE_MINUTES,
):
    """
    Return a successful saved AI result for an exact request hash.

    max_age_minutes:
    - integer: cache expires after that many minutes
    - None: keep using the result until the request hash changes

    Worker hashes include complaint.updated_at and complaint state,
    so a persistent Worker result automatically becomes invalid when
    the complaint changes.
    """

    if not request_hash:
        return None

    filters = {
        "user": user,
        "feature": feature,
        "request_hash": request_hash,
        "status": "success",
        "response_json__isnull": False,
    }

    if max_age_minutes is not None:
        filters[
            "created_at__gte"
        ] = (
            timezone.now()
            - timedelta(
                minutes=max(
                    int(
                        max_age_minutes
                    ),
                    1,
                )
            )
        )

    return (
        AIUsageLog.objects
        .filter(
            **filters
        )
        .order_by(
            "-created_at"
        )
        .first()
    )


# =========================================================
# MONTHLY BUDGET
# =========================================================

def _current_budget_row_locked():
    now = _local_now()

    budget, created = (
        AIMonthlyBudget.objects
        .get_or_create(
            year=now.year,
            month=now.month,
            defaults={
                "budget_inr":
                    DEFAULT_MONTHLY_BUDGET_INR,
            },
        )
    )

    budget = (
        AIMonthlyBudget.objects
        .select_for_update()
        .get(pk=budget.pk)
    )

    # Environment value can be changed without a migration.
    if (
        budget.budget_inr
        != DEFAULT_MONTHLY_BUDGET_INR
    ):
        budget.budget_inr = (
            DEFAULT_MONTHLY_BUDGET_INR
        )
        budget.save(
            update_fields=[
                "budget_inr",
                "updated_at",
            ]
        )

    return budget


def _free_budget_limit(budget):
    return (
        budget.budget_inr
        * FREE_BUDGET_PERCENT
        / Decimal("100")
    )


# =========================================================
# RESERVE BEFORE CALLING GEMINI
# =========================================================

@transaction.atomic
def reserve_ai_request(
    user,
    feature,
    request_hash="",
    model_name="",
):
    if feature not in AI_FEATURES:
        raise AIRequestBlocked(
            "unknown_feature",
            "This AI feature is not configured.",
            400,
        )

    if (
        not user.is_authenticated
        or user.is_staff
        or user.is_superuser
    ):
        raise AIRequestBlocked(
            "account_not_allowed",
            "AI is not available for this account.",
            403,
        )

    # Serialise AI requests from the same user so simultaneous
    # taps cannot bypass credit limits.
    User.objects.select_for_update().get(
        pk=user.pk
    )

    plan = get_ai_plan(user)
    feature_rule = AI_FEATURES[feature]

    # -----------------------------------------------------
    # Duplicate in-flight protection
    # -----------------------------------------------------

    if request_hash:

        in_flight_since = (
            timezone.now()
            - timedelta(seconds=45)
        )

        in_flight = (
            AIUsageLog.objects
            .filter(
                user=user,
                feature=feature,
                request_hash=request_hash,
                status="reserved",
                created_at__gte=in_flight_since,
            )
            .exists()
        )

        if in_flight:
            raise AIRequestBlocked(
                "duplicate_in_progress",
                (
                    "This AI request is already being processed. "
                    "Please wait a moment."
                ),
                409,
            )

    # -----------------------------------------------------
    # Credit limit
    # -----------------------------------------------------

    used_credits = (
        _credit_query(
            user,
            plan,
        )
        .aggregate(
            total=Sum("credit_cost")
        )
        .get("total")
        or 0
    )

    credit_cost = feature_rule["credits"]

    if (
        used_credits + credit_cost
        > plan["credit_limit"]
    ):
        raise AIRequestBlocked(
            "credits_exhausted",
            (
                "Your AI credits are finished. "
                "Upgrade or wait for your next premium monthly reset."
                if plan["period"] == "monthly"
                else
                "Your free AI trial credits are finished. "
                "Upgrade to Premium to continue using AI."
            ),
            402,
        )

    # -----------------------------------------------------
    # Daily anti-abuse limit
    # -----------------------------------------------------

    today_calls = (
        AIUsageLog.objects
        .filter(
            user=user,
            status__in=[
                "reserved",
                "success",
            ],
            created_at__gte=_day_start(),
        )
        .count()
    )

    if today_calls >= plan["daily_limit"]:
        raise AIRequestBlocked(
            "daily_limit_reached",
            (
                "Your AI daily safety limit is reached. "
                "Please try again tomorrow."
            ),
            429,
        )

    # -----------------------------------------------------
    # Global monthly spending guard
    # -----------------------------------------------------

    budget = _current_budget_row_locked()

    reserve_inr = feature_rule[
        "reserve_inr"
    ]

    total_committed = (
        budget.total_spent_inr
        + budget.total_reserved_inr
    )

    if (
        total_committed + reserve_inr
        > budget.budget_inr
    ):
        raise AIRequestBlocked(
            "monthly_budget_reached",
            (
                "AI is temporarily paused because the monthly "
                "safety budget has been reached."
            ),
            503,
        )

    # Free users only get a limited slice of the monthly AI
    # budget. Premium capacity stays protected.
    if not plan["premium"]:

        free_limit = _free_budget_limit(
            budget
        )

        free_committed = (
            budget.free_spent_inr
            + budget.free_reserved_inr
        )

        if (
            free_committed + reserve_inr
            > free_limit
        ):
            raise AIRequestBlocked(
                "free_budget_reached",
                (
                    "Free AI capacity for this month has been used. "
                    "Premium AI capacity is reserved for paid members."
                ),
                503,
            )

    # -----------------------------------------------------
    # Reserve budget first, then create request log.
    # -----------------------------------------------------

    budget.total_reserved_inr += (
        reserve_inr
    )

    if not plan["premium"]:
        budget.free_reserved_inr += (
            reserve_inr
        )

    budget.save(
        update_fields=[
            "total_reserved_inr",
            "free_reserved_inr",
            "updated_at",
        ]
    )

    log = AIUsageLog.objects.create(
        user=user,
        feature=feature,
        plan=plan["key"],
        status="reserved",
        credit_cost=credit_cost,
        model_name=model_name,
        request_hash=request_hash,
        reserved_cost_inr=reserve_inr,
    )

    return log


# =========================================================
# COST ESTIMATION
# =========================================================

def estimate_paid_tier_cost_inr(
    input_tokens,
    output_tokens,
):
    input_tokens = Decimal(
        max(
            int(input_tokens or 0),
            0,
        )
    )

    output_tokens = Decimal(
        max(
            int(output_tokens or 0),
            0,
        )
    )

    million = Decimal("1000000")

    usd = (
        (
            input_tokens
            / million
            * GEMINI_INPUT_USD_PER_MILLION
        )
        +
        (
            output_tokens
            / million
            * GEMINI_OUTPUT_USD_PER_MILLION
        )
    )

    inr = (
        usd
        * USD_TO_INR
        * COST_SAFETY_MULTIPLIER
    )

    # Keep a tiny non-zero amount for successful calls so
    # the internal ledger remains conservative.
    if inr <= 0:
        inr = Decimal("0.000001")

    return inr.quantize(
        Decimal("0.000001"),
        rounding=ROUND_UP,
    )


# =========================================================
# SUCCESS / FAILURE FINALISATION
# =========================================================

@transaction.atomic
def complete_ai_request(
    usage_log,
    *,
    input_tokens=0,
    output_tokens=0,
    total_tokens=0,
    response_json=None,
):
    log = (
        AIUsageLog.objects
        .select_for_update()
        .get(pk=usage_log.pk)
    )

    if log.status != "reserved":
        return log

    budget = (
        AIMonthlyBudget.objects
        .select_for_update()
        .get(
            year=timezone.localtime(
                log.created_at
            ).year,
            month=timezone.localtime(
                log.created_at
            ).month,
        )
    )

    estimated_cost = (
        estimate_paid_tier_cost_inr(
            input_tokens,
            output_tokens,
        )
    )

    reserve = log.reserved_cost_inr

    budget.total_reserved_inr = max(
        budget.total_reserved_inr
        - reserve,
        Decimal("0"),
    )

    budget.total_spent_inr += (
        estimated_cost
    )

    if log.plan in {
        "free",
        "worker_free",
    }:
        budget.free_reserved_inr = max(
            budget.free_reserved_inr
            - reserve,
            Decimal("0"),
        )
        budget.free_spent_inr += (
            estimated_cost
        )

    budget.save(
        update_fields=[
            "total_reserved_inr",
            "total_spent_inr",
            "free_reserved_inr",
            "free_spent_inr",
            "updated_at",
        ]
    )

    log.status = "success"
    log.input_tokens = max(
        int(input_tokens or 0),
        0,
    )
    log.output_tokens = max(
        int(output_tokens or 0),
        0,
    )
    log.total_tokens = max(
        int(total_tokens or 0),
        (
            log.input_tokens
            + log.output_tokens
        ),
    )
    log.estimated_cost_inr = (
        estimated_cost
    )
    log.response_json = (
        response_json
        if response_json is not None
        else {}
    )
    log.completed_at = timezone.now()

    log.save(
        update_fields=[
            "status",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost_inr",
            "response_json",
            "completed_at",
        ]
    )

    return log


@transaction.atomic
def fail_ai_request(
    usage_log,
    error_code="ai_error",
):
    log = (
        AIUsageLog.objects
        .select_for_update()
        .get(pk=usage_log.pk)
    )

    if log.status != "reserved":
        return log

    budget = (
        AIMonthlyBudget.objects
        .select_for_update()
        .get(
            year=timezone.localtime(
                log.created_at
            ).year,
            month=timezone.localtime(
                log.created_at
            ).month,
        )
    )

    reserve = log.reserved_cost_inr

    budget.total_reserved_inr = max(
        budget.total_reserved_inr
        - reserve,
        Decimal("0"),
    )

    if log.plan in {
        "free",
        "worker_free",
    }:
        budget.free_reserved_inr = max(
            budget.free_reserved_inr
            - reserve,
            Decimal("0"),
        )

    budget.save(
        update_fields=[
            "total_reserved_inr",
            "free_reserved_inr",
            "updated_at",
        ]
    )

    log.status = "failed"
    log.error_code = (
        str(error_code or "ai_error")[:80]
    )
    log.completed_at = timezone.now()

    log.save(
        update_fields=[
            "status",
            "error_code",
            "completed_at",
        ]
    )

    return log
