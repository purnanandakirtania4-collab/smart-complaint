import json
import os
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .ai_limits import (
    AIRequestBlocked,
    CITIZEN_EXACT_CACHE_MINUTES,
    build_request_hash,
    complete_ai_request,
    fail_ai_request,
    get_ai_credit_status,
    get_cached_success,
    reserve_ai_request,
)
from .ai_service import (
    GeminiServiceError,
    gemini_generate_json,
)
from .models import Complaint, WorkerProfile


def _normalize_for_quality(text):
    return " ".join(
        str(text or "").split()
    ).strip()


def _description_quality_check(text):
    """
    Reject descriptions that are too vague before any Gemini call.

    This protects:
    - user credits,
    - provider cost,
    - output quality.
    """

    normalized = _normalize_for_quality(text)

    words = re.findall(
        r"[A-Za-z0-9\u0900-\u097F]+",
        normalized,
    )

    if len(normalized) < 35:
        return False

    if len(words) < 7:
        return False

    generic_only = {
        "sir",
        "please",
        "solve",
        "this",
        "problem",
        "issue",
        "help",
        "me",
        "urgent",
        "quickly",
        "plz",
    }

    meaningful_words = [
        word.lower()
        for word in words
        if word.lower() not in generic_only
    ]

    if len(meaningful_words) < 3:
        return False

    return True


def _sanitize_ai_text(text):
    """
    Remove common unnecessary private identifiers before sending
    complaint text to the AI provider.

    The original complaint remains untouched in the user's form.
    """

    safe = str(text or "")

    safe = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[email removed]",
        safe,
        flags=re.IGNORECASE,
    )

    # Long phone/account/Aadhaar-like digit sequences.
    safe = re.sub(
        r"(?<!\d)(?:\d[\s-]?){10,16}(?!\d)",
        "[number removed]",
        safe,
    )

    # Explicit OTP / one-time-code patterns.
    safe = re.sub(
        r"\b(?:otp|one[\s-]?time[\s-]?(?:password|code))"
        r"\s*[:=-]?\s*\d{4,8}\b",
        "[OTP removed]",
        safe,
        flags=re.IGNORECASE,
    )

    return safe.strip()


def _credit_payload(user):
    status = get_ai_credit_status(
        user
    )

    return {
        "plan":
            status["plan"],
        "plan_label":
            status["plan_label"],
        "is_premium":
            status["is_premium"],
        "period":
            status["period"],
        "credit_limit":
            status["credit_limit"],
        "credits_used":
            status["credits_used"],
        "credits_remaining":
            status["credits_remaining"],
        "daily_limit":
            status["daily_limit"],
    }


@login_required(login_url="login")
@require_GET
def ai_status(request):
    """
    Lightweight endpoint for future AI-credit UI.
    It intentionally does not expose the global rupee budget.
    """

    if (
        request.user.is_staff
        or request.user.is_superuser
    ):
        return JsonResponse(
            {
                "success": False,
                "error":
                    "AI is not available for admin accounts.",
            },
            status=403,
        )

    return JsonResponse(
        {
            "success": True,
            "ai": _credit_payload(
                request.user
            ),
        }
    )


@login_required(login_url="login")
@require_POST
def analyze_complaint_ai(request):
    """
    Protected Gemini complaint analyzer.

    Credit cost:
        1 AI credit

    Cost protection:
        - credit check before API call
        - daily anti-abuse limit
        - duplicate request cache
        - free monthly budget slice
        - global monthly safety budget
        - failed Gemini calls consume 0 credits
    """

    if (
        request.user.is_staff
        or request.user.is_superuser
    ):
        return JsonResponse(
            {
                "success": False,
                "error":
                    "AI is not available for admin accounts.",
            },
            status=403,
        )

    # =====================================================
    # REQUEST JSON
    # =====================================================

    try:
        body = json.loads(
            request.body.decode(
                "utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "success": False,
                "error":
                    "Invalid request data.",
            },
            status=400,
        )

    description = str(
        body.get(
            "description",
            "",
        )
    ).strip()

    if len(description) < 10:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Please write at least 10 characters "
                    "in Complaint Description."
                ),
            },
            status=400,
        )

    # Limit input length to protect token cost.
    if len(description) > 3000:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Complaint Description is too long for AI. "
                    "Please keep it under 3000 characters."
                ),
            },
            status=400,
        )

    # =====================================================
    # QUALITY GATE - NO CREDIT / NO GEMINI CALL
    # =====================================================

    if not _description_quality_check(
        description
    ):
        return JsonResponse(
            {
                "success": False,
                "code":
                    "description_too_vague",
                "error": (
                    "Please add a little more detail before using AI: "
                    "what exactly is wrong, which place/item is affected, "
                    "and how long or when the issue happens."
                ),
                "ai":
                    _credit_payload(
                        request.user
                    ),
            },
            status=400,
        )

    safe_description = (
        _sanitize_ai_text(
            description
        )
    )

    # =====================================================
    # CATEGORY LIST
    # =====================================================

    categories = [
        value
        for value, label
        in WorkerProfile.SKILL_CHOICES
    ]

    # =====================================================
    # DUPLICATE HASH / CACHE
    # =====================================================

    normalized_description = (
        " ".join(
            description.split()
        )
        .strip()
        .lower()
    )

    request_hash = build_request_hash(
        request.user.id,
        "complaint_analysis",
        {
            "description":
                normalized_description,
        },
    )

    cached = get_cached_success(
        request.user,
        "complaint_analysis",
        request_hash,
        max_age_minutes=
            CITIZEN_EXACT_CACHE_MINUTES,
    )

    if cached:

        payload = dict(
            cached.response_json
            or {}
        )

        payload.update(
            {
                "success": True,
                "cached": True,
                "saved_result": True,
                "ai": _credit_payload(
                    request.user
                ),
            }
        )

        return JsonResponse(
            payload
        )

    # =====================================================
    # RESERVE CREDIT + MONTHLY BUDGET
    # =====================================================

    model_name = os.environ.get(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    ).strip() or "gemini-3.5-flash-lite"

    try:
        usage_log = reserve_ai_request(
            request.user,
            "complaint_analysis",
            request_hash=request_hash,
            model_name=model_name,
        )

    except AIRequestBlocked as blocked:
        return JsonResponse(
            {
                "success": False,
                "error":
                    blocked.message,
                "code":
                    blocked.code,
                "ai":
                    _credit_payload(
                        request.user
                    ),
            },
            status=blocked.http_status,
        )

    # =====================================================
    # AI INSTRUCTION
    # =====================================================

    system_instruction = (
        "You are Smart Complaint's complaint assistant. "
        "Use only the sanitized description. "
        "Never request, infer or repeat Aadhaar, OTP, payment, phone, email, "
        "account or other unnecessary private data. "
        f"Category must be exactly one of: {', '.join(categories)}. "
        "Use Other when no category clearly matches. "
        "Priority must be Normal, High or Emergency. "
        "Emergency only means an immediate serious safety danger such as live "
        "electrical exposure, active fire, major flooding, dangerous gas leakage "
        "or structural collapse risk. High is clearly time-sensitive or strongly "
        "disruptive without immediate life danger; otherwise use Normal. "
        "Summary must be one factual sentence under 22 words. "
        "Do not invent location, duration, cause, damage or severity. "
        "Return only the requested JSON."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "category": {
                "type": "STRING",
                "enum": categories,
            },
            "priority": {
                "type": "STRING",
                "enum": [
                    "Normal",
                    "High",
                    "Emergency",
                ],
            },
            "summary": {
                "type": "STRING",
            },
        },
        "required": [
            "category",
            "priority",
            "summary",
        ],
    }

    # =====================================================
    # GEMINI CALL
    # =====================================================

    try:
        result = gemini_generate_json(
            system_instruction=
                system_instruction,
            user_text=safe_description,
            response_schema=schema,
            max_output_tokens=128,
            temperature=0.0,
        )

    except GeminiServiceError as error:

        fail_ai_request(
            usage_log,
            error.code,
        )

        return JsonResponse(
            {
                "success": False,
                "error":
                    error.message,
                "code":
                    error.code,
                "ai":
                    _credit_payload(
                        request.user
                    ),
            },
            status=error.http_status,
        )

    # =====================================================
    # SERVER-SIDE RESULT VALIDATION
    # =====================================================

    analysis = (
        result.get(
            "data",
            {}
        )
        or {}
    )

    category = str(
        analysis.get(
            "category",
            "",
        )
    ).strip()

    priority = str(
        analysis.get(
            "priority",
            "",
        )
    ).strip()

    summary = str(
        analysis.get(
            "summary",
            "",
        )
    ).strip()

    if category not in categories:
        category = (
            "Other"
            if "Other" in categories
            else categories[-1]
        )

    if priority not in {
        "Normal",
        "High",
        "Emergency",
    }:
        priority = "Normal"

    if not summary:
        summary = description[:240]

    response_json = {
        "category":
            category,
        "priority":
            priority,
        "summary":
            summary[:500],
    }

    usage = result.get(
        "usage",
        {},
    )

    complete_ai_request(
        usage_log,
        input_tokens=usage.get(
            "input_tokens",
            0,
        ),
        output_tokens=usage.get(
            "output_tokens",
            0,
        ),
        total_tokens=usage.get(
            "total_tokens",
            0,
        ),
        response_json=response_json,
    )

    response_json.update(
        {
            "success": True,
            "cached": False,
            "ai": _credit_payload(
                request.user
            ),
        }
    )

    return JsonResponse(
        response_json
    )

# ============================================================
# WORKER AI HELPERS
# ============================================================

def _worker_ai_access(request, complaint_id):
    """
    Authorize a worker AI request.

    The worker may use AI only for a complaint actually assigned
    to their own approved WorkerProfile.
    """

    if (
        request.user.is_staff
        or request.user.is_superuser
    ):
        return None, None, JsonResponse(
            {
                "success": False,
                "error":
                    "Worker AI is not available for admin accounts.",
            },
            status=403,
        )

    worker = (
        WorkerProfile.objects
        .filter(
            user=request.user,
            is_approved=True,
        )
        .first()
    )

    if not worker:
        return None, None, JsonResponse(
            {
                "success": False,
                "error":
                    "Approved worker access is required.",
            },
            status=403,
        )

    complaint = (
        Complaint.objects
        .filter(
            id=complaint_id,
            assigned_worker=worker,
        )
        .first()
    )

    if not complaint:
        return worker, None, JsonResponse(
            {
                "success": False,
                "error":
                    "This complaint is not assigned to your worker account.",
            },
            status=404,
        )

    return worker, complaint, None


def _worker_ai_source(complaint):
    """
    Build a privacy-minimised complaint context.

    Deliberately excluded:
    - complainant name
    - email
    - phone
    - exact coordinates
    - OTP
    - payment information
    """

    subject = _sanitize_ai_text(
        complaint.subject
    )

    description = _sanitize_ai_text(
        complaint.description
    )

    return (
        f"Subject: {subject}\n"
        f"Description: {description}\n"
        f"Priority: {complaint.priority}\n"
        f"Status: {complaint.status}\n"
        f"Before photo available: {'Yes' if complaint.photo else 'No'}\n"
        f"After photo available: {'Yes' if complaint.after_photo else 'No'}"
    )


def _worker_request_hash(
    user_id,
    complaint,
    feature,
):
    return build_request_hash(
        user_id,
        feature,
        {
            "complaint_id":
                complaint.id,
            "updated_at":
                complaint.updated_at.isoformat(),
            "subject":
                _normalize_for_quality(
                    complaint.subject
                ).lower(),
            "description":
                _normalize_for_quality(
                    complaint.description
                ).lower(),
            "priority":
                complaint.priority,
            "status":
                complaint.status,
            "has_before_photo":
                bool(complaint.photo),
            "has_after_photo":
                bool(complaint.after_photo),
        },
    )


def _worker_cached_response(
    request,
    complaint,
    feature,
):
    request_hash = _worker_request_hash(
        request.user.id,
        complaint,
        feature,
    )

    cached = get_cached_success(
        request.user,
        feature,
        request_hash,
        max_age_minutes=None,
    )

    if not cached:
        return request_hash, None

    payload = dict(
        cached.response_json
        or {}
    )

    payload.update(
        {
            "success": True,
            "cached": True,
            "saved_result": True,
            "feature": feature,
            "ai": _credit_payload(
                request.user
            ),
        }
    )

    return request_hash, JsonResponse(
        payload
    )


def _worker_reserve(
    request,
    feature,
    request_hash,
):
    model_name = os.environ.get(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    ).strip() or "gemini-3.5-flash-lite"

    try:
        usage_log = reserve_ai_request(
            request.user,
            feature,
            request_hash=request_hash,
            model_name=model_name,
        )

    except AIRequestBlocked as blocked:
        return None, JsonResponse(
            {
                "success": False,
                "error":
                    blocked.message,
                "code":
                    blocked.code,
                "ai":
                    _credit_payload(
                        request.user
                    ),
            },
            status=blocked.http_status,
        )

    return usage_log, None


def _worker_gemini_error(
    request,
    usage_log,
    error,
):
    fail_ai_request(
        usage_log,
        error.code,
    )

    return JsonResponse(
        {
            "success": False,
            "error":
                error.message,
            "code":
                error.code,
            "ai":
                _credit_payload(
                    request.user
                ),
        },
        status=error.http_status,
    )


# ============================================================
# WORKER AI - COMPLAINT SUMMARY
# 2 credits
# ============================================================

@login_required(login_url="worker_login")
@require_POST
def worker_ai_summary(
    request,
    complaint_id,
):
    worker, complaint, error_response = (
        _worker_ai_access(
            request,
            complaint_id,
        )
    )

    if error_response:
        return error_response

    request_hash, cached_response = (
        _worker_cached_response(
            request,
            complaint,
            "worker_summary",
        )
    )

    if cached_response:
        return cached_response

    usage_log, blocked_response = (
        _worker_reserve(
            request,
            "worker_summary",
            request_hash,
        )
    )

    if blocked_response:
        return blocked_response

    schema = {
        "type": "OBJECT",
        "properties": {
            "summary": {
                "type": "STRING",
            },
            "key_issue": {
                "type": "STRING",
            },
            "recommended_focus": {
                "type": "STRING",
            },
        },
        "required": [
            "summary",
            "key_issue",
            "recommended_focus",
        ],
    }

    system_instruction = (
        "You are Smart Complaint's worker assistant. "
        "Use only the complaint context provided. "
        "Do not infer private identity, exact location, cause, technical diagnosis "
        "or facts not present in the complaint. "
        "Write a concise worker-oriented summary. "
        "key_issue must identify the main reported problem in one short sentence. "
        "recommended_focus must state what the worker should inspect or confirm first, "
        "without pretending a diagnosis is known. "
        "Do not change complaint status, promise completion time or mention AI. "
        "Return only the requested JSON."
    )

    try:
        result = gemini_generate_json(
            system_instruction=
                system_instruction,
            user_text=
                _worker_ai_source(
                    complaint
                ),
            response_schema=schema,
            max_output_tokens=160,
            temperature=0.0,
        )

    except GeminiServiceError as error:
        return _worker_gemini_error(
            request,
            usage_log,
            error,
        )

    data = result.get(
        "data",
        {},
    ) or {}

    response_json = {
        "summary":
            str(
                data.get(
                    "summary",
                    "",
                )
            ).strip()[:500],
        "key_issue":
            str(
                data.get(
                    "key_issue",
                    "",
                )
            ).strip()[:300],
        "recommended_focus":
            str(
                data.get(
                    "recommended_focus",
                    "",
                )
            ).strip()[:350],
    }

    if not response_json["summary"]:
        response_json["summary"] = (
            complaint.description[:300]
        )

    usage = result.get(
        "usage",
        {},
    )

    complete_ai_request(
        usage_log,
        input_tokens=usage.get(
            "input_tokens",
            0,
        ),
        output_tokens=usage.get(
            "output_tokens",
            0,
        ),
        total_tokens=usage.get(
            "total_tokens",
            0,
        ),
        response_json=response_json,
    )

    response_json.update(
        {
            "success": True,
            "cached": False,
            "feature":
                "worker_summary",
            "ai":
                _credit_payload(
                    request.user
                ),
        }
    )

    return JsonResponse(
        response_json
    )


# ============================================================
# WORKER AI - WORK CHECKLIST
# 2 credits
# ============================================================

@login_required(login_url="worker_login")
@require_POST
def worker_ai_checklist(
    request,
    complaint_id,
):
    worker, complaint, error_response = (
        _worker_ai_access(
            request,
            complaint_id,
        )
    )

    if error_response:
        return error_response

    request_hash, cached_response = (
        _worker_cached_response(
            request,
            complaint,
            "worker_checklist",
        )
    )

    if cached_response:
        return cached_response

    usage_log, blocked_response = (
        _worker_reserve(
            request,
            "worker_checklist",
            request_hash,
        )
    )

    if blocked_response:
        return blocked_response

    schema = {
        "type": "OBJECT",
        "properties": {
            "steps": {
                "type": "ARRAY",
                "items": {
                    "type": "STRING",
                },
            },
            "safety_note": {
                "type": "STRING",
            },
        },
        "required": [
            "steps",
            "safety_note",
        ],
    }

    system_instruction = (
        "You are Smart Complaint's worker checklist assistant. "
        "Use only the supplied complaint context. "
        "Create 3 to 6 short practical inspection/work-preparation steps. "
        "Do not claim a technical diagnosis. "
        "Do not instruct the worker to bypass safety rules, electrical isolation, "
        "traffic controls, permits or other required precautions. "
        "If specialist or hazardous work may be involved, the safety_note should "
        "tell the worker to follow applicable safety procedures and stop/escalate "
        "when conditions are unsafe. "
        "Do not change complaint status, request OTP, expose private data or mention AI. "
        "Return only the requested JSON."
    )

    try:
        result = gemini_generate_json(
            system_instruction=
                system_instruction,
            user_text=
                _worker_ai_source(
                    complaint
                ),
            response_schema=schema,
            max_output_tokens=220,
            temperature=0.0,
        )

    except GeminiServiceError as error:
        return _worker_gemini_error(
            request,
            usage_log,
            error,
        )

    data = result.get(
        "data",
        {},
    ) or {}

    raw_steps = data.get(
        "steps",
        [],
    )

    if not isinstance(
        raw_steps,
        list,
    ):
        raw_steps = []

    steps = []

    for item in raw_steps[:6]:
        text = str(
            item
        ).strip()

        if text:
            steps.append(
                text[:220]
            )

    if len(steps) < 2:
        steps = [
            "Review the complaint details and confirm the reported issue on site.",
            "Inspect the affected item or area using the appropriate safety procedure.",
            "Document the work completed and update the complaint only after verification.",
        ]

    response_json = {
        "steps": steps,
        "safety_note":
            str(
                data.get(
                    "safety_note",
                    "",
                )
            ).strip()[:400],
    }

    if not response_json[
        "safety_note"
    ]:
        response_json[
            "safety_note"
        ] = (
            "Follow the applicable safety procedure and stop or escalate "
            "the work if the site is unsafe or outside your authorised scope."
        )

    usage = result.get(
        "usage",
        {},
    )

    complete_ai_request(
        usage_log,
        input_tokens=usage.get(
            "input_tokens",
            0,
        ),
        output_tokens=usage.get(
            "output_tokens",
            0,
        ),
        total_tokens=usage.get(
            "total_tokens",
            0,
        ),
        response_json=response_json,
    )

    response_json.update(
        {
            "success": True,
            "cached": False,
            "feature":
                "worker_checklist",
            "ai":
                _credit_payload(
                    request.user
                ),
        }
    )

    return JsonResponse(
        response_json
    )


# ============================================================
# WORKER AI - USER REPLY DRAFT
# 1 credit
# ============================================================

@login_required(login_url="worker_login")
@require_POST
def worker_ai_reply(
    request,
    complaint_id,
):
    worker, complaint, error_response = (
        _worker_ai_access(
            request,
            complaint_id,
        )
    )

    if error_response:
        return error_response

    request_hash, cached_response = (
        _worker_cached_response(
            request,
            complaint,
            "worker_reply",
        )
    )

    if cached_response:
        return cached_response

    usage_log, blocked_response = (
        _worker_reserve(
            request,
            "worker_reply",
            request_hash,
        )
    )

    if blocked_response:
        return blocked_response

    schema = {
        "type": "OBJECT",
        "properties": {
            "reply": {
                "type": "STRING",
            },
        },
        "required": [
            "reply",
        ],
    }

    system_instruction = (
        "You are Smart Complaint's worker reply drafting assistant. "
        "Draft one respectful message the assigned worker could send to the complainant. "
        "Keep it under 55 words. "
        "Use only the complaint context. "
        "Do not include or request OTP, phone, email, payment, Aadhaar or other private data. "
        "Do not promise a completion date/time, compensation, outcome or diagnosis. "
        "Do not claim work is completed unless the status says Resolved. "
        "Do not mention AI. "
        "Return only the requested JSON."
    )

    try:
        result = gemini_generate_json(
            system_instruction=
                system_instruction,
            user_text=
                _worker_ai_source(
                    complaint
                ),
            response_schema=schema,
            max_output_tokens=96,
            temperature=0.0,
        )

    except GeminiServiceError as error:
        return _worker_gemini_error(
            request,
            usage_log,
            error,
        )

    data = result.get(
        "data",
        {},
    ) or {}

    reply = str(
        data.get(
            "reply",
            "",
        )
    ).strip()

    if not reply:
        reply = (
            "I have reviewed your complaint and will inspect the reported issue. "
            "I will update the complaint status after the relevant checks are completed."
        )

    response_json = {
        "reply":
            reply[:700],
    }

    usage = result.get(
        "usage",
        {},
    )

    complete_ai_request(
        usage_log,
        input_tokens=usage.get(
            "input_tokens",
            0,
        ),
        output_tokens=usage.get(
            "output_tokens",
            0,
        ),
        total_tokens=usage.get(
            "total_tokens",
            0,
        ),
        response_json=response_json,
    )

    response_json.update(
        {
            "success": True,
            "cached": False,
            "feature":
                "worker_reply",
            "ai":
                _credit_payload(
                    request.user
                ),
        }
    )

    return JsonResponse(
        response_json
    )

