import calendar
import secrets
import re
import json
import os
from datetime import timedelta
from decimal import Decimal

import razorpay

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files import File
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Avg, Count, Case, When, Value, IntegerField, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.cache import never_cache

from .models import (
    Complaint,
    ComplaintStatusHistory,
    WorkerProfile,
    WorkerFollow,
    WorkerProfileLike,
    UserProfile,
    UserPremiumMembership,
    UserFollow,
    Rating,
    WorkerSubscription,
    WorkerPayoutDetails,
    Notification,
    DeviceToken,
    ChatMessage,
    SupportRequest,
    PaymentTransaction,
)

from .firebase_push import send_push_to_user
from .ai_limits import get_ai_credit_status


# =========================================================
# HELPER - ADD ONE CALENDAR MONTH
# =========================================================

def add_one_month(dt):

    local_dt = timezone.localtime(dt)

    year = local_dt.year
    month = local_dt.month + 1

    if month == 13:
        month = 1
        year += 1

    last_day = calendar.monthrange(
        year,
        month
    )[1]

    day = min(
        local_dt.day,
        last_day
    )

    return local_dt.replace(
        year=year,
        month=month,
        day=day
    )


# =========================================================
# ADMIN ACCOUNT PROTECTION
# =========================================================

def _admin_account_redirect(request):
    """Keep Django staff/superuser accounts out of the normal app UI."""
    if (
        request.user.is_authenticated
        and (request.user.is_staff or request.user.is_superuser)
    ):
        return redirect('/admin/')

    return None


def _worker_account_redirect_from_user_ui(request):
    """
    Keep an authenticated worker out of citizen-only pages.

    A Django/WebView cookie jar can hold only one authenticated account at a
    time. If a worker was the last account used on the phone, opening the app
    again must land on the Worker Dashboard instead of rendering citizen UI
    with the worker's name.
    """
    if not request.user.is_authenticated:
        return None

    if WorkerProfile.objects.filter(user_id=request.user.id).exists():
        return redirect('worker_dashboard')

    return None


def _citizen_area_guard(request):
    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    return _worker_account_redirect_from_user_ui(request)




# =========================================================
# FREE PROFILE AVATAR HELPERS
# =========================================================

FREE_PROFILE_AVATARS = {
    'avatar_01',
    'avatar_02',
    'avatar_03',
    'avatar_04',
    'avatar_05',
    'avatar_06',
    'avatar_07',
    'avatar_08',
    'avatar_09',
    'avatar_10',
    'avatar_11',
    'avatar_12',
    'avatar_13',
    'avatar_14',
    'avatar_15',
    'avatar_16',
    'avatar_17',
    'avatar_18',
    'avatar_19',
    'avatar_20',
    'avatar_21',
    'avatar_22',
    'avatar_23',
    'avatar_24',
    'avatar_25',
    'avatar_26',
    'avatar_27',
    'avatar_28',
    'avatar_29',
    'avatar_30',
    'avatar_31',
    'avatar_32',
    'avatar_33',
    'avatar_34',
    'avatar_35',
    'avatar_36',
    'avatar_37',
    'avatar_38',
    'avatar_39',
    'avatar_40',
}


def _apply_free_profile_avatar(instance, field_name, avatar_id, filename_prefix):
    """
    Save one of Smart Complaint's bundled free avatars into the existing
    ImageField. No model/database schema change is required.
    """
    if avatar_id not in FREE_PROFILE_AVATARS:
        return False

    relative_path = (
        f'complaints/avatars/free/{avatar_id}.png'
    )

    source_path = finders.find(relative_path)

    if not source_path:
        return False

    image_field = getattr(instance, field_name)

    if image_field:
        old_name = image_field.name

        if old_name and default_storage.exists(old_name):
            default_storage.delete(old_name)

    with open(source_path, 'rb') as avatar_file:
        image_field.save(
            f'{filename_prefix}_{avatar_id}.png',
            File(avatar_file),
            save=False,
        )

    return True


# =========================================================
# HOME
# =========================================================

@login_required(login_url='login')
def home(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    # Monthly public leaderboard data is also shown as a
    # compact right-side panel on the User Home page.
    user_rows = _user_rows(monthly=True)
    worker_rows = _worker_rows(monthly=True)

    league = next(
        (
            row
            for row in user_rows
            if row["user"].pk == request.user.pk
        ),
        None,
    )

    if league is None:
        league = {
            "user": request.user,
            "name": request.user.get_full_name() or request.user.username,
            "xp": 0,
            "resolved": 0,
            "ratings": 0,
            "detailed": 0,
            "verified": 0,
            "rank": len(user_rows) + 1,
            "level": _league_level(0),
        }

    activity = _user_activity_snapshot(request.user)

    return render(
        request,
        'complaints/User_Folder/home.html',
        {
            'league': league,
            'activity': activity,
            'public_worker_rows': worker_rows,
            'public_user_rows': user_rows,
        }
    )


# =========================================================
# USER LOGIN
# =========================================================

@never_cache
@ensure_csrf_cookie
def user_login(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if request.user.is_authenticated:

        try:

            request.user.worker_profile

            return redirect(
                'worker_dashboard'
            )

        except WorkerProfile.DoesNotExist:

            return redirect(
                'home'
            )

    if request.method == 'POST':

        username = request.POST.get(
            'username',
            ''
        ).strip()

        password = request.POST.get(
            'password',
            ''
        )

        if not username or not password:

            messages.error(
                request,
                'Please enter username and password.'
            )

            return redirect(
                'login'
            )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            if user.is_staff or user.is_superuser:
                login(
                    request,
                    user
                )
                return redirect('/admin/')

            try:

                user.worker_profile

                messages.error(
                    request,
                    'Worker account detected. Please use Worker Login.'
                )

                return redirect(
                    'worker_login'
                )

            except WorkerProfile.DoesNotExist:
                pass

            login(
                request,
                user
            )
            request.session['smart_complaint_role'] = 'citizen'

            return redirect(
                'home'
            )

        messages.error(
            request,
            'Invalid username or password.'
        )

        return redirect(
            'login'
        )

    return render(
        request,
        'complaints/login_register.html'
    )


# =========================================================
# USER REGISTER
# =========================================================

def register(request):

    if request.method != 'POST':

        return redirect(
            'login'
        )

    username = request.POST.get(
        'username',
        ''
    ).strip()

    email = request.POST.get(
        'email',
        ''
    ).strip()

    password = request.POST.get(
        'password',
        ''
    )

    if not username or not email or not password:

        messages.error(
            request,
            'Please fill all fields.'
        )

        return redirect(
            'login'
        )

    if User.objects.filter(
        username=username
    ).exists():

        messages.error(
            request,
            'Username already exists.'
        )

        return redirect(
            'login'
        )

    if User.objects.filter(
        email=email
    ).exists():

        messages.error(
            request,
            'This email is already registered.'
        )

        return redirect(
            'login'
        )

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

    UserProfile.objects.create(
        user=user
    )

    messages.success(
        request,
        'Registration successful. Please login.'
    )

    return redirect(
        'login'
    )


# =========================================================
# USER PROFILE
# =========================================================

@login_required(login_url='login')
def profile(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    user = request.user

    # Worker accounts keep using the existing worker profile system.
    if WorkerProfile.objects.filter(user=user).exists():
        worker = user.worker_profile
        return redirect(
            'worker_profile',
            worker_id=worker.id,
        )

    user_profile, created = UserProfile.objects.get_or_create(
        user=user
    )

    user_rating_data = (
        Rating.objects
        .filter(
            complaint__user=user,
            rating_type='worker_to_user'
        )
        .aggregate(
            average=Avg('stars'),
            total=Count('id')
        )
    )

    user_average_rating = user_rating_data['average']
    user_rating_count = user_rating_data['total']

    if request.method == 'POST':

        first_name = request.POST.get(
            'first_name',
            ''
        ).strip()

        last_name = request.POST.get(
            'last_name',
            ''
        ).strip()

        email = request.POST.get(
            'email',
            ''
        ).strip()

        phone = request.POST.get(
            'phone',
            ''
        ).strip()

        gender = request.POST.get(
            'gender',
            ''
        ).strip()

        photo = request.FILES.get(
            'photo'
        )

        free_avatar = request.POST.get(
            'free_avatar',
            ''
        ).strip()

        if not email:

            messages.error(
                request,
                'Email address is required.'
            )

            return redirect(
                'profile'
            )

        if (
            User.objects
            .filter(
                email=email
            )
            .exclude(
                id=user.id
            )
            .exists()
        ):

            messages.error(
                request,
                'This email is already registered.'
            )

            return redirect(
                'profile'
            )

        if phone and len(phone) > 15:

            messages.error(
                request,
                'Phone number is too long.'
            )

            return redirect(
                'profile'
            )

        allowed_genders = {
            'Male',
            'Female',
            'Other',
            'Prefer not to say',
            '',
        }

        if gender not in allowed_genders:

            messages.error(
                request,
                'Please select a valid gender.'
            )

            return redirect(
                'profile'
            )

        if photo:

            if photo.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    'Profile photo must be less than 5 MB.'
                )

                return redirect(
                    'profile'
                )

            if not photo.content_type.startswith(
                'image/'
            ):

                messages.error(
                    request,
                    'Please select a valid image.'
                )

                return redirect(
                    'profile'
                )

            if user_profile.photo:

                old_photo = user_profile.photo.name

                if (
                    old_photo
                    and default_storage.exists(old_photo)
                ):

                    default_storage.delete(
                        old_photo
                    )

            user_profile.photo = photo

        elif free_avatar:

            if not _apply_free_profile_avatar(
                user_profile,
                'photo',
                free_avatar,
                f'user_{user.id}',
            ):

                messages.error(
                    request,
                    'Please select a valid free avatar.'
                )

                return redirect(
                    'profile'
                )

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        user_profile.phone = phone
        user_profile.gender = gender
        user_profile.save()

        messages.success(
            request,
            'Profile updated successfully.'
        )

        return redirect(
            'profile'
        )

    lifetime_rows = _user_rows(
        monthly=False
    )

    league = next(
        (
            row
            for row in lifetime_rows
            if row['user'].pk == user.pk
        ),
        None,
    )

    if league is None:
        league = _find_user_row(
            user,
            monthly=False,
        )

    followers_count = UserFollow.objects.filter(
        following=user
    ).count()

    following_count = UserFollow.objects.filter(
        follower=user
    ).count()

    network_user_ids = set(
        UserFollow.objects.filter(
            follower=user
        ).values_list(
            'following_id',
            flat=True,
        )
    )

    network_user_ids.update(
        UserFollow.objects.filter(
            following=user
        ).values_list(
            'follower_id',
            flat=True,
        )
    )

    network_count = len(
        network_user_ids
    )

    following_ids = set(
        UserFollow.objects.filter(
            follower=user
        ).values_list(
            'following_id',
            flat=True,
        )
    )

    candidate_profiles = list(
        UserProfile.objects
        .select_related('user')
        .filter(
            user__worker_profile__isnull=True,
            user__is_staff=False,
            user__is_superuser=False,
        )
        .exclude(
            user=user
        )
        .exclude(
            user_id__in=following_ids
        )
    )

    current_city = (
        user_profile.city
        or ''
    ).strip().lower()

    candidate_profiles.sort(
        key=lambda item: (
            0
            if (
                current_city
                and (item.city or '').strip().lower()
                == current_city
            )
            else 1,
            (
                item.user.get_full_name()
                or item.user.username
            ).lower(),
        )
    )

    row_map = {
        row['user'].pk: row
        for row in lifetime_rows
    }

    suggestions = []

    for item in candidate_profiles[:4]:

        suggestion_league = row_map.get(
            item.user_id
        )

        if suggestion_league is None:
            suggestion_league = {
                'level': _league_level(0),
                'xp': 0,
                'resolved': 0,
            }

        suggestions.append(
            {
                'user': item.user,
                'profile': item,
                'league': suggestion_league,
            }
        )

    achievement_cards = _user_achievement_cards(
        league
    )

    unlocked_achievements = [
        item
        for item in achievement_cards
        if item['unlocked']
    ]

    return render(
        request,
        'complaints/User_Folder/profile.html',
        {
            'profile_user': user,
            'user_profile': user_profile,
            'user_average_rating': user_average_rating,
            'user_rating_count': user_rating_count,
            'league': league,
            'followers_count': followers_count,
            'following_count': following_count,
            'network_count': network_count,
            'suggestions': suggestions,
            'unlocked_achievements': unlocked_achievements[:4],
            'unlocked_achievement_count': len(
                unlocked_achievements
            ),
        }
    )


# =========================================================
# USER COMMUNITY / FOLLOW SYSTEM
# =========================================================

def public_user_profile(request, username):
    """
    Public safe community profile.

    Private fields such as email, phone, gender, exact address,
    pincode and payment information are intentionally not exposed.
    """

    target_user = get_object_or_404(
        User.objects.filter(
            worker_profile__isnull=True,
            is_staff=False,
            is_superuser=False,
        ),
        username=username,
    )

    target_profile, created = UserProfile.objects.get_or_create(
        user=target_user
    )

    league = _find_user_row(
        target_user,
        monthly=False,
    )

    rating_data = (
        Rating.objects
        .filter(
            complaint__user=target_user,
            rating_type='worker_to_user',
        )
        .aggregate(
            average=Avg('stars'),
            total=Count('id'),
        )
    )

    followers_count = UserFollow.objects.filter(
        following=target_user
    ).count()

    following_count = UserFollow.objects.filter(
        follower=target_user
    ).count()

    can_follow = False
    is_following = False

    if request.user.is_authenticated:

        is_worker_viewer = WorkerProfile.objects.filter(
            user=request.user
        ).exists()

        can_follow = (
            not is_worker_viewer
            and request.user.pk != target_user.pk
            and not request.user.is_staff
            and not request.user.is_superuser
        )

        if can_follow:
            is_following = UserFollow.objects.filter(
                follower=request.user,
                following=target_user,
            ).exists()

    achievement_cards = _user_achievement_cards(
        league
    )

    unlocked_achievements = [
        item
        for item in achievement_cards
        if item['unlocked']
    ]

    return render(
        request,
        'complaints/User_Folder/public_user_profile.html',
        {
            'target_user': target_user,
            'target_profile': target_profile,
            'league': league,
            'user_average_rating': rating_data['average'],
            'user_rating_count': rating_data['total'],
            'followers_count': followers_count,
            'following_count': following_count,
            'can_follow': can_follow,
            'is_following': is_following,
            'unlocked_achievements': unlocked_achievements[:6],
            'unlocked_achievement_count': len(
                unlocked_achievements
            ),
        },
    )


@login_required(login_url='login')
@require_POST
def toggle_user_follow(request, username):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():

        messages.error(
            request,
            'Community follow is available for citizen accounts.'
        )

        return redirect(
            'worker_dashboard'
        )

    target_user = get_object_or_404(
        User.objects.filter(
            worker_profile__isnull=True,
            is_staff=False,
            is_superuser=False,
        ),
        username=username,
    )

    if target_user.pk == request.user.pk:

        messages.info(
            request,
            'You cannot follow your own profile.'
        )

        return redirect(
            'profile'
        )

    follow, created = UserFollow.objects.get_or_create(
        follower=request.user,
        following=target_user,
    )

    if created:

        messages.success(
            request,
            f'You are now following {target_user.get_full_name() or target_user.username}.'
        )

    else:

        follow.delete()

        messages.info(
            request,
            f'You unfollowed {target_user.get_full_name() or target_user.username}.'
        )

    source = request.POST.get(
        'source',
        ''
    ).strip()

    if source == 'people':
        return redirect(
            'people_you_may_know'
        )

    if source == 'followers':
        return redirect(
            'user_followers'
        )

    if source == 'following':
        return redirect(
            'user_following'
        )

    if source == 'profile':
        return redirect(
            'profile'
        )

    return redirect(
        'public_user_profile',
        username=target_user.username,
    )


@login_required(login_url='login')
def user_followers(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():

        return redirect(
            'worker_dashboard'
        )

    links = (
        UserFollow.objects
        .filter(
            following=request.user
        )
        .select_related(
            'follower',
            'follower__user_profile',
        )
    )

    following_ids = set(
        UserFollow.objects.filter(
            follower=request.user
        ).values_list(
            'following_id',
            flat=True,
        )
    )

    rows = _user_rows(
        monthly=False
    )

    row_map = {
        row['user'].pk: row
        for row in rows
    }

    people = []

    for link in links:

        person = link.follower

        people.append(
            {
                'user': person,
                'profile': getattr(
                    person,
                    'user_profile',
                    None,
                ),
                'league': row_map.get(
                    person.pk,
                    {
                        'level': _league_level(0),
                        'xp': 0,
                        'resolved': 0,
                    },
                ),
                'is_following': (
                    person.pk in following_ids
                ),
            }
        )

    return render(
        request,
        'complaints/User_Folder/followers.html',
        {
            'people': people,
            'page_title': 'Followers',
        },
    )


@login_required(login_url='login')
def user_following(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():

        return redirect(
            'worker_dashboard'
        )

    links = (
        UserFollow.objects
        .filter(
            follower=request.user
        )
        .select_related(
            'following',
            'following__user_profile',
        )
    )

    rows = _user_rows(
        monthly=False
    )

    row_map = {
        row['user'].pk: row
        for row in rows
    }

    people = []

    for link in links:

        person = link.following

        people.append(
            {
                'user': person,
                'profile': getattr(
                    person,
                    'user_profile',
                    None,
                ),
                'league': row_map.get(
                    person.pk,
                    {
                        'level': _league_level(0),
                        'xp': 0,
                        'resolved': 0,
                    },
                ),
                'is_following': True,
            }
        )

    return render(
        request,
        'complaints/User_Folder/following.html',
        {
            'people': people,
            'page_title': 'Following',
        },
    )


@login_required(login_url='login')
def people_you_may_know(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():

        return redirect(
            'worker_dashboard'
        )

    user_profile, created = UserProfile.objects.get_or_create(
        user=request.user
    )

    following_ids = set(
        UserFollow.objects.filter(
            follower=request.user
        ).values_list(
            'following_id',
            flat=True,
        )
    )

    candidate_profiles = list(
        UserProfile.objects
        .select_related(
            'user'
        )
        .filter(
            user__worker_profile__isnull=True,
            user__is_staff=False,
            user__is_superuser=False,
        )
        .exclude(
            user=request.user
        )
        .exclude(
            user_id__in=following_ids
        )
    )

    current_city = (
        user_profile.city
        or ''
    ).strip().lower()

    candidate_profiles.sort(
        key=lambda item: (
            0
            if (
                current_city
                and (item.city or '').strip().lower()
                == current_city
            )
            else 1,
            (
                item.user.get_full_name()
                or item.user.username
            ).lower(),
        )
    )

    rows = _user_rows(
        monthly=False
    )

    row_map = {
        row['user'].pk: row
        for row in rows
    }

    people = []

    for item in candidate_profiles:

        people.append(
            {
                'user': item.user,
                'profile': item,
                'league': row_map.get(
                    item.user_id,
                    {
                        'level': _league_level(0),
                        'xp': 0,
                        'resolved': 0,
                    },
                ),
            }
        )

    return render(
        request,
        'complaints/User_Folder/people.html',
        {
            'people': people,
        },
    )


# =========================================================
# CITIZEN PREMIUM
# =========================================================

CITIZEN_PREMIUM_PRICE = Decimal("79.00")
CITIZEN_PREMIUM_DAYS = 30


def _local_premium_test_allowed(request):
    """
    Development-only Citizen Premium switch.

    ALL three conditions are required:
    1. Django DEBUG=True
    2. LOCAL_PREMIUM_TEST_ENABLED=True
    3. Request host is localhost / 127.0.0.1

    This keeps the local test switch unavailable on Railway/live.
    """

    enabled = (
        str(
            os.environ.get(
                "LOCAL_PREMIUM_TEST_ENABLED",
                "",
            )
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )

    host = (
        request.get_host()
        .split(":")[0]
        .strip()
        .lower()
    )

    return (
        settings.DEBUG
        and enabled
        and host in {
            "127.0.0.1",
            "localhost",
        }
    )



def _local_worker_pro_test_allowed(request):
    """
    Development-only Worker Pro switch.

    ALL three conditions are required:
    1. Django DEBUG=True
    2. LOCAL_WORKER_PRO_TEST_ENABLED=True
    3. Request host is localhost / 127.0.0.1

    Railway/live will not expose this test control unless someone
    deliberately misconfigures all three conditions.
    """

    enabled = (
        str(
            os.environ.get(
                "LOCAL_WORKER_PRO_TEST_ENABLED",
                "",
            )
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )

    host = (
        request.get_host()
        .split(":")[0]
        .strip()
        .lower()
    )

    return (
        settings.DEBUG
        and enabled
        and host in {
            "127.0.0.1",
            "localhost",
        }
    )

def _sync_citizen_premium(user):
    """
    Keep the paid membership and the existing UserProfile.is_premium
    flag aligned.

    UserProfile.is_premium remains useful to the existing theme UI,
    but payment/expiry authority comes from UserPremiumMembership.
    """

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

    active = membership.is_active

    if profile.is_premium != active:
        profile.is_premium = active
        profile.save(
            update_fields=[
                "is_premium",
                "updated_at",
            ]
        )

    return profile, membership, active


def _activate_citizen_premium(
    membership,
    payment,
):
    """
    Activate exactly once per verified Razorpay payment.

    Each successful ₹79 payment:
    - adds 30 days,
    - starts a fresh 60-credit AI cycle,
    - never creates an automatic debit.
    """

    payment_id = (
        payment.razorpay_payment_id
        or ""
    ).strip()

    if (
        payment_id
        and membership.last_razorpay_payment_id
        == payment_id
    ):
        return membership

    now = timezone.now()

    if (
        membership.current_period_end
        and membership.current_period_end > now
    ):
        base_end = (
            membership.current_period_end
        )
    else:
        base_end = now

    membership.status = "active"
    membership.price = (
        CITIZEN_PREMIUM_PRICE
    )

    # Fresh AI-credit cycle starts now.
    membership.current_period_start = now

    # Access itself is extended from the later of now/current expiry.
    membership.current_period_end = (
        base_end
        + timedelta(
            days=CITIZEN_PREMIUM_DAYS
        )
    )

    if not membership.activated_at:
        membership.activated_at = now

    membership.last_paid_at = now
    membership.last_razorpay_payment_id = (
        payment_id
    )
    membership.renewal_count += 1

    membership.save(
        update_fields=[
            "status",
            "price",
            "current_period_start",
            "current_period_end",
            "activated_at",
            "last_paid_at",
            "last_razorpay_payment_id",
            "renewal_count",
            "updated_at",
        ]
    )

    profile, created = (
        UserProfile.objects
        .get_or_create(
            user=membership.user
        )
    )

    if not profile.is_premium:
        profile.is_premium = True
        profile.save(
            update_fields=[
                "is_premium",
                "updated_at",
            ]
        )

    return membership


@login_required(login_url="login")
def citizen_premium(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(
        request
    )
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():
        return redirect(
            "worker_settings"
        )

    profile, membership, is_active = (
        _sync_citizen_premium(
            request.user
        )
    )

    ai_status = get_ai_credit_status(
        request.user
    )

    return render(
        request,
        "complaints/User_Folder/citizen_premium.html",
        {
            "user_profile": profile,
            "membership": membership,
            "premium_active": is_active,
            "premium_price":
                CITIZEN_PREMIUM_PRICE,
            "premium_days":
                CITIZEN_PREMIUM_DAYS,
            "ai_status":
                ai_status,
            "local_premium_test_allowed":
                _local_premium_test_allowed(
                    request
                ),
        },
    )


@login_required(login_url="login")
@require_POST
def create_citizen_premium_order(request):

    admin_redirect = _admin_account_redirect(
        request
    )
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Citizen Premium is for citizen accounts.",
            },
            status=403,
        )

    razorpay_key_id = getattr(
        settings,
        "RAZORPAY_KEY_ID",
        "",
    )

    razorpay_key_secret = getattr(
        settings,
        "RAZORPAY_KEY_SECRET",
        "",
    )

    if (
        not razorpay_key_id
        or not razorpay_key_secret
    ):
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Payment service is not configured.",
            },
            status=503,
        )

    profile, membership, active = (
        _sync_citizen_premium(
            request.user
        )
    )

    payment = PaymentTransaction.objects.create(
        payer=request.user,
        user_premium_membership=membership,
        payment_for="citizen_premium",
        amount=CITIZEN_PREMIUM_PRICE,
        currency="INR",
        status="created",
        description=(
            "Citizen Premium - 30 day pass"
        ),
    )

    receipt = (
        f"sc_cp_{payment.id}"
    )

    payment.receipt = receipt
    payment.save(
        update_fields=[
            "receipt",
            "updated_at",
        ]
    )

    try:
        client = razorpay.Client(
            auth=(
                razorpay_key_id,
                razorpay_key_secret,
            )
        )

        order = client.order.create(
            {
                "amount": int(
                    CITIZEN_PREMIUM_PRICE
                    * 100
                ),
                "currency": "INR",
                "receipt": receipt,
                "notes": {
                    "payment_transaction_id":
                        str(payment.id),
                    "purpose":
                        "Citizen Premium 30 day pass",
                    "user_id":
                        str(request.user.id),
                },
            }
        )

        order_id = str(
            order.get(
                "id",
                "",
            )
        ).strip()

        if not order_id:
            raise ValueError(
                "Razorpay order ID missing."
            )

        payment.razorpay_order_id = (
            order_id
        )
        payment.status = "pending"
        payment.save(
            update_fields=[
                "razorpay_order_id",
                "status",
                "updated_at",
            ]
        )

        return JsonResponse(
            {
                "success": True,
                "key_id":
                    razorpay_key_id,
                "order_id":
                    order_id,
                "amount": int(
                    CITIZEN_PREMIUM_PRICE
                    * 100
                ),
                "currency": "INR",
                "transaction_id":
                    payment.id,
                "plan_name":
                    "Citizen Premium",
                "description":
                    "30 days, 60 AI credits, premium themes",
            }
        )

    except razorpay.errors.BadRequestError as error:

        payment.status = "failed"
        payment.failed_at = (
            timezone.now()
        )
        payment.save(
            update_fields=[
                "status",
                "failed_at",
                "updated_at",
            ]
        )

        print(
            "CITIZEN PREMIUM ORDER BAD REQUEST:",
            error,
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Razorpay rejected the payment order.",
            },
            status=400,
        )

    except razorpay.errors.ServerError as error:

        payment.status = "failed"
        payment.failed_at = (
            timezone.now()
        )
        payment.save(
            update_fields=[
                "status",
                "failed_at",
                "updated_at",
            ]
        )

        print(
            "CITIZEN PREMIUM ORDER SERVER ERROR:",
            error,
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Payment service is temporarily unavailable.",
            },
            status=502,
        )

    except Exception as error:

        payment.status = "failed"
        payment.failed_at = (
            timezone.now()
        )
        payment.save(
            update_fields=[
                "status",
                "failed_at",
                "updated_at",
            ]
        )

        print(
            "CITIZEN PREMIUM ORDER ERROR:",
            error,
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Unable to create the premium payment order.",
            },
            status=500,
        )


@login_required(login_url="login")
@require_POST
def verify_citizen_premium_payment(request):
    """
    Citizen Premium becomes active only after server-side verification.

    Browser-provided amount/plan data is never trusted.
    """

    admin_redirect = _admin_account_redirect(
        request
    )
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Citizen Premium is for citizen accounts.",
            },
            status=403,
        )

    razorpay_key_id = getattr(
        settings,
        "RAZORPAY_KEY_ID",
        "",
    )

    razorpay_key_secret = getattr(
        settings,
        "RAZORPAY_KEY_SECRET",
        "",
    )

    if (
        not razorpay_key_id
        or not razorpay_key_secret
    ):
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Payment service is not configured.",
            },
            status=503,
        )

    try:
        payload = json.loads(
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
                "message":
                    "Invalid payment verification data.",
            },
            status=400,
        )

    transaction_id = payload.get(
        "transaction_id"
    )

    order_id = str(
        payload.get(
            "razorpay_order_id",
            "",
        )
    ).strip()

    payment_id = str(
        payload.get(
            "razorpay_payment_id",
            "",
        )
    ).strip()

    signature = str(
        payload.get(
            "razorpay_signature",
            "",
        )
    ).strip()

    if (
        not transaction_id
        or not order_id
        or not payment_id
        or not signature
    ):
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Payment verification data is incomplete.",
            },
            status=400,
        )

    try:
        transaction_id = int(
            transaction_id
        )
    except (
        TypeError,
        ValueError,
    ):
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Invalid transaction ID.",
            },
            status=400,
        )

    client = razorpay.Client(
        auth=(
            razorpay_key_id,
            razorpay_key_secret,
        )
    )

    try:
        with transaction.atomic():

            payment = (
                PaymentTransaction.objects
                .select_for_update()
                .select_related(
                    "user_premium_membership"
                )
                .get(
                    id=transaction_id,
                    payer=request.user,
                    payment_for="citizen_premium",
                )
            )

            membership = (
                payment.user_premium_membership
            )

            if (
                not membership
                or membership.user_id
                != request.user.id
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Premium membership does not match this payment.",
                    },
                    status=400,
                )

            if payment.status == "paid":

                if (
                    payment.razorpay_order_id
                    == order_id
                    and payment.razorpay_payment_id
                    == payment_id
                ):
                    _activate_citizen_premium(
                        membership,
                        payment,
                    )

                    return JsonResponse(
                        {
                            "success": True,
                            "message":
                                "Citizen Premium is already active.",
                            "redirect_url":
                                "/citizen-premium/",
                        }
                    )

                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "This payment transaction has already been used.",
                    },
                    status=409,
                )

            if payment.status != "pending":
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "This payment is not pending verification.",
                    },
                    status=409,
                )

            if (
                payment.razorpay_order_id
                != order_id
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Razorpay order ID does not match.",
                    },
                    status=400,
                )

            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id":
                        order_id,
                    "razorpay_payment_id":
                        payment_id,
                    "razorpay_signature":
                        signature,
                }
            )

            provider_payment = (
                client.payment.fetch(
                    payment_id
                )
            )

            provider_payment_id = str(
                provider_payment.get(
                    "id",
                    "",
                )
            ).strip()

            provider_order_id = str(
                provider_payment.get(
                    "order_id",
                    "",
                )
            ).strip()

            provider_currency = str(
                provider_payment.get(
                    "currency",
                    "",
                )
            ).strip().upper()

            provider_status = str(
                provider_payment.get(
                    "status",
                    "",
                )
            ).strip().lower()

            provider_captured = (
                provider_payment.get(
                    "captured",
                    False,
                )
            )

            try:
                provider_amount = int(
                    provider_payment.get(
                        "amount"
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Razorpay returned an invalid amount.",
                    },
                    status=502,
                )

            expected_amount = int(
                CITIZEN_PREMIUM_PRICE
                * 100
            )

            if (
                provider_payment_id
                != payment_id
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Razorpay payment ID verification failed.",
                    },
                    status=400,
                )

            if (
                provider_order_id
                != payment.razorpay_order_id
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Razorpay payment does not belong to this order.",
                    },
                    status=400,
                )

            if (
                provider_amount
                != expected_amount
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Payment amount verification failed.",
                    },
                    status=400,
                )

            if provider_currency != "INR":
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Payment currency verification failed.",
                    },
                    status=400,
                )

            if (
                provider_status
                != "captured"
                or provider_captured
                is not True
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Payment has not been captured by Razorpay.",
                    },
                    status=409,
                )

            payment.razorpay_payment_id = (
                payment_id
            )
            payment.status = "paid"
            payment.paid_at = (
                timezone.now()
            )
            payment.failed_at = None

            payment.save(
                update_fields=[
                    "razorpay_payment_id",
                    "status",
                    "paid_at",
                    "failed_at",
                    "updated_at",
                ]
            )

            _activate_citizen_premium(
                membership,
                payment,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message":
                        "Citizen Premium activated successfully.",
                    "redirect_url":
                        "/citizen-premium/",
                }
            )

    except PaymentTransaction.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Payment transaction was not found.",
            },
            status=404,
        )

    except razorpay.errors.SignatureVerificationError:
        return JsonResponse(
            {
                "success": False,
                "message":
                    "Payment signature verification failed.",
            },
            status=400,
        )

    except Exception as error:
        print(
            "CITIZEN PREMIUM VERIFY ERROR:",
            error,
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Unable to verify the payment right now.",
            },
            status=500,
        )


# =========================================================
# LOCAL-ONLY CITIZEN PREMIUM TEST CONTROLS
# =========================================================

@login_required(login_url="login")
@require_POST
def activate_local_test_premium(request):
    """
    Activate Citizen Premium without Razorpay ONLY on local development.

    This endpoint refuses to run unless:
    - DEBUG=True
    - LOCAL_PREMIUM_TEST_ENABLED=True
    - host is localhost / 127.0.0.1
    """

    if not _local_premium_test_allowed(
        request
    ):
        return HttpResponse(
            "Local Premium test activation is disabled.",
            status=403,
        )

    admin_redirect = _admin_account_redirect(
        request
    )
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():
        messages.error(
            request,
            "Citizen Premium test activation is only for citizen accounts.",
        )
        return redirect(
            "citizen_premium"
        )

    with transaction.atomic():

        membership, created = (
            UserPremiumMembership.objects
            .select_for_update()
            .get_or_create(
                user=request.user
            )
        )

        profile, profile_created = (
            UserProfile.objects
            .select_for_update()
            .get_or_create(
                user=request.user
            )
        )

        now = timezone.now()

        membership.status = "active"
        membership.price = (
            CITIZEN_PREMIUM_PRICE
        )
        membership.current_period_start = now
        membership.current_period_end = (
            now
            + timedelta(
                days=CITIZEN_PREMIUM_DAYS
            )
        )

        if not membership.activated_at:
            membership.activated_at = now

        membership.save(
            update_fields=[
                "status",
                "price",
                "current_period_start",
                "current_period_end",
                "activated_at",
                "updated_at",
            ]
        )

        if not profile.is_premium:
            profile.is_premium = True
            profile.save(
                update_fields=[
                    "is_premium",
                    "updated_at",
                ]
            )

    messages.success(
        request,
        "Local test Premium activated for 30 days. No Razorpay payment was created.",
    )

    return redirect(
        "citizen_premium"
    )


@login_required(login_url="login")
@require_POST
def reset_local_test_premium(request):
    """
    Return the local citizen account to Free mode.

    This is also protected by the same three local-development checks.
    """

    if not _local_premium_test_allowed(
        request
    ):
        return HttpResponse(
            "Local Premium test reset is disabled.",
            status=403,
        )

    admin_redirect = _admin_account_redirect(
        request
    )
    if admin_redirect:
        return admin_redirect

    if WorkerProfile.objects.filter(
        user=request.user
    ).exists():
        return redirect(
            "worker_settings"
        )

    with transaction.atomic():

        membership, created = (
            UserPremiumMembership.objects
            .select_for_update()
            .get_or_create(
                user=request.user
            )
        )

        profile, profile_created = (
            UserProfile.objects
            .select_for_update()
            .get_or_create(
                user=request.user
            )
        )

        membership.status = "inactive"
        membership.current_period_start = None
        membership.current_period_end = None

        membership.save(
            update_fields=[
                "status",
                "current_period_start",
                "current_period_end",
                "updated_at",
            ]
        )

        if profile.is_premium:
            profile.is_premium = False
            profile.save(
                update_fields=[
                    "is_premium",
                    "updated_at",
                ]
            )

    messages.success(
        request,
        "Local test Premium reset. This account is back on the Free plan.",
    )

    return redirect(
        "citizen_premium"
    )


# =========================================================
# USER SETTINGS
# =========================================================

@login_required(login_url='login')
def user_settings(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    try:
        request.user.worker_profile

        return redirect(
            'worker_settings'
        )

    except WorkerProfile.DoesNotExist:
        pass

    user_profile, membership, premium_active = (
        _sync_citizen_premium(
            request.user
        )
    )

    ai_status = get_ai_credit_status(
        request.user
    )

    return render(
        request,
        'complaints/User_Folder/user_settings.html',
        {
            'user_profile':
                user_profile,
            'user_is_premium':
                premium_active,
            'premium_membership':
                membership,
            'ai_status':
                ai_status,
        }
    )


# =========================================================
# USER CHANGE PASSWORD
# =========================================================

@login_required(login_url='login')
@require_POST
def user_change_password(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect
    try:
        request.user.worker_profile
        messages.error(request, 'Worker accounts must use Worker Settings.')
        return redirect('worker_settings')
    except WorkerProfile.DoesNotExist:
        pass

    current_password = request.POST.get('current_password', '')
    new_password = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not current_password or not new_password or not confirm_password:
        messages.error(request, 'Please fill all password fields.')
        return redirect('user_settings')

    if not request.user.check_password(current_password):
        messages.error(request, 'Current password is incorrect.')
        return redirect('user_settings')

    if new_password != confirm_password:
        messages.error(request, 'New password and confirm password do not match.')
        return redirect('user_settings')

    if len(new_password) < 6:
        messages.error(request, 'New password must be at least 6 characters.')
        return redirect('user_settings')

    if current_password == new_password:
        messages.error(request, 'New password must be different from current password.')
        return redirect('user_settings')

    request.user.set_password(new_password)
    request.user.save()
    update_session_auth_hash(request, request.user)

    messages.success(request, 'Password changed successfully.')
    return redirect('user_settings')


# =========================================================
# USER ADDRESS / LOCATION
# =========================================================

@login_required(login_url='login')
@require_POST
def user_update_address(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect
    try:
        request.user.worker_profile
        messages.error(request, 'Worker accounts must use Worker Settings.')
        return redirect('worker_settings')
    except WorkerProfile.DoesNotExist:
        pass

    address = request.POST.get('address', '').strip()
    city = request.POST.get('city', '').strip()
    state = request.POST.get('state', '').strip()
    pincode = request.POST.get('pincode', '').strip()

    if not address or not city or not state or not pincode:
        messages.error(request, 'Please fill all address fields.')
        return redirect('user_settings')

    if len(address) > 500:
        messages.error(request, 'Address must be less than 500 characters.')
        return redirect('user_settings')

    if len(city) > 100 or len(state) > 100:
        messages.error(request, 'City and state must be less than 100 characters.')
        return redirect('user_settings')

    if not pincode.isdigit() or len(pincode) != 6:
        messages.error(request, 'Please enter a valid 6-digit PIN code.')
        return redirect('user_settings')

    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    user_profile.address = address
    user_profile.city = city
    user_profile.state = state
    user_profile.pincode = pincode
    user_profile.save(update_fields=['address', 'city', 'state', 'pincode', 'updated_at'])

    messages.success(request, 'Address updated successfully.')
    return redirect('user_settings')


# =========================================================
# USER HELP & SUPPORT
# =========================================================

@login_required(login_url='login')
@require_POST
def user_support_request(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect
    try:
        request.user.worker_profile
        messages.error(request, 'Worker accounts must use Worker Settings.')
        return redirect('worker_settings')
    except WorkerProfile.DoesNotExist:
        pass

    issue_type = request.POST.get('issue_type', '').strip()
    subject = request.POST.get('subject', '').strip()
    support_message = request.POST.get('message', '').strip()

    valid_issue_types = {choice[0] for choice in SupportRequest.ISSUE_TYPE_CHOICES}

    if issue_type not in valid_issue_types:
        messages.error(request, 'Please select a valid issue type.')
        return redirect('user_settings')

    if not subject or not support_message:
        messages.error(request, 'Please enter subject and message.')
        return redirect('user_settings')

    if len(subject) > 150:
        messages.error(request, 'Subject must be less than 150 characters.')
        return redirect('user_settings')

    if len(support_message) > 2000:
        messages.error(request, 'Support message must be less than 2000 characters.')
        return redirect('user_settings')

    SupportRequest.objects.create(
        user=request.user,
        issue_type=issue_type,
        subject=subject,
        message=support_message,
    )

    messages.success(request, 'Your support request has been submitted successfully.')
    return redirect('user_settings')


# =========================================================
# USER DELETE ACCOUNT
# =========================================================

@login_required(login_url='login')
@require_POST
def user_delete_account(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    try:
        request.user.worker_profile

        messages.error(
            request,
            'Worker accounts must be deleted from Worker Settings.'
        )

        return redirect(
            'worker_settings'
        )

    except WorkerProfile.DoesNotExist:
        pass

    password = request.POST.get(
        'password',
        ''
    )

    confirmation = request.POST.get(
        'confirmation',
        ''
    ).strip()

    if not password:
        messages.error(
            request,
            'Please enter your current password.'
        )

        return redirect(
            'user_settings'
        )

    if not request.user.check_password(
        password
    ):
        messages.error(
            request,
            'Current password is incorrect.'
        )

        return redirect(
            'user_settings'
        )

    if confirmation != 'DELETE':
        messages.error(
            request,
            'Type DELETE exactly to confirm account deletion.'
        )

        return redirect(
            'user_settings'
        )

    user = request.user
    storage_files = set()

    try:
        user_profile = user.user_profile

        if user_profile.photo:
            storage_files.add(
                user_profile.photo.name
            )

    except UserProfile.DoesNotExist:
        pass

    complaints = (
        Complaint.objects
        .filter(user=user)
        .prefetch_related('chat_messages')
    )

    sent_chat_images = (
        ChatMessage.objects
        .filter(sender=user)
        .exclude(image='')
        .values_list('image', flat=True)
    )

    for image_name in sent_chat_images:
        if image_name:
            storage_files.add(image_name)

    for complaint in complaints:
        if complaint.photo:
            storage_files.add(
                complaint.photo.name
            )

        if complaint.after_photo:
            storage_files.add(
                complaint.after_photo.name
            )

        for chat_message in complaint.chat_messages.all():
            if chat_message.image:
                storage_files.add(
                    chat_message.image.name
                )

    try:
        with transaction.atomic():
            user.delete()

    except Exception:
        messages.error(
            request,
            'Account could not be deleted. Please try again.'
        )

        return redirect(
            'user_settings'
        )

    for file_name in storage_files:
        try:
            if file_name and default_storage.exists(file_name):
                default_storage.delete(file_name)
        except Exception:
            pass

    logout(
        request
    )

    messages.success(
        request,
        'Your Smart Complaint account has been permanently deleted.'
    )

    return redirect(
        'login'
    )


# =========================================================
# USER LOGOUT
# =========================================================

def user_logout(request):

    logout(
        request
    )

    return redirect(
        'login'
    )


# =========================================================
# SMART WORKER ASSIGNMENT HELPERS
# =========================================================

def _worker_experience_score(experience):
    experience_scores = {
        "1 Month": 1,
        "2 Months": 2,
        "3 Months": 3,
        "6 Months": 6,
        "1 Year": 12,
        "2 Years": 24,
        "3 Years": 36,
        "4 Years": 48,
        "5 Years": 60,
        "More than 5 Years": 72,
    }

    return experience_scores.get(
        experience,
        0,
    )


def get_smart_worker():
    """
    Choose the best approved worker.

    Priority:
    1. Fewer Pending / In Progress complaints
    2. Better average user rating
    3. More experience
    4. More resolved complaints
    """

    workers = (
        WorkerProfile.objects
        .filter(
            is_approved=True,
            verification_status="Approved",
            availability_status="available",
        )
        .select_related("user")
        .order_by("created_at", "id")
    )

    best_worker = None
    best_rank = None

    for worker in workers:

        active_complaints = (
            Complaint.objects
            .filter(
                assigned_worker=worker,
                status__in=[
                    "Pending",
                    "In Progress",
                ],
            )
            .count()
        )

        rating_data = (
            Rating.objects
            .filter(
                complaint__assigned_worker=worker,
                rating_type="user_to_worker",
            )
            .aggregate(
                average=Avg("stars"),
            )
        )

        average_rating = (
            rating_data["average"]
            or 0
        )

        resolved_complaints = (
            Complaint.objects
            .filter(
                assigned_worker=worker,
                status="Resolved",
            )
            .count()
        )

        experience_score = (
            _worker_experience_score(
                worker.experience
            )
        )

        rank = (
            active_complaints,
            -float(average_rating),
            -experience_score,
            -resolved_complaints,
            worker.created_at,
            worker.id,
        )

        if (
            best_rank is None
            or rank < best_rank
        ):
            best_rank = rank
            best_worker = worker

    return best_worker


def notify_worker_about_assignment(
    worker,
    complaint,
    smart_assigned=False,
):
    if not worker:
        return

    if smart_assigned:
        title = "New Smart Assignment"
        message = (
            f"{complaint.tracking_id} was automatically assigned to you. "
            f"Priority: {complaint.priority}."
        )
    else:
        title = "New Complaint Assigned"
        message = (
            f"{complaint.tracking_id} was assigned to you. "
            f"Priority: {complaint.priority}."
        )

    Notification.objects.create(
        recipient=worker.user,
        complaint=complaint,
        notification_type="assignment",
        title=title,
        message=message,
    )

    try:
        send_push_to_user(
            worker.user,
            title,
            message,
            data={
                "type": "assignment",
                "complaint_id": str(complaint.id),
                "tracking_id": complaint.tracking_id,
            },
        )

    except Exception as error:
        print(
            "Assignment push notification failed:",
            error,
        )


# =========================================================
# SUBMIT COMPLAINT
# =========================================================

@login_required(login_url='login')
def submit_complaint(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    workers = (
        WorkerProfile.objects
        .filter(
            is_approved=True,
            verification_status="Approved",
            availability_status="available",
        )
        .select_related('user')
        .order_by('-created_at')
    )

    if request.method == 'POST':

        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'Normal').strip()
        assignment_mode = request.POST.get(
            'assignment_mode',
            'smart',
        ).strip()
        worker_id = request.POST.get('worker', '').strip()
        latitude = request.POST.get('latitude', '').strip()
        longitude = request.POST.get('longitude', '').strip()
        photo = request.FILES.get('photo')

        valid_priorities = [
            choice[0]
            for choice in Complaint.PRIORITY_CHOICES
        ]

        if not name or not email or not subject or not description:
            messages.error(request, 'Please fill all complaint fields.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        if priority not in valid_priorities:
            messages.error(request, 'Please select a valid complaint priority.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        if assignment_mode not in ['smart', 'manual']:
            messages.error(request, 'Please select a valid worker assignment option.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        if not latitude or not longitude:
            messages.error(request, 'Please select complaint location.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        try:
            latitude_value = float(latitude)
            longitude_value = float(longitude)

            if not (
                -90 <= latitude_value <= 90
                and -180 <= longitude_value <= 180
            ):
                raise ValueError

        except (ValueError, TypeError):
            messages.error(request, 'Invalid complaint location.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        if not photo:
            messages.error(request, 'Please upload complaint photo.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        allowed_types = [
            'image/jpeg',
            'image/png',
            'image/webp',
        ]

        if photo.content_type not in allowed_types:
            messages.error(request, 'Only JPG, PNG or WEBP images are allowed.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        if photo.size > 5 * 1024 * 1024:
            messages.error(request, 'Complaint photo must be less than 5 MB.')
            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {'workers': workers},
            )

        selected_worker = None
        smart_assigned = False

        if assignment_mode == 'smart':

            selected_worker = get_smart_worker()

            if selected_worker is None:
                messages.error(
                    request,
                    (
                        'No worker is currently available. '
                        'Please try again later or choose an available worker.'
                    ),
                )
                return render(
                    request,
                    'complaints/User_Folder/submit_complaint.html',
                    {'workers': workers},
                )

            smart_assigned = True

        else:

            if not worker_id:
                messages.error(
                    request,
                    'Please select a worker or choose Smart Auto Assign.',
                )
                return render(
                    request,
                    'complaints/User_Folder/submit_complaint.html',
                    {'workers': workers},
                )

            try:
                selected_worker = WorkerProfile.objects.get(
                    id=worker_id,
                    is_approved=True,
                    verification_status="Approved",
                    availability_status="available",
                )

            except (
                WorkerProfile.DoesNotExist,
                ValueError,
                TypeError,
            ):
                messages.error(request, 'Selected worker is not available.')
                return render(
                    request,
                    'complaints/User_Folder/submit_complaint.html',
                    {'workers': workers},
                )

        complaint = Complaint.objects.create(
            user=request.user,
            assigned_worker=selected_worker,
            name=name,
            email=email,
            subject=subject,
            description=description,
            priority=priority,
            photo=photo,
            latitude=latitude_value,
            longitude=longitude_value,
            status='Pending',
        )

        if selected_worker:

            notify_worker_about_assignment(
                worker=selected_worker,
                complaint=complaint,
                smart_assigned=smart_assigned,
            )

            if smart_assigned:
                messages.success(
                    request,
                    (
                        f'Complaint submitted successfully with {priority} priority. '
                        f'Smart Assignment selected {selected_worker.name} '
                        f'({selected_worker.worker_id}).'
                    ),
                )
            else:
                messages.success(
                    request,
                    (
                        f'Complaint submitted successfully with {priority} priority. '
                        f'{selected_worker.name} ({selected_worker.worker_id}) '
                        f'was assigned.'
                    ),
                )

        else:

            messages.warning(
                request,
                (
                    f'Complaint submitted successfully with {priority} priority, '
                    'but no approved worker is available right now.'
                ),
            )

        return render(
            request,
            'complaints/User_Folder/success.html',
            {'complaint': complaint},
        )

    return render(
        request,
        'complaints/User_Folder/submit_complaint.html',
        {'workers': workers},
    )


# =========================================================
# SUCCESS PAGE
# =========================================================

@login_required(login_url='login')
def success(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    return render(
        request,
        'complaints/User_Folder/success.html'
    )


# =========================================================
# CHECK COMPLAINT STATUS
# =========================================================

def check_status(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    complaint = None
    status = None

    if request.method == 'POST':

        tracking_id = request.POST.get(
            'tracking_id',
            ''
        ).strip()

        if not tracking_id:

            status = 'Not Found'

        else:

            try:

                complaint = (
                    Complaint.objects
                    .select_related(
                        'assigned_worker'
                    )
                    .get(
                        tracking_id=tracking_id
                    )
                )

                status = complaint.status

            except Complaint.DoesNotExist:

                status = 'Not Found'

    return render(
        request,
        'complaints/User_Folder/check_status.html',
        {
            'complaint': complaint,
            'status': status,
        }
    )


# =========================================================
# MY COMPLAINTS
# =========================================================

@login_required(login_url='login')
def my_complaints(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    complaints = list(
        Complaint.objects
        .filter(
            user=request.user
        )
        .select_related(
            'assigned_worker',
            'assigned_worker__user'
        )
        .order_by(
            '-created_at'
        )
    )

    complaint_ids = [
        complaint.id
        for complaint in complaints
    ]

    ratings = (
        Rating.objects
        .filter(
            complaint_id__in=complaint_ids,
            rating_type='user_to_worker'
        )
    )

    rating_map = {
        rating.complaint_id: rating
        for rating in ratings
    }

    for complaint in complaints:

        complaint.user_rating = (
            rating_map.get(
                complaint.id
            )
        )

    return render(
        request,
        'complaints/User_Folder/my_complaints.html',
        {
            'complaints': complaints
        }
    )


# =========================================================
# USER -> WORKER RATING
# =========================================================

@login_required(login_url='login')
def rate_worker(request, complaint_id):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if request.method != 'POST':

        return redirect(
            'my_complaints'
        )

    try:

        complaint = (
            Complaint.objects
            .select_related(
                'assigned_worker'
            )
            .get(
                id=complaint_id,
                user=request.user
            )
        )

    except Complaint.DoesNotExist:

        messages.error(
            request,
            'Complaint not found.'
        )

        return redirect(
            'my_complaints'
        )

    if complaint.status != 'Resolved':

        messages.error(
            request,
            'You can rate the worker only after the complaint is resolved.'
        )

        return redirect(
            'my_complaints'
        )

    if not complaint.assigned_worker:

        messages.error(
            request,
            'No worker is assigned to this complaint.'
        )

        return redirect(
            'my_complaints'
        )

    if Rating.objects.filter(
        complaint=complaint,
        rating_type='user_to_worker'
    ).exists():

        messages.info(
            request,
            'You have already rated this worker for this complaint.'
        )

        return redirect(
            'my_complaints'
        )

    stars = request.POST.get(
        'stars',
        ''
    ).strip()

    problem = request.POST.get(
        'problem',
        ''
    ).strip()

    try:

        stars = int(
            stars
        )

    except (
        ValueError,
        TypeError
    ):

        messages.error(
            request,
            'Please select a star rating.'
        )

        return redirect(
            'my_complaints'
        )

    if stars < 1 or stars > 5:

        messages.error(
            request,
            'Rating must be between 1 and 5 stars.'
        )

        return redirect(
            'my_complaints'
        )

    if len(problem) > 1000:

        messages.error(
            request,
            'Problem / feedback must be less than 1000 characters.'
        )

        return redirect(
            'my_complaints'
        )

    Rating.objects.create(
        complaint=complaint,
        rater=request.user,
        rating_type='user_to_worker',
        stars=stars,
        problem=problem,
    )

    messages.success(
        request,
        'Worker rating submitted successfully.'
    )

    return redirect(
        'my_complaints'
    )


# =========================================================
# USER NOTIFICATIONS
# =========================================================

@login_required(login_url='login')
def notifications(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    user_notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related('complaint')
        .order_by('-created_at')
    )

    unread_count = (
        user_notifications
        .filter(is_read=False)
        .count()
    )

    if request.method == 'POST':

        Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(
            is_read=True
        )

        messages.success(
            request,
            'All notifications marked as read.'
        )

        return redirect(
            'notifications'
        )

    return render(
        request,
        'complaints/User_Folder/notifications.html',
        {
            'notifications': user_notifications,
            'unread_count': unread_count,
        }
    )


# =========================================================
# WORKER DETAILS
# =========================================================

@login_required(login_url='login')
def worker_details(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    workers = (
        WorkerProfile.objects
        .filter(
            is_approved=True
        )
        .select_related(
            'user'
        )
        .order_by(
            '-created_at'
        )
    )

    return render(
        request,
        'complaints/User_Folder/worker_details.html',
        {
            'workers': workers
        }
    )

# =========================================================
# WORKER PROFILE
# =========================================================

def worker_profile(request, worker_id):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    worker = get_object_or_404(
        WorkerProfile.objects.select_related("user"),
        id=worker_id,
        is_approved=True,
    )

    is_owner = (
        request.user.is_authenticated
        and request.user.pk == worker.user_id
    )

    # -----------------------------------------------------
    # Edit profile - owner only
    # -----------------------------------------------------
    if request.method == "POST":

        if not is_owner:
            messages.error(
                request,
                "You cannot edit this worker profile.",
            )
            return redirect(
                "worker_profile",
                worker_id=worker.id,
            )

        name = request.POST.get(
            "name",
            "",
        ).strip()

        email = request.POST.get(
            "email",
            "",
        ).strip()

        phone = request.POST.get(
            "phone",
            "",
        ).strip()

        experience = request.POST.get(
            "experience",
            "",
        ).strip()

        photo = request.FILES.get(
            "photo"
        )

        free_avatar = request.POST.get(
            "free_avatar",
            "",
        ).strip()

        if not name or not email or not phone or not experience:
            messages.error(
                request,
                "Please fill all required fields.",
            )
            return redirect(
                "worker_profile",
                worker_id=worker.id,
            )

        if (
            User.objects
            .filter(email=email)
            .exclude(id=worker.user_id)
            .exists()
        ):
            messages.error(
                request,
                "This email is already registered.",
            )
            return redirect(
                "worker_profile",
                worker_id=worker.id,
            )

        valid_experience = {
            choice[0]
            for choice in WorkerProfile.EXPERIENCE_CHOICES
        }

        if experience not in valid_experience:
            messages.error(
                request,
                "Invalid experience selected.",
            )
            return redirect(
                "worker_profile",
                worker_id=worker.id,
            )

        if photo:

            if photo.size > 5 * 1024 * 1024:
                messages.error(
                    request,
                    "Profile photo must be less than 5 MB.",
                )
                return redirect(
                    "worker_profile",
                    worker_id=worker.id,
                )

            if not photo.content_type.startswith("image/"):
                messages.error(
                    request,
                    "Please select a valid image.",
                )
                return redirect(
                    "worker_profile",
                    worker_id=worker.id,
                )

            if worker.photo:
                old_photo = worker.photo.name

                if (
                    old_photo
                    and default_storage.exists(old_photo)
                ):
                    default_storage.delete(old_photo)

            worker.photo = photo

        elif free_avatar:

            if not _apply_free_profile_avatar(
                worker,
                "photo",
                free_avatar,
                f"worker_{worker.id}",
            ):
                messages.error(
                    request,
                    "Please select a valid free avatar.",
                )
                return redirect(
                    "worker_profile",
                    worker_id=worker.id,
                )

        worker.name = name
        worker.phone = phone
        worker.experience = experience

        worker.user.email = email
        worker.user.save(
            update_fields=["email"]
        )

        worker.save()

        messages.success(
            request,
            "Worker profile updated successfully.",
        )

        return redirect(
            "worker_profile",
            worker_id=worker.id,
        )

    # -----------------------------------------------------
    # Performance
    # -----------------------------------------------------
    assigned_qs = Complaint.objects.filter(
        assigned_worker=worker
    )

    jobs_assigned = assigned_qs.count()
    jobs_completed = assigned_qs.filter(
        status="Resolved"
    ).count()
    jobs_in_progress = assigned_qs.filter(
        status="In Progress"
    ).count()
    jobs_pending = assigned_qs.filter(
        status="Pending"
    ).count()

    verified_completed = assigned_qs.filter(
        status="Resolved",
        otp_verified=True,
    ).count()

    verified_rate = (
        round(
            (verified_completed / jobs_completed) * 100
        )
        if jobs_completed
        else 0
    )

    rating_qs = Rating.objects.filter(
        complaint__assigned_worker=worker,
        rating_type="user_to_worker",
    )

    worker_rating_data = rating_qs.aggregate(
        average=Avg("stars"),
        total=Count("id"),
    )

    worker_average_rating = (
        worker_rating_data["average"]
        or 0
    )
    worker_rating_count = (
        worker_rating_data["total"]
        or 0
    )

    recent_reviews = list(
        rating_qs
        .select_related(
            "rater",
            "complaint",
        )
        .order_by("-created_at")[:4]
    )

    # -----------------------------------------------------
    # League / achievements
    # -----------------------------------------------------
    worker_league = _find_worker_row(
        worker,
        monthly=False,
    )

    all_achievement_cards = _worker_achievement_cards(
        worker_league
    )

    unlocked_achievements = [
        item
        for item in all_achievement_cards
        if item["unlocked"]
    ]

    # -----------------------------------------------------
    # Social stats
    # -----------------------------------------------------
    followers_count = WorkerFollow.objects.filter(
        worker=worker
    ).count()

    following_count = WorkerFollow.objects.filter(
        follower=worker.user
    ).count()

    profile_likes_count = WorkerProfileLike.objects.filter(
        worker=worker
    ).count()

    is_following = False
    is_profile_liked = False
    can_interact = False

    if request.user.is_authenticated:

        can_interact = (
            request.user.pk != worker.user_id
            and not request.user.is_staff
            and not request.user.is_superuser
        )

        if can_interact:
            is_following = WorkerFollow.objects.filter(
                follower=request.user,
                worker=worker,
            ).exists()

            is_profile_liked = WorkerProfileLike.objects.filter(
                user=request.user,
                worker=worker,
            ).exists()

    # -----------------------------------------------------
    # People You May Know - owner view
    # -----------------------------------------------------
    suggestions = []

    if is_owner:

        followed_worker_ids = set(
            WorkerFollow.objects.filter(
                follower=worker.user
            ).values_list(
                "worker_id",
                flat=True,
            )
        )

        candidates = list(
            WorkerProfile.objects
            .select_related("user")
            .filter(
                is_approved=True
            )
            .exclude(
                id=worker.id
            )
            .exclude(
                id__in=followed_worker_ids
            )
        )

        worker_city = (
            worker.city
            or ""
        ).strip().lower()

        worker_skill = (
            worker.skill_category
            or ""
        ).strip().lower()

        candidates.sort(
            key=lambda item: (
                0
                if (
                    worker_city
                    and (item.city or "").strip().lower()
                    == worker_city
                )
                else 1,
                0
                if (
                    worker_skill
                    and (item.skill_category or "").strip().lower()
                    == worker_skill
                )
                else 1,
                (item.name or item.user.username).lower(),
            )
        )

        league_map = {
            row["worker"].pk: row
            for row in _worker_rows(monthly=False)
        }

        for item in candidates[:5]:
            suggestions.append(
                {
                    "worker": item,
                    "league": league_map.get(
                        item.pk,
                        {
                            "level": _league_level(0),
                            "xp": 0,
                            "resolved": 0,
                            "rating_avg": 0,
                        },
                    ),
                }
            )

    # -----------------------------------------------------
    # Recent activity from real complaint status history
    # -----------------------------------------------------
    recent_activity = []

    histories = (
        ComplaintStatusHistory.objects
        .filter(
            complaint__assigned_worker=worker
        )
        .select_related("complaint")
        .order_by("-changed_at")[:8]
    )

    for history in histories:

        if history.new_status == "Resolved":
            title = "Completed a job"
            icon = "check"
        elif history.new_status == "In Progress":
            title = "Started working on a job"
            icon = "clock"
        else:
            title = "New job activity"
            icon = "briefcase"

        recent_activity.append(
            {
                "title": title,
                "detail": history.complaint.subject,
                "date": history.changed_at,
                "icon": icon,
            }
        )

        if len(recent_activity) >= 4:
            break

    return render(
        request,
        "complaints/Worker_Folder/worker_profile.html",
        {
            "worker": worker,
            "is_owner": is_owner,
            "experience_choices":
                WorkerProfile.EXPERIENCE_CHOICES,

            "worker_average_rating":
                worker_average_rating,
            "worker_rating_count":
                worker_rating_count,

            "jobs_assigned": jobs_assigned,
            "jobs_completed": jobs_completed,
            "jobs_in_progress": jobs_in_progress,
            "jobs_pending": jobs_pending,
            "verified_completed":
                verified_completed,
            "verified_rate":
                verified_rate,

            "worker_league":
                worker_league,
            "unlocked_achievements":
                unlocked_achievements[:4],
            "unlocked_achievement_count":
                len(unlocked_achievements),

            "followers_count":
                followers_count,
            "following_count":
                following_count,
            "profile_likes_count":
                profile_likes_count,
            "is_following":
                is_following,
            "is_profile_liked":
                is_profile_liked,
            "can_interact":
                can_interact,

            "suggestions":
                suggestions,
            "recent_activity":
                recent_activity,
            "recent_reviews":
                recent_reviews,
        },
    )


@login_required(login_url="login")
@require_POST
def toggle_worker_follow(request, worker_id):

    worker = get_object_or_404(
        WorkerProfile,
        id=worker_id,
        is_approved=True,
    )

    if request.user.pk == worker.user_id:
        messages.info(
            request,
            "You cannot follow your own worker profile.",
        )
        return redirect(
            "worker_profile",
            worker_id=worker.id,
        )

    follow, created = WorkerFollow.objects.get_or_create(
        follower=request.user,
        worker=worker,
    )

    if created:
        messages.success(
            request,
            f"You are now following {worker.name}.",
        )
    else:
        follow.delete()
        messages.info(
            request,
            f"You unfollowed {worker.name}.",
        )

    next_worker_id = request.POST.get(
        "next_worker_id",
        "",
    ).strip()

    if next_worker_id.isdigit():
        return redirect(
            "worker_profile",
            worker_id=int(next_worker_id),
        )

    return redirect(
        "worker_profile",
        worker_id=worker.id,
    )


@login_required(login_url="login")
@require_POST
def toggle_worker_profile_like(request, worker_id):

    worker = get_object_or_404(
        WorkerProfile,
        id=worker_id,
        is_approved=True,
    )

    if request.user.pk == worker.user_id:
        messages.info(
            request,
            "You cannot like your own worker profile.",
        )
        return redirect(
            "worker_profile",
            worker_id=worker.id,
        )

    like, created = WorkerProfileLike.objects.get_or_create(
        user=request.user,
        worker=worker,
    )

    if created:
        messages.success(
            request,
            f"You liked {worker.name}'s profile.",
        )
    else:
        like.delete()
        messages.info(
            request,
            f"You removed your like from {worker.name}'s profile.",
        )

    return redirect(
        "worker_profile",
        worker_id=worker.id,
    )


# =========================================================
# WORKER REGISTER
# =========================================================

def worker_register(request):

    if request.method == 'POST':

        username = request.POST.get(
            'username',
            ''
        ).strip()

        email = request.POST.get(
            'email',
            ''
        ).strip()

        phone = request.POST.get(
            'phone',
            ''
        ).strip()

        name = request.POST.get(
            'name',
            ''
        ).strip()

        experience = request.POST.get(
            'experience',
            ''
        ).strip()

        skill_category = request.POST.get(
            'skill_category',
            ''
        ).strip()

        city = request.POST.get(
            'city',
            ''
        ).strip()

        area = request.POST.get(
            'area',
            ''
        ).strip()

        pincode = request.POST.get(
            'pincode',
            ''
        ).strip()

        aadhaar_number = request.POST.get(
            'aadhaar_number',
            ''
        ).replace(' ', '').strip()

        password = request.POST.get(
            'password',
            ''
        )

        declaration = request.POST.get(
            'verification_declaration',
            ''
        ).strip()

        profile_photo = request.FILES.get(
            'photo'
        )

        aadhaar_front_photo = request.FILES.get(
            'aadhaar_front_photo'
        )

        aadhaar_back_photo = request.FILES.get(
            'aadhaar_back_photo'
        )

        required_text_fields = [
            username,
            email,
            phone,
            name,
            experience,
            skill_category,
            city,
            area,
            pincode,
            aadhaar_number,
            password,
        ]

        if not all(required_text_fields):

            messages.error(
                request,
                'Please fill all worker registration fields.'
            )

            return redirect(
                'worker_register'
            )

        if declaration != 'yes':

            messages.error(
                request,
                'Please confirm that your verification information is genuine.'
            )

            return redirect(
                'worker_register'
            )

        if (
            not profile_photo
            or not aadhaar_front_photo
            or not aadhaar_back_photo
        ):

            messages.error(
                request,
                'Profile photo and both Aadhaar proof images are required.'
            )

            return redirect(
                'worker_register'
            )

        if User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                'Username already exists.'
            )

            return redirect(
                'worker_register'
            )

        if User.objects.filter(
            email=email
        ).exists():

            messages.error(
                request,
                'This email is already registered.'
            )

            return redirect(
                'worker_register'
            )

        valid_experience = [
            choice[0]
            for choice
            in WorkerProfile.EXPERIENCE_CHOICES
        ]

        if experience not in valid_experience:

            messages.error(
                request,
                'Please select valid experience.'
            )

            return redirect(
                'worker_register'
            )

        valid_skills = [
            choice[0]
            for choice
            in WorkerProfile.SKILL_CHOICES
        ]

        if skill_category not in valid_skills:

            messages.error(
                request,
                'Please select a valid skill category.'
            )

            return redirect(
                'worker_register'
            )

        if (
            not aadhaar_number.isdigit()
            or len(aadhaar_number) != 12
        ):

            messages.error(
                request,
                'Please enter a valid 12-digit Aadhaar number.'
            )

            return redirect(
                'worker_register'
            )

        if (
            not pincode.isdigit()
            or len(pincode) != 6
        ):

            messages.error(
                request,
                'Please enter a valid 6-digit pincode.'
            )

            return redirect(
                'worker_register'
            )

        phone_digits = ''.join(
            character
            for character in phone
            if character.isdigit()
        )

        if len(phone_digits) < 10 or len(phone_digits) > 15:

            messages.error(
                request,
                'Please enter a valid mobile number.'
            )

            return redirect(
                'worker_register'
            )

        if len(password) < 6:

            messages.error(
                request,
                'Password must be at least 6 characters.'
            )

            return redirect(
                'worker_register'
            )

        allowed_image_types = [
            'image/jpeg',
            'image/png',
            'image/webp',
        ]

        verification_images = [
            (
                profile_photo,
                'Profile photo',
            ),
            (
                aadhaar_front_photo,
                'Aadhaar front photo',
            ),
            (
                aadhaar_back_photo,
                'Aadhaar back photo',
            ),
        ]

        for image_file, image_label in verification_images:

            if image_file.content_type not in allowed_image_types:

                messages.error(
                    request,
                    f'{image_label} must be JPG, PNG or WEBP.'
                )

                return redirect(
                    'worker_register'
                )

            if image_file.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    f'{image_label} must be less than 5 MB.'
                )

                return redirect(
                    'worker_register'
                )

        try:

            with transaction.atomic():

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )

                WorkerProfile.objects.create(
                    user=user,
                    name=name,
                    phone=phone,
                    experience=experience,
                    skill_category=skill_category,
                    photo=profile_photo,
                    city=city,
                    area=area,
                    pincode=pincode,
                    aadhaar_last4=aadhaar_number[-4:],
                    aadhaar_front_photo=aadhaar_front_photo,
                    aadhaar_back_photo=aadhaar_back_photo,
                    verification_status='Pending',
                    is_approved=False,
                    probation_completed=False,
                )

        except Exception as error:

            print(
                'WORKER REGISTRATION ERROR:',
                error
            )

            messages.error(
                request,
                'Unable to create worker registration. Please try again.'
            )

            return redirect(
                'worker_register'
            )

        messages.success(
            request,
            (
                'Worker registration submitted successfully. '
                'Your Aadhaar proof and worker details are now pending admin verification. '
                'You can login only after approval.'
            )
        )

        return redirect(
            'worker_login'
        )

    return render(
        request,
        'complaints/Worker_Folder/worker_register.html',
        {
            'experience_choices':
                WorkerProfile.EXPERIENCE_CHOICES,

            'skill_choices':
                WorkerProfile.SKILL_CHOICES,
        }
    )


# =========================================================
# WORKER LOGIN
# =========================================================

@never_cache
@ensure_csrf_cookie
def worker_login(request):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    if request.user.is_authenticated:

        try:

            worker = (
                request.user.worker_profile
            )

            if worker.is_approved:

                return redirect(
                    'worker_dashboard'
                )

        except WorkerProfile.DoesNotExist:
            pass

    if request.method == 'POST':

        username = request.POST.get(
            'username',
            ''
        ).strip()

        password = request.POST.get(
            'password',
            ''
        )

        if not username or not password:

            messages.error(
                request,
                'Please enter username and password.'
            )

            return redirect(
                'worker_login'
            )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:

            messages.error(
                request,
                'Invalid worker username or password.'
            )

            return redirect(
                'worker_login'
            )

        if user.is_staff or user.is_superuser:
            login(
                request,
                user
            )
            return redirect('/admin/')

        try:

            worker = (
                user.worker_profile
            )

        except WorkerProfile.DoesNotExist:

            messages.error(
                request,
                'This account is not a worker account.'
            )

            return redirect(
                'worker_login'
            )

        if not worker.is_approved:

            if worker.verification_status == 'Pending':

                messages.info(
                    request,
                    (
                        'Your worker registration is still under verification. '
                        'You can login after admin approval.'
                    )
                )

            elif worker.verification_status == 'Rejected':

                messages.error(
                    request,
                    (
                        'Your worker verification was rejected. '
                        'Please contact support or the administrator for details.'
                    )
                )

            elif worker.verification_status == 'Suspended':

                messages.error(
                    request,
                    (
                        'Your worker account is suspended. '
                        'Please contact the administrator.'
                    )
                )

            else:

                messages.error(
                    request,
                    'Your worker account is not approved yet.'
                )

            return redirect(
                'worker_login'
            )

        login(
            request,
            user
        )
        request.session['smart_complaint_role'] = 'worker'

        return redirect(
            'worker_dashboard'
        )

    return render(
        request,
        'complaints/Worker_Folder/worker_login.html'
    )




# =========================================================
# LOCAL-ONLY WORKER PRO TEST CONTROLS
# =========================================================

@login_required(login_url='worker_login')
@require_POST
def activate_local_test_worker_pro(request):
    """
    Activate Worker Pro without Razorpay ONLY on local development.

    This endpoint refuses to run unless:
    - DEBUG=True
    - LOCAL_WORKER_PRO_TEST_ENABLED=True
    - host is localhost / 127.0.0.1
    """

    if not _local_worker_pro_test_allowed(
        request
    ):
        return HttpResponse(
            "Local Worker Pro test activation is disabled.",
            status=403,
        )

    try:
        worker = request.user.worker_profile

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Approved worker access is required.'
        )

        return redirect(
            'worker_login'
        )

    with transaction.atomic():

        subscription, created = (
            WorkerSubscription.objects
            .select_for_update()
            .get_or_create(
                worker=worker
            )
        )

        now = timezone.now()
        period_end = (
            now
            + timedelta(days=30)
        )

        subscription.status = 'active'

        if not subscription.started_at:
            subscription.started_at = now

        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.next_billing_at = period_end
        subscription.cancelled_at = None
        subscription.cancel_at_period_end = False
        subscription.last_gateway_status = 'local_test'
        subscription.last_synced_at = now

        subscription.save(
            update_fields=[
                'status',
                'started_at',
                'current_period_start',
                'current_period_end',
                'next_billing_at',
                'cancelled_at',
                'cancel_at_period_end',
                'last_gateway_status',
                'last_synced_at',
                'updated_at',
            ]
        )

    messages.success(
        request,
        (
            'Local test Worker Pro activated for 30 days. '
            'No Razorpay payment or subscription was created.'
        )
    )

    return redirect(
        'worker_dashboard'
    )


@login_required(login_url='worker_login')
@require_POST
def reset_local_test_worker_pro(request):
    """
    Return the local worker account to Free Worker mode.

    Protected by the same local-development safety checks.
    """

    if not _local_worker_pro_test_allowed(
        request
    ):
        return HttpResponse(
            "Local Worker Pro test reset is disabled.",
            status=403,
        )

    try:
        worker = request.user.worker_profile

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Approved worker access is required.'
        )

        return redirect(
            'worker_login'
        )

    with transaction.atomic():

        subscription, created = (
            WorkerSubscription.objects
            .select_for_update()
            .get_or_create(
                worker=worker
            )
        )

        subscription.status = 'inactive'
        subscription.current_period_start = None
        subscription.current_period_end = None
        subscription.next_billing_at = None
        subscription.cancelled_at = None
        subscription.cancel_at_period_end = False
        subscription.last_gateway_status = 'local_test_reset'
        subscription.last_synced_at = timezone.now()

        subscription.save(
            update_fields=[
                'status',
                'current_period_start',
                'current_period_end',
                'next_billing_at',
                'cancelled_at',
                'cancel_at_period_end',
                'last_gateway_status',
                'last_synced_at',
                'updated_at',
            ]
        )

    messages.success(
        request,
        'Local test Worker Pro reset. This worker is back on the Free Worker plan.'
    )

    return redirect(
        'worker_dashboard'
    )


# =========================================================
# WORKER DASHBOARD
# =========================================================

@login_required(login_url='worker_login')
def worker_dashboard(request):

    try:
        worker = request.user.worker_profile

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        logout(request)

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        logout(request)

        return redirect(
            'worker_login'
        )

    # =====================================================
    # ONE-COMPLAINT WORKFLOW
    # =====================================================
    # A worker sees and works on one full complaint at a time.
    # 1. Keep an already In Progress complaint as the current job.
    # 2. Otherwise promote the most important Pending complaint.
    # 3. Remaining active complaints stay in the waiting queue.

    def get_current_worker_job():
        in_progress_job = (
            Complaint.objects
            .filter(
                assigned_worker=worker,
                status='In Progress',
            )
            .select_related(
                'user',
                'user__user_profile',
            )
            .order_by(
                'created_at',
                'id',
            )
            .first()
        )

        if in_progress_job:
            return in_progress_job

        return (
            Complaint.objects
            .filter(
                assigned_worker=worker,
                status='Pending',
            )
            .select_related(
                'user',
                'user__user_profile',
            )
            .annotate(
                priority_rank=Case(
                    When(priority='Emergency', then=Value(0)),
                    When(priority='High', then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by(
                'priority_rank',
                'created_at',
                'id',
            )
            .first()
        )

    if request.method == 'POST':

        action = request.POST.get(
            'action',
            'status_update'
        ).strip()

        complaint_id = request.POST.get(
            'complaint_id',
            ''
        ).strip()

        if not complaint_id:

            messages.error(
                request,
                'Complaint not found.'
            )

            return redirect(
                'worker_dashboard'
            )

        # =====================================================
        # HANDOVER A WAITING COMPLAINT
        # =====================================================
        # Only a Pending complaint that is waiting behind the current
        # job can be handed over. In-progress work is never silently moved.

        if action == 'handover_complaint':

            target_worker_id = request.POST.get(
                'target_worker_id',
                ''
            ).strip()

            handover_reason = request.POST.get(
                'handover_reason',
                ''
            ).strip()

            if len(handover_reason) > 200:
                handover_reason = handover_reason[:200]

            if not target_worker_id:

                messages.error(
                    request,
                    'Please select a worker for handover.'
                )

                return redirect(
                    'worker_dashboard'
                )

            try:
                with transaction.atomic():

                    complaint = (
                        Complaint.objects
                        .select_for_update()
                        .select_related(
                            'user',
                            'assigned_worker',
                        )
                        .get(
                            id=complaint_id,
                            assigned_worker=worker,
                        )
                    )

                    current_job = get_current_worker_job()

                    if (
                        current_job
                        and complaint.id == current_job.id
                    ):

                        messages.error(
                            request,
                            (
                                'The current complaint cannot be handed over from '
                                'the waiting queue. Finish it first or keep working on it.'
                            )
                        )

                        return redirect(
                            'worker_dashboard'
                        )

                    if complaint.status != 'Pending':

                        messages.error(
                            request,
                            'Only a waiting Pending complaint can be handed over.'
                        )

                        return redirect(
                            'worker_dashboard'
                        )

                    target_worker = (
                        WorkerProfile.objects
                        .select_for_update()
                        .get(
                            id=target_worker_id,
                            is_approved=True,
                            verification_status='Approved',
                            availability_status='available',
                        )
                    )

                    if target_worker.id == worker.id:

                        messages.error(
                            request,
                            'Please choose a different worker.'
                        )

                        return redirect(
                            'worker_dashboard'
                        )

                    target_has_active_job = (
                        Complaint.objects
                        .filter(
                            assigned_worker=target_worker,
                            status__in=[
                                'Pending',
                                'In Progress',
                            ],
                        )
                        .exists()
                    )

                    if target_has_active_job:

                        messages.error(
                            request,
                            (
                                f'{target_worker.name} already has an active complaint. '
                                'Choose another available worker.'
                            )
                        )

                        return redirect(
                            'worker_dashboard'
                        )

                    source_worker_name = worker.name
                    target_worker_name = target_worker.name

                    complaint.assigned_worker = target_worker
                    complaint.completion_otp = ''
                    complaint.otp_created_at = None
                    complaint.otp_verified = False

                    complaint.save(
                        update_fields=[
                            'assigned_worker',
                            'completion_otp',
                            'otp_created_at',
                            'otp_verified',
                            'updated_at',
                        ]
                    )

                    target_message = (
                        f'Complaint {complaint.tracking_id} was handed over to you '
                        f'by {source_worker_name}. Priority: {complaint.priority}.'
                    )

                    if handover_reason:
                        target_message += (
                            f' Reason: {handover_reason}'
                        )

                    Notification.objects.create(
                        recipient=target_worker.user,
                        complaint=complaint,
                        notification_type='assignment',
                        title='Complaint Handover',
                        message=target_message,
                    )

                    user_message = (
                        f'Your complaint {complaint.tracking_id} was handed over '
                        f'from {source_worker_name} to {target_worker_name}. '
                        'The complaint remains Pending and no completion was recorded.'
                    )

                    if handover_reason:
                        user_message += (
                            f' Handover note: {handover_reason}'
                        )

                    Notification.objects.create(
                        recipient=complaint.user,
                        complaint=complaint,
                        notification_type='status_update',
                        title='Assigned Worker Changed',
                        message=user_message,
                    )

                try:
                    send_push_to_user(
                        target_worker.user,
                        'Complaint Handover',
                        target_message,
                        data={
                            'type': 'assignment',
                            'complaint_id': str(complaint.id),
                            'tracking_id': complaint.tracking_id,
                        },
                    )
                except Exception as error:
                    print(
                        'Handover worker push failed:',
                        error,
                    )

                try:
                    send_push_to_user(
                        complaint.user,
                        'Assigned Worker Changed',
                        user_message,
                        data={
                            'type': 'status_update',
                            'complaint_id': str(complaint.id),
                            'tracking_id': complaint.tracking_id,
                        },
                    )
                except Exception as error:
                    print(
                        'Handover user push failed:',
                        error,
                    )

                messages.success(
                    request,
                    (
                        f'Complaint {complaint.tracking_id} handed over to '
                        f'{target_worker_name} successfully.'
                    )
                )

                return redirect(
                    'worker_dashboard'
                )

            except (
                Complaint.DoesNotExist,
                WorkerProfile.DoesNotExist,
                ValueError,
                TypeError,
            ):

                messages.error(
                    request,
                    'The complaint or selected worker is no longer available.'
                )

                return redirect(
                    'worker_dashboard'
                )

        # =====================================================
        # ALL NORMAL WORK ACTIONS MUST TARGET CURRENT JOB
        # =====================================================

        try:
            complaint = Complaint.objects.get(
                id=complaint_id,
                assigned_worker=worker
            )

        except (
            Complaint.DoesNotExist,
            ValueError,
            TypeError
        ):

            messages.error(
                request,
                'You cannot update this complaint.'
            )

            return redirect(
                'worker_dashboard'
            )

        current_job = get_current_worker_job()

        if (
            not current_job
            or complaint.id != current_job.id
        ):

            messages.error(
                request,
                (
                    'Please finish the current complaint first. '
                    'Waiting complaints cannot be worked on out of order.'
                )
            )

            return redirect(
                'worker_dashboard'
            )

        # =====================================================
        # UPLOAD / REPLACE AFTER PHOTO
        # =====================================================

        if action == 'upload_after_photo':

            if complaint.status == 'Resolved':

                messages.error(
                    request,
                    'Resolved complaint photo cannot be changed.'
                )

                return redirect(
                    'worker_dashboard'
                )

            after_photo = request.FILES.get(
                'after_photo'
            )

            if not after_photo:

                messages.error(
                    request,
                    'Please select an after photo.'
                )

                return redirect(
                    'worker_dashboard'
                )

            allowed_types = [
                'image/jpeg',
                'image/png',
                'image/webp',
            ]

            if after_photo.content_type not in allowed_types:

                messages.error(
                    request,
                    'Only JPG, PNG or WEBP images are allowed.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if after_photo.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    'After photo must be less than 5 MB.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if complaint.after_photo:

                old_photo = complaint.after_photo.name

                if (
                    old_photo
                    and default_storage.exists(old_photo)
                ):
                    default_storage.delete(old_photo)

            complaint.after_photo = after_photo
            complaint.after_photo_uploaded_at = timezone.now()

            complaint.save(
                update_fields=[
                    'after_photo',
                    'after_photo_uploaded_at',
                    'updated_at',
                ]
            )

            messages.success(
                request,
                'After photo uploaded successfully.'
            )

            return redirect(
                'worker_dashboard'
            )

        # =====================================================
        # VERIFY COMPLETION OTP
        # =====================================================

        if action == 'verify_otp':

            entered_otp = request.POST.get(
                'completion_otp',
                ''
            ).strip()

            if complaint.status == 'Resolved':

                messages.info(
                    request,
                    'This complaint is already resolved.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if not complaint.after_photo:

                messages.error(
                    request,
                    'Please upload the After Photo before resolving the complaint.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if not entered_otp:

                messages.error(
                    request,
                    'Please enter the completion OTP.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if (
                not complaint.completion_otp
                or not complaint.otp_created_at
            ):

                messages.error(
                    request,
                    'No active completion OTP found. Select Resolved first to generate a new OTP.'
                )

                return redirect(
                    'worker_dashboard'
                )

            otp_expiry_time = (
                complaint.otp_created_at
                + timedelta(minutes=10)
            )

            if timezone.now() > otp_expiry_time:

                complaint.completion_otp = ''
                complaint.otp_created_at = None
                complaint.otp_verified = False

                complaint.save(
                    update_fields=[
                        'completion_otp',
                        'otp_created_at',
                        'otp_verified',
                        'updated_at',
                    ]
                )

                messages.error(
                    request,
                    'OTP expired. Select Resolved again to generate a new OTP.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if entered_otp != complaint.completion_otp:

                messages.error(
                    request,
                    'Incorrect completion OTP.'
                )

                return redirect(
                    'worker_dashboard'
                )

            complaint.otp_verified = True
            complaint.completion_otp = ''
            complaint.status = 'Resolved'
            complaint.save()

            resolved_count = (
                Complaint.objects
                .filter(
                    assigned_worker=worker,
                    status='Resolved'
                )
                .count()
            )

            if (
                not worker.probation_completed
                and resolved_count >= worker.probation_target
            ):

                worker.probation_completed = True

                worker.save(
                    update_fields=[
                        'probation_completed',
                    ]
                )

            Notification.objects.create(
                recipient=complaint.user,
                complaint=complaint,
                notification_type='status_update',
                title='Complaint Resolved',
                message=(
                    f'Your complaint {complaint.tracking_id} '
                    f'has been successfully resolved.'
                ),
            )

            send_push_to_user(
                complaint.user,
                'Complaint Resolved',
                (
                    f'Your complaint {complaint.tracking_id} '
                    f'has been successfully resolved.'
                )
            )

            messages.success(
                request,
                (
                    f'OTP verified successfully. '
                    f'Complaint {complaint.tracking_id} '
                    f'is now Resolved. The next waiting complaint is now available.'
                )
            )

            return redirect(
                'worker_dashboard'
            )

        # =====================================================
        # STATUS UPDATE
        # =====================================================

        if action == 'status_update':

            new_status = request.POST.get(
                'status',
                ''
            ).strip()

            valid_statuses = [
                'Pending',
                'In Progress',
                'Resolved',
            ]

            if new_status not in valid_statuses:

                messages.error(
                    request,
                    'Invalid complaint status.'
                )

                return redirect(
                    'worker_dashboard'
                )

            if complaint.status == new_status:

                messages.info(
                    request,
                    f'Complaint is already {new_status}.'
                )

                return redirect(
                    'worker_dashboard'
                )

            # =================================================
            # RESOLVED REQUIRES AFTER PHOTO + USER OTP
            # =================================================

            if new_status == 'Resolved':

                if not complaint.after_photo:

                    messages.error(
                        request,
                        'Please upload the After Photo before selecting Resolved.'
                    )

                    return redirect(
                        'worker_dashboard'
                    )

                otp_is_active = False

                if (
                    complaint.completion_otp
                    and complaint.otp_created_at
                    and not complaint.otp_verified
                ):

                    otp_expiry_time = (
                        complaint.otp_created_at
                        + timedelta(minutes=10)
                    )

                    if timezone.now() <= otp_expiry_time:
                        otp_is_active = True

                if not otp_is_active:

                    complaint.completion_otp = str(
                        100000
                        + secrets.randbelow(900000)
                    )

                    complaint.otp_created_at = timezone.now()
                    complaint.otp_verified = False

                    complaint.save(
                        update_fields=[
                            'completion_otp',
                            'otp_created_at',
                            'otp_verified',
                            'updated_at',
                        ]
                    )

                    otp_message = (
                        f'Completion OTP for complaint '
                        f'{complaint.tracking_id}: '
                        f'{complaint.completion_otp}. '
                        f'This OTP is valid for 10 minutes. '
                        f'Share it only with the assigned worker after the work is completed.'
                    )

                    Notification.objects.create(
                        recipient=complaint.user,
                        complaint=complaint,
                        notification_type='otp',
                        title='Completion OTP Ready',
                        message=otp_message,
                    )

                    send_push_to_user(
                        complaint.user,
                        'Completion OTP Ready',
                        otp_message,
                        data={
                            'type': 'completion_otp',
                            'complaint_id': str(complaint.id),
                            'tracking_id': complaint.tracking_id,
                        },
                    )

                messages.info(
                    request,
                    (
                        'Completion OTP is ready. '
                        'Ask the user for the OTP and enter it on the dashboard. '
                        'The OTP is valid for 10 minutes.'
                    )
                )

                return redirect(
                    'worker_dashboard'
                )

            # =================================================
            # PENDING / IN PROGRESS
            # =================================================

            complaint.status = new_status
            complaint.completion_otp = ''
            complaint.otp_created_at = None
            complaint.otp_verified = False
            complaint.save()

            Notification.objects.create(
                recipient=complaint.user,
                complaint=complaint,
                notification_type='status_update',
                title='Complaint Status Updated',
                message=(
                    f'Your complaint {complaint.tracking_id} '
                    f'status is now {new_status}.'
                ),
            )

            send_push_to_user(
                complaint.user,
                'Complaint Status Updated',
                (
                    f'Your complaint {complaint.tracking_id} '
                    f'status is now {new_status}.'
                )
            )

            messages.success(
                request,
                (
                    f'Complaint {complaint.tracking_id} '
                    f'status updated to {new_status}.'
                )
            )

            return redirect(
                'worker_dashboard'
            )

        messages.error(
            request,
            'Invalid action.'
        )

        return redirect(
            'worker_dashboard'
        )

    # =====================================================
    # DASHBOARD DATA
    # =====================================================

    assigned_complaints = (
        Complaint.objects
        .filter(
            assigned_worker=worker
        )
    )

    total_assigned_count = assigned_complaints.count()

    active_count = (
        assigned_complaints
        .filter(
            status__in=[
                'Pending',
                'In Progress',
            ]
        )
        .count()
    )

    in_progress_count = (
        assigned_complaints
        .filter(
            status='In Progress'
        )
        .count()
    )

    resolved_count = (
        assigned_complaints
        .filter(
            status='Resolved'
        )
        .count()
    )

    current_complaint = get_current_worker_job()

    complaints = (
        [current_complaint]
        if current_complaint
        else []
    )

    queued_count = max(
        active_count - (1 if current_complaint else 0),
        0,
    )

    waiting_complaint = None

    if current_complaint:

        waiting_complaint = (
            Complaint.objects
            .filter(
                assigned_worker=worker,
                status__in=[
                    'Pending',
                    'In Progress',
                ],
            )
            .exclude(
                id=current_complaint.id
            )
            .select_related(
                'user',
                'user__user_profile',
            )
            .annotate(
                waiting_status_rank=Case(
                    When(status='Pending', then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
                priority_rank=Case(
                    When(priority='Emergency', then=Value(0)),
                    When(priority='High', then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
            )
            .order_by(
                'waiting_status_rank',
                'priority_rank',
                'created_at',
                'id',
            )
            .first()
        )

    # Only show workers who are approved, marked available, and currently
    # have no Pending/In Progress complaint. Same-skill workers are listed first.
    handover_workers = []

    if (
        waiting_complaint
        and waiting_complaint.status == 'Pending'
    ):

        handover_workers = list(
            WorkerProfile.objects
            .filter(
                is_approved=True,
                verification_status='Approved',
                availability_status='available',
            )
            .exclude(
                id=worker.id
            )
            .annotate(
                active_job_count=Count(
                    'assigned_complaints',
                    filter=Q(
                        assigned_complaints__status__in=[
                            'Pending',
                            'In Progress',
                        ]
                    ),
                ),
                skill_match_rank=Case(
                    When(
                        skill_category=worker.skill_category,
                        then=Value(0),
                    ),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
            )
            .filter(
                active_job_count=0
            )
            .order_by(
                'skill_match_rank',
                'name',
                'id',
            )
        )

    complaint_ids = [
        complaint.id
        for complaint in complaints
    ]

    ratings = (
        Rating.objects
        .filter(
            complaint_id__in=complaint_ids,
            rating_type='worker_to_user'
        )
    )

    rating_map = {
        rating.complaint_id: rating
        for rating in ratings
    }

    now = timezone.now()

    for complaint in complaints:

        complaint.worker_rating = (
            rating_map.get(
                complaint.id
            )
        )

        complaint.otp_active = False

        if (
            complaint.completion_otp
            and complaint.otp_created_at
            and not complaint.otp_verified
        ):

            otp_expiry_time = (
                complaint.otp_created_at
                + timedelta(minutes=10)
            )

            complaint.otp_active = (
                now <= otp_expiry_time
            )

    # A resolved complaint disappears from the active work card immediately,
    # so keep a small feedback prompt for the most recent unresolved rating.
    recent_resolved_unrated = (
        Complaint.objects
        .filter(
            assigned_worker=worker,
            status='Resolved',
        )
        .exclude(
            ratings__rating_type='worker_to_user'
        )
        .select_related(
            'user',
        )
        .order_by(
            '-updated_at',
            '-id',
        )
        .first()
    )

    worker_subscription, created = (
        WorkerSubscription.objects
        .get_or_create(
            worker=worker
        )
    )

    return render(
        request,
        'complaints/Worker_Folder/worker_dashboard.html',
        {
            'worker': worker,
            'complaints': complaints,
            'current_complaint': current_complaint,
            'waiting_complaint': waiting_complaint,
            'queued_count': queued_count,
            'active_count': active_count,
            'in_progress_count': in_progress_count,
            'resolved_count': resolved_count,
            'total_assigned_count': total_assigned_count,
            'handover_workers': handover_workers,
            'recent_resolved_unrated': recent_resolved_unrated,
            'league': _worker_league_snapshot(worker),
            'public_worker_rows': _worker_rows(monthly=True),
            'public_user_rows': _user_rows(monthly=True),
            'worker_subscription': worker_subscription,
            'local_worker_pro_test_allowed':
                _local_worker_pro_test_allowed(
                    request
                ),
        }
    )


# =========================================================
# WORKER SETTINGS
# =========================================================

@login_required(login_url='worker_login')
def worker_settings(request):

    try:

        worker = (
            request.user.worker_profile
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        return redirect(
            'worker_login'
        )

    subscription, created = (
        WorkerSubscription.objects.get_or_create(
            worker=worker
        )
    )

    payout_details, payout_created = (
        WorkerPayoutDetails.objects.get_or_create(
            worker=worker
        )
    )

    if request.method == 'POST':

        action = request.POST.get(
            'action',
            ''
        ).strip()

        if action == 'save_availability':

            availability_status = request.POST.get(
                'availability_status',
                ''
            ).strip().lower()

            valid_availability_statuses = {
                choice[0]
                for choice in WorkerProfile.AVAILABILITY_STATUS_CHOICES
            }

            if availability_status not in valid_availability_statuses:

                messages.error(
                    request,
                    'Please select a valid availability status.'
                )

                return redirect(
                    'worker_settings'
                )

            worker.availability_status = availability_status
            worker.save(
                update_fields=[
                    'availability_status',
                ]
            )

            messages.success(
                request,
                f'Availability updated to {worker.get_availability_status_display()}.'
            )

            return redirect(
                'worker_settings'
            )

        if action == 'save_payout_details':

            payout_method = request.POST.get(
                'payout_method',
                ''
            ).strip().lower()

            if payout_method not in {
                'upi',
                'bank',
            }:

                messages.error(
                    request,
                    'Please select a valid payout method.'
                )

                return redirect(
                    'worker_settings'
                )

            if payout_method == 'upi':

                upi_id = request.POST.get(
                    'upi_id',
                    ''
                ).strip()

                upi_pattern = re.compile(
                    r'^[A-Za-z0-9._-]{2,100}@[A-Za-z0-9.-]{2,50}$'
                )

                if not upi_id:

                    messages.error(
                        request,
                        'Please enter your UPI ID.'
                    )

                    return redirect(
                        'worker_settings'
                    )

                if not upi_pattern.fullmatch(
                    upi_id
                ):

                    messages.error(
                        request,
                        'Please enter a valid UPI ID.'
                    )

                    return redirect(
                        'worker_settings'
                    )

                payout_details.payout_method = (
                    'upi'
                )

                payout_details.upi_id = (
                    upi_id
                )

                payout_details.account_holder_name = (
                    ''
                )

                payout_details.bank_name = (
                    ''
                )

                payout_details.bank_account_last4 = (
                    ''
                )

                payout_details.ifsc_code = (
                    ''
                )

                payout_details.is_verified = (
                    False
                )

                payout_details.save()

                messages.success(
                    request,
                    'UPI payout details saved successfully.'
                )

                return redirect(
                    'worker_settings'
                )

            account_holder_name = (
                request.POST.get(
                    'account_holder_name',
                    ''
                ).strip()
            )

            bank_name = request.POST.get(
                'bank_name',
                ''
            ).strip()

            account_number = request.POST.get(
                'account_number',
                ''
            ).replace(
                ' ',
                ''
            ).strip()

            confirm_account_number = (
                request.POST.get(
                    'confirm_account_number',
                    ''
                )
                .replace(
                    ' ',
                    ''
                )
                .strip()
            )

            ifsc_code = (
                request.POST.get(
                    'ifsc_code',
                    ''
                )
                .strip()
                .upper()
            )

            if (
                not account_holder_name
                or not bank_name
                or not account_number
                or not confirm_account_number
                or not ifsc_code
            ):

                messages.error(
                    request,
                    'Please fill all bank payout fields.'
                )

                return redirect(
                    'worker_settings'
                )

            if not account_number.isdigit():

                messages.error(
                    request,
                    'Bank account number must contain digits only.'
                )

                return redirect(
                    'worker_settings'
                )

            if not (
                6 <= len(account_number) <= 18
            ):

                messages.error(
                    request,
                    'Bank account number must be between 6 and 18 digits.'
                )

                return redirect(
                    'worker_settings'
                )

            if (
                account_number
                != confirm_account_number
            ):

                messages.error(
                    request,
                    'Bank account numbers do not match.'
                )

                return redirect(
                    'worker_settings'
                )

            ifsc_pattern = re.compile(
                r'^[A-Z]{4}0[A-Z0-9]{6}$'
            )

            if not ifsc_pattern.fullmatch(
                ifsc_code
            ):

                messages.error(
                    request,
                    'Please enter a valid 11-character IFSC code.'
                )

                return redirect(
                    'worker_settings'
                )

            payout_details.payout_method = (
                'bank'
            )

            payout_details.upi_id = (
                ''
            )

            payout_details.account_holder_name = (
                account_holder_name
            )

            payout_details.bank_name = (
                bank_name
            )

            payout_details.bank_account_last4 = (
                account_number[-4:]
            )

            payout_details.ifsc_code = (
                ifsc_code
            )

            payout_details.is_verified = (
                False
            )

            payout_details.save()

            messages.success(
                request,
                (
                    'Bank payout details saved successfully. '
                    'For security, only the last 4 account digits are stored.'
                )
            )

            return redirect(
                'worker_settings'
            )

    return render(
        request,
        'complaints/Worker_Folder/worker_settings.html',
        {
            'worker': worker,
            'subscription': subscription,
            'payout_details': payout_details,
            'worker_is_premium': subscription.is_premium_active,
        }
    )


# =========================================================
# WORKER DELETE ACCOUNT
# =========================================================

@login_required(login_url='worker_login')
@require_POST
def worker_delete_account(request):

    try:
        worker = request.user.worker_profile

    except WorkerProfile.DoesNotExist:
        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    password = request.POST.get(
        'password',
        ''
    )

    confirmation = request.POST.get(
        'confirmation',
        ''
    ).strip()

    if not password:
        messages.error(
            request,
            'Please enter your current password.'
        )

        return redirect(
            'worker_settings'
        )

    if not request.user.check_password(
        password
    ):
        messages.error(
            request,
            'Current password is incorrect.'
        )

        return redirect(
            'worker_settings'
        )

    if confirmation != 'DELETE':
        messages.error(
            request,
            'Type DELETE exactly to confirm account deletion.'
        )

        return redirect(
            'worker_settings'
        )

    subscription = (
        WorkerSubscription.objects
        .filter(worker=worker)
        .first()
    )

    if (
        subscription
        and subscription.razorpay_subscription_id
        and subscription.status in {'active', 'pending'}
    ):
        if (
            not settings.RAZORPAY_KEY_ID
            or not settings.RAZORPAY_KEY_SECRET
        ):
            messages.error(
                request,
                (
                    'Your subscription is still active. '
                    'Please cancel the subscription before deleting your account.'
                )
            )

            return redirect(
                'worker_settings'
            )

        try:
            client = razorpay.Client(
                auth=(
                    settings.RAZORPAY_KEY_ID,
                    settings.RAZORPAY_KEY_SECRET,
                )
            )

            client.subscription.cancel(
                subscription.razorpay_subscription_id
            )

        except Exception:
            messages.error(
                request,
                (
                    'We could not cancel your active subscription. '
                    'Your account was not deleted. Please try again.'
                )
            )

            return redirect(
                'worker_settings'
            )

    user = request.user
    storage_files = set()

    for image_field in (
        worker.photo,
        worker.aadhaar_front_photo,
        worker.aadhaar_back_photo,
    ):
        if image_field:
            storage_files.add(
                image_field.name
            )

    sent_chat_messages = (
        ChatMessage.objects
        .filter(sender=user)
    )

    for chat_message in sent_chat_messages:
        if chat_message.image:
            storage_files.add(
                chat_message.image.name
            )

    try:
        with transaction.atomic():
            user.delete()

    except Exception:
        messages.error(
            request,
            'Worker account could not be deleted. Please try again.'
        )

        return redirect(
            'worker_settings'
        )

    for file_name in storage_files:
        try:
            if file_name and default_storage.exists(file_name):
                default_storage.delete(file_name)
        except Exception:
            pass

    logout(
        request
    )

    messages.success(
        request,
        'Your worker account has been permanently deleted.'
    )

    return redirect(
        'worker_login'
    )


# =========================================================
# WORKER CHANGE PASSWORD
# =========================================================

@login_required(login_url='worker_login')
@require_POST
def worker_change_password(request):

    try:

        worker = (
            request.user.worker_profile
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        return redirect(
            'worker_login'
        )

    current_password = request.POST.get(
        'current_password',
        ''
    )

    new_password = request.POST.get(
        'new_password',
        ''
    )

    confirm_password = request.POST.get(
        'confirm_password',
        ''
    )

    if (
        not current_password
        or not new_password
        or not confirm_password
    ):

        messages.error(
            request,
            'Please fill all password fields.'
        )

        return redirect(
            'worker_settings'
        )

    if not request.user.check_password(
        current_password
    ):

        messages.error(
            request,
            'Current password is incorrect.'
        )

        return redirect(
            'worker_settings'
        )

    if new_password != confirm_password:

        messages.error(
            request,
            'New password and confirm password do not match.'
        )

        return redirect(
            'worker_settings'
        )

    if len(new_password) < 6:

        messages.error(
            request,
            'New password must be at least 6 characters.'
        )

        return redirect(
            'worker_settings'
        )

    if current_password == new_password:

        messages.error(
            request,
            'New password must be different from your current password.'
        )

        return redirect(
            'worker_settings'
        )

    request.user.set_password(
        new_password
    )

    request.user.save(
        update_fields=[
            'password',
        ]
    )

    update_session_auth_hash(
        request,
        request.user
    )

    messages.success(
        request,
        'Password changed successfully.'
    )

    return redirect(
        'worker_settings'
    )


# =========================================================
# WORKER APP TERMS & CONDITIONS - READ ONLY
# =========================================================

@login_required(login_url='worker_login')
def worker_app_terms(request):

    try:

        worker = (
            request.user.worker_profile
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        return redirect(
            'worker_login'
        )

    return render(
        request,
        'complaints/Worker_Folder/app_terms_conditions.html',
        {
            'worker': worker,
        }
    )


# =========================================================
# WORKER SUBSCRIPTION TERMS & CONDITIONS
# =========================================================

@login_required(login_url='worker_login')
def terms_conditions(request):

    try:

        worker = (
            request.user.worker_profile
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        return redirect(
            'worker_login'
        )

    subscription, created = (
        WorkerSubscription.objects.get_or_create(
            worker=worker
        )
    )

    if request.method == 'POST':

        agree = request.POST.get(
            'agree_terms'
        )

        if agree != 'yes':

            messages.error(
                request,
                'Please accept the Terms & Conditions.'
            )

            return redirect(
                'terms_conditions'
            )

        subscription.terms_accepted = True
        subscription.terms_accepted_at = (
            timezone.now()
        )

        subscription.terms_version = '2.0'

        if subscription.status == 'inactive':

            subscription.status = (
                'pending'
            )

        subscription.save()

        return redirect(
            'worker_subscription_payment'
        )

    return render(
        request,
        'complaints/Worker_Folder/terms_conditions.html',
        {
            'worker': worker,
            'subscription': subscription,
        }
    )


# =========================================================
# WORKER SUBSCRIPTION HELPERS
# =========================================================

WORKER_PRO_PLAN_DEFINITIONS = {
    'monthly': {
        'code': 'monthly',
        'name': 'Worker Pro Monthly',
        'short_name': 'Monthly',
        'upfront_price': 49,
        'renewal_price': 149,
        'reference_price': None,
        'saving': None,
        'interval_months': 1,
        'billing_label': 'month',
        'renewal_copy': '₹149 every month after the introductory first month',
        'ai_credits': 150,
        'env_key': 'RAZORPAY_WORKER_PLAN_ID',
        'total_count': 12,
    },
    'four_month': {
        'code': 'four_month',
        'name': 'Worker Pro 4 Months',
        'short_name': '4 Months',
        'upfront_price': 589,
        'renewal_price': 589,
        'reference_price': 596,
        'saving': 7,
        'interval_months': 4,
        'billing_label': '4 months',
        'renewal_copy': '₹589 every 4 months',
        'ai_credits': 155,
        'env_key': 'RAZORPAY_WORKER_PLAN_4M_ID',
        'total_count': 6,
    },
    'yearly': {
        'code': 'yearly',
        'name': 'Worker Pro Yearly',
        'short_name': '1 Year',
        'upfront_price': 1769,
        'renewal_price': 1769,
        'reference_price': 1788,
        'saving': 19,
        'interval_months': 12,
        'billing_label': 'year',
        'renewal_copy': '₹1769 every 12 months',
        'ai_credits': 160,
        'env_key': 'RAZORPAY_WORKER_PLAN_YEARLY_ID',
        'total_count': 5,
    },
}


def _setting_or_env(name):
    return (
        getattr(settings, name, '')
        or os.environ.get(name, '')
    ).strip()


def _worker_subscription_config():
    plans = {}

    for code, definition in WORKER_PRO_PLAN_DEFINITIONS.items():
        plan = dict(definition)
        plan['plan_id'] = _setting_or_env(
            definition['env_key']
        )
        plan['configured'] = bool(plan['plan_id'])
        plans[code] = plan

    return {
        'key_id': _setting_or_env('RAZORPAY_KEY_ID'),
        'key_secret': _setting_or_env('RAZORPAY_KEY_SECRET'),
        'webhook_secret': _setting_or_env('RAZORPAY_WEBHOOK_SECRET'),
        'plans': plans,
    }


def _add_calendar_months(dt, months):
    local_dt = timezone.localtime(dt)
    month_index = (local_dt.month - 1) + int(months)
    year = local_dt.year + (month_index // 12)
    month = (month_index % 12) + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(local_dt.day, last_day)

    return local_dt.replace(
        year=year,
        month=month,
        day=day,
    )


def _razorpay_timestamp_to_datetime(value):
    """Convert a Razorpay Unix timestamp to a timezone-aware datetime."""
    if value in (None, ''):
        return None

    try:
        return timezone.datetime.fromtimestamp(
            int(value),
            tz=timezone.get_current_timezone(),
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _plan_code_from_gateway_plan_id(plan_id):
    if not plan_id:
        return None

    config = _worker_subscription_config()

    for code, plan in config['plans'].items():
        if plan['plan_id'] and plan['plan_id'] == plan_id:
            return code

    return None


def _sync_worker_subscription_from_razorpay(
    subscription,
    razorpay_subscription,
):
    """
    Synchronise local entitlement with Razorpay's verified state.

    Razorpay remains the source of truth for the gateway state.
    Local cancel_at_period_end preserves already-paid access until
    current_period_end after the worker disables future renewal.
    """

    razorpay_status = str(
        razorpay_subscription.get('status', '')
    ).strip().lower()

    subscription.last_gateway_status = razorpay_status
    subscription.last_synced_at = timezone.now()

    customer_id = razorpay_subscription.get('customer_id') or ''
    plan_id = razorpay_subscription.get('plan_id') or ''

    if customer_id:
        subscription.razorpay_customer_id = customer_id

    if plan_id:
        subscription.razorpay_plan_id = plan_id
        detected_plan_code = _plan_code_from_gateway_plan_id(plan_id)
        if detected_plan_code:
            subscription.plan_code = detected_plan_code

    now = timezone.now()

    current_start = _razorpay_timestamp_to_datetime(
        razorpay_subscription.get('current_start')
    )
    current_end = _razorpay_timestamp_to_datetime(
        razorpay_subscription.get('current_end')
    )
    charge_at = _razorpay_timestamp_to_datetime(
        razorpay_subscription.get('charge_at')
    )

    if current_start:
        subscription.current_period_start = current_start

    if current_end:
        subscription.current_period_end = current_end

    if charge_at:
        subscription.next_billing_at = charge_at

    if razorpay_status in {'authenticated', 'active'}:
        subscription.status = 'active'

        if not subscription.started_at:
            subscription.started_at = now

        if not subscription.current_period_start:
            subscription.current_period_start = subscription.started_at

        if (
            not subscription.current_period_end
            and subscription.next_billing_at
        ):
            subscription.current_period_end = subscription.next_billing_at

        if not subscription.cancel_at_period_end:
            subscription.cancelled_at = None

    elif razorpay_status in {'created', 'pending', 'halted', 'paused'}:
        subscription.status = 'pending'

    elif razorpay_status == 'cancelled':
        if (
            subscription.cancel_at_period_end
            and subscription.current_period_end
            and subscription.current_period_end > now
        ):
            subscription.status = 'active'
            subscription.next_billing_at = None
        else:
            subscription.status = 'cancelled'

        if not subscription.cancelled_at:
            subscription.cancelled_at = now

    elif razorpay_status in {'completed', 'expired'}:
        subscription.status = 'expired'
        subscription.next_billing_at = None

    if (
        subscription.cancel_at_period_end
        and subscription.current_period_end
        and subscription.current_period_end <= now
    ):
        subscription.status = 'cancelled'
        subscription.next_billing_at = None

    subscription.save()


def _fetch_and_sync_worker_subscription(subscription):
    config = _worker_subscription_config()

    if (
        not config['key_id']
        or not config['key_secret']
        or not subscription.razorpay_subscription_id
    ):
        return None

    client = razorpay.Client(
        auth=(config['key_id'], config['key_secret'])
    )

    gateway_subscription = client.subscription.fetch(
        subscription.razorpay_subscription_id
    )

    _sync_worker_subscription_from_razorpay(
        subscription,
        gateway_subscription,
    )

    return gateway_subscription


def _worker_plan_template_rows(config):
    rows = []
    for code in ('monthly', 'four_month', 'yearly'):
        rows.append(dict(config['plans'][code]))
    return rows


# =========================================================
# WORKER SUBSCRIPTION PAYMENT - THREE AUTOPAY PLANS
# =========================================================

@login_required(login_url='worker_login')
def worker_subscription_payment(request):

    try:
        worker = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        messages.error(request, 'Worker access required.')
        return redirect('worker_login')

    if not worker.is_approved:
        messages.error(request, 'Your worker account is not approved.')
        return redirect('worker_login')

    subscription, created = WorkerSubscription.objects.get_or_create(
        worker=worker
    )

    if not subscription.terms_accepted:
        messages.error(
            request,
            'Please accept the Terms & Conditions first.'
        )
        return redirect('terms_conditions')

    config = _worker_subscription_config()
    gateway_sync_error = ''

    if (
        subscription.razorpay_subscription_id
        and config['key_id']
        and config['key_secret']
    ):
        try:
            _fetch_and_sync_worker_subscription(subscription)
        except Exception as error:
            print('RAZORPAY SUBSCRIPTION SYNC ERROR:', error)
            gateway_sync_error = (
                'Live subscription status could not be refreshed right now.'
            )

    if request.method == 'POST':

        if subscription.is_premium_active:
            messages.info(
                request,
                'Worker Pro is already active for this account.'
            )
            return redirect('worker_subscription_payment')

        if subscription.terms_version != '2.0':
            messages.info(
                request,
                'Please review the updated multi-plan subscription terms.'
            )
            return redirect('terms_conditions')

        selected_code = (
            request.POST.get('plan_code', '')
            .strip()
            .lower()
        )

        selected_plan = config['plans'].get(selected_code)

        if not selected_plan:
            messages.error(request, 'Please select a valid Worker Pro plan.')
            return redirect('worker_subscription_payment')

        if (
            not config['key_id']
            or not config['key_secret']
            or not selected_plan['plan_id']
        ):
            messages.error(
                request,
                f"{selected_plan['name']} payment configuration is incomplete."
            )
            return redirect('worker_subscription_payment')

        try:
            client = razorpay.Client(
                auth=(config['key_id'], config['key_secret'])
            )

            if subscription.razorpay_subscription_id:
                try:
                    existing = client.subscription.fetch(
                        subscription.razorpay_subscription_id
                    )
                    _sync_worker_subscription_from_razorpay(
                        subscription,
                        existing,
                    )

                    existing_status = str(
                        existing.get('status', '')
                    ).lower()
                    existing_plan_id = str(
                        existing.get('plan_id', '')
                    ).strip()
                    short_url = existing.get('short_url') or ''

                    if existing_status in {'authenticated', 'active'}:
                        messages.success(request, 'Worker Pro is active.')
                        return redirect('worker_subscription_payment')

                    same_plan = (
                        existing_plan_id == selected_plan['plan_id']
                    )

                    if (
                        existing_status in {'created', 'pending', 'halted'}
                        and same_plan
                        and short_url
                    ):
                        return redirect(short_url)

                    if (
                        existing_status in {'created', 'pending', 'halted'}
                        and not same_plan
                    ):
                        # No paid entitlement exists yet. Cancel the abandoned
                        # pending link before creating the newly selected plan.
                        client.subscription.cancel(
                            subscription.razorpay_subscription_id
                        )
                        subscription.razorpay_subscription_id = ''
                        subscription.razorpay_plan_id = ''
                        subscription.last_gateway_status = 'cancelled'
                        subscription.save(
                            update_fields=[
                                'razorpay_subscription_id',
                                'razorpay_plan_id',
                                'last_gateway_status',
                                'updated_at',
                            ]
                        )

                except Exception as error:
                    print('RAZORPAY EXISTING SUBSCRIPTION ERROR:', error)
                    messages.error(
                        request,
                        (
                            'Your existing Razorpay subscription could not be '
                            'verified right now. No new subscription was created.'
                        )
                    )
                    return redirect('worker_subscription_payment')

            now = timezone.now()
            first_regular_billing_date = _add_calendar_months(
                now,
                selected_plan['interval_months'],
            )

            gateway_subscription = client.subscription.create(
                {
                    'plan_id': selected_plan['plan_id'],
                    'total_count': selected_plan['total_count'],
                    'quantity': 1,
                    'customer_notify': True,
                    'start_at': int(first_regular_billing_date.timestamp()),
                    'addons': [
                        {
                            'item': {
                                'name': (
                                    f"{selected_plan['name']} first paid period"
                                ),
                                'amount': selected_plan['upfront_price'] * 100,
                                'currency': 'INR',
                            }
                        }
                    ],
                    'notes': {
                        'worker_id': str(worker.id),
                        'worker_name': worker.name,
                        'django_user_id': str(request.user.id),
                        'subscription_type': 'worker_pro',
                        'plan_code': selected_code,
                        'upfront_price_inr': str(
                            selected_plan['upfront_price']
                        ),
                        'renewal_price_inr': str(
                            selected_plan['renewal_price']
                        ),
                        'billing_interval_months': str(
                            selected_plan['interval_months']
                        ),
                        'ai_credits_per_30_days': str(
                            selected_plan['ai_credits']
                        ),
                    },
                }
            )

            subscription_id = str(
                gateway_subscription.get('id', '')
            ).strip()
            short_url = str(
                gateway_subscription.get('short_url', '')
            ).strip()

            if not subscription_id:
                messages.error(
                    request,
                    'Razorpay did not return a subscription ID.'
                )
                return redirect('worker_subscription_payment')

            subscription.plan_code = selected_code
            subscription.razorpay_subscription_id = subscription_id
            subscription.razorpay_plan_id = selected_plan['plan_id']
            subscription.first_month_price = selected_plan['upfront_price']
            subscription.monthly_price = selected_plan['renewal_price']
            subscription.status = 'pending'
            subscription.started_at = None
            subscription.current_period_start = None
            subscription.current_period_end = None
            subscription.next_billing_at = first_regular_billing_date
            subscription.cancelled_at = None
            subscription.cancel_at_period_end = False
            subscription.last_gateway_status = str(
                gateway_subscription.get('status', 'created')
            ).lower()
            subscription.last_synced_at = timezone.now()
            subscription.save()

            if short_url:
                return redirect(short_url)

            messages.error(
                request,
                (
                    'Subscription was created, but Razorpay did not return '
                    'a payment link. Refresh status before trying again.'
                )
            )
            return redirect('worker_subscription_payment')

        except razorpay.errors.BadRequestError as error:
            print('RAZORPAY BAD REQUEST ERROR:', error)
            messages.error(
                request,
                (
                    'Razorpay rejected the Worker Pro request. '
                    'No Worker Pro access was activated.'
                )
            )
        except razorpay.errors.ServerError as error:
            print('RAZORPAY SERVER ERROR:', error)
            messages.error(
                request,
                'Razorpay is temporarily unavailable. Please try again later.'
            )
        except Exception as error:
            print('RAZORPAY GENERAL ERROR:', error)
            messages.error(
                request,
                'Unable to start Worker Pro payment. No access was activated.'
            )

        return redirect('worker_subscription_payment')

    current_plan = config['plans'].get(
        subscription.plan_code,
        config['plans']['monthly'],
    )

    return render(
        request,
        'complaints/Worker_Folder/worker_subscription_payment.html',
        {
            'worker': worker,
            'subscription': subscription,
            'worker_pro_plans': _worker_plan_template_rows(config),
            'current_plan': current_plan,
            'gateway_sync_error': gateway_sync_error,
            'worker_pro_gateway_configured': bool(
                config['key_id'] and config['key_secret']
            ),
            'webhook_configured': bool(config['webhook_secret']),
        }
    )


@login_required(login_url='worker_login')
@require_POST
def worker_subscription_sync(request):
    try:
        worker = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        messages.error(request, 'Worker access required.')
        return redirect('worker_login')

    if not worker.is_approved:
        messages.error(request, 'Approved worker access is required.')
        return redirect('worker_login')

    subscription, created = WorkerSubscription.objects.get_or_create(
        worker=worker
    )

    if not subscription.razorpay_subscription_id:
        messages.info(
            request,
            'No Razorpay Worker Pro subscription exists yet.'
        )
        return redirect('worker_subscription_payment')

    try:
        _fetch_and_sync_worker_subscription(subscription)
        messages.success(
            request,
            'Worker Pro status refreshed securely from Razorpay.'
        )
    except Exception as error:
        print('WORKER SUBSCRIPTION MANUAL SYNC ERROR:', error)
        messages.error(
            request,
            'Could not refresh the Razorpay subscription right now.'
        )

    return redirect('worker_subscription_payment')


@login_required(login_url='worker_login')
@require_POST
def worker_subscription_cancel_renewal(request):
    """Turn off future recurring renewal while preserving paid access."""

    try:
        worker = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        messages.error(request, 'Worker access required.')
        return redirect('worker_login')

    if not worker.is_approved:
        messages.error(request, 'Approved worker access is required.')
        return redirect('worker_login')

    subscription, created = WorkerSubscription.objects.get_or_create(
        worker=worker
    )

    if not subscription.razorpay_subscription_id:
        messages.error(
            request,
            'No Razorpay Worker Pro subscription is available to cancel.'
        )
        return redirect('worker_subscription_payment')

    if subscription.cancel_at_period_end:
        messages.info(request, 'Automatic renewal is already turned off.')
        return redirect('worker_subscription_payment')

    confirm = request.POST.get('confirm_cancel', '').strip().lower()
    if confirm != 'yes':
        messages.error(request, 'Cancellation confirmation was not received.')
        return redirect('worker_subscription_payment')

    config = _worker_subscription_config()
    if not config['key_id'] or not config['key_secret']:
        messages.error(request, 'Razorpay configuration is incomplete.')
        return redirect('worker_subscription_payment')

    try:
        client = razorpay.Client(
            auth=(config['key_id'], config['key_secret'])
        )
        gateway_subscription = client.subscription.cancel(
            subscription.razorpay_subscription_id,
            {'cancel_at_cycle_end': True},
        )

        subscription.cancel_at_period_end = True
        subscription.cancelled_at = timezone.now()

        gateway_current_end = _razorpay_timestamp_to_datetime(
            gateway_subscription.get('current_end')
        )
        if gateway_current_end:
            subscription.current_period_end = gateway_current_end

        subscription.next_billing_at = None
        subscription.last_gateway_status = str(
            gateway_subscription.get(
                'status',
                subscription.last_gateway_status,
            )
        ).lower()
        subscription.last_synced_at = timezone.now()

        if (
            subscription.current_period_end
            and subscription.current_period_end > timezone.now()
        ):
            subscription.status = 'active'
        else:
            subscription.status = 'cancelled'

        subscription.save()

        messages.success(
            request,
            (
                'Automatic renewal is turned off. Your already-paid '
                'Worker Pro access remains available until the current '
                'billing period ends.'
            )
        )

    except razorpay.errors.BadRequestError as error:
        print('RAZORPAY CANCEL BAD REQUEST:', error)
        messages.error(
            request,
            (
                'Razorpay could not schedule the cancellation. '
                'Your subscription was not changed.'
            )
        )
    except Exception as error:
        print('RAZORPAY CANCEL ERROR:', error)
        messages.error(
            request,
            (
                'Unable to turn off renewal right now. '
                'Your subscription was not changed.'
            )
        )

    return redirect('worker_subscription_payment')


# =========================================================
# RAZORPAY WORKER SUBSCRIPTION WEBHOOK
# =========================================================

@csrf_exempt
@require_POST
def worker_subscription_webhook(request):
    config = _worker_subscription_config()

    webhook_secret = config['webhook_secret']
    razorpay_key_id = config['key_id']
    razorpay_key_secret = config['key_secret']

    if (
        not webhook_secret
        or not razorpay_key_id
        or not razorpay_key_secret
    ):
        print('RAZORPAY WEBHOOK ERROR: webhook configuration is missing.')
        return HttpResponse(status=503)

    signature = request.headers.get('X-Razorpay-Signature', '')

    if not signature:
        return HttpResponse(status=400)

    raw_body = request.body

    try:
        client = razorpay.Client(
            auth=(razorpay_key_id, razorpay_key_secret)
        )

        client.utility.verify_webhook_signature(
            raw_body.decode('utf-8'),
            signature,
            webhook_secret,
        )

    except Exception as error:
        print('RAZORPAY WEBHOOK SIGNATURE ERROR:', error)
        return HttpResponse(status=400)

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponse(status=400)

    event = payload.get('event', '')
    event_payload = payload.get('payload', {})

    razorpay_subscription = (
        event_payload
        .get('subscription', {})
        .get('entity', {})
    )

    razorpay_subscription_id = razorpay_subscription.get('id', '')

    # Payment events can contain the subscription id inside the payment
    # entity instead of a subscription entity.
    if not razorpay_subscription_id:
        payment_entity = (
            event_payload
            .get('payment', {})
            .get('entity', {})
        )
        razorpay_subscription_id = payment_entity.get(
            'subscription_id',
            ''
        )

    if not razorpay_subscription_id:
        return HttpResponse(status=200)

    subscription = (
        WorkerSubscription.objects
        .filter(
            razorpay_subscription_id=razorpay_subscription_id
        )
        .first()
    )

    if not subscription:
        return HttpResponse(status=200)

    try:
        # Fetching from Razorpay after signature verification means our local
        # status is based on Razorpay's current server-side subscription state.
        verified_subscription = client.subscription.fetch(
            razorpay_subscription_id
        )

        _sync_worker_subscription_from_razorpay(
            subscription,
            verified_subscription,
        )

        print(
            'RAZORPAY WORKER SUBSCRIPTION WEBHOOK:',
            event,
            razorpay_subscription_id,
            verified_subscription.get('status', ''),
        )

    except Exception as error:
        print('RAZORPAY WEBHOOK SYNC ERROR:', error)
        return HttpResponse(status=500)

    return HttpResponse(status=200)


# =========================================================
# WORKER -> USER RATING
# =========================================================

@login_required(login_url='worker_login')
def rate_user(request, complaint_id):

    if request.method != 'POST':

        return redirect(
            'worker_dashboard'
        )

    try:

        worker = (
            request.user.worker_profile
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        return redirect(
            'worker_login'
        )

    try:

        complaint = (
            Complaint.objects
            .select_related(
                'user'
            )
            .get(
                id=complaint_id,
                assigned_worker=worker
            )
        )

    except Complaint.DoesNotExist:

        messages.error(
            request,
            'Complaint not found.'
        )

        return redirect(
            'worker_dashboard'
        )

    if complaint.status != 'Resolved':

        messages.error(
            request,
            'You can rate the user only after the complaint is resolved.'
        )

        return redirect(
            'worker_dashboard'
        )

    if Rating.objects.filter(
        complaint=complaint,
        rating_type='worker_to_user'
    ).exists():

        messages.info(
            request,
            'You have already rated this user for this complaint.'
        )

        return redirect(
            'worker_dashboard'
        )

    stars = request.POST.get(
        'stars',
        ''
    ).strip()

    problem = request.POST.get(
        'problem',
        ''
    ).strip()

    try:

        stars = int(
            stars
        )

    except (
        ValueError,
        TypeError
    ):

        messages.error(
            request,
            'Please select a star rating.'
        )

        return redirect(
            'worker_dashboard'
        )

    if stars < 1 or stars > 5:

        messages.error(
            request,
            'Rating must be between 1 and 5 stars.'
        )

        return redirect(
            'worker_dashboard'
        )

    if len(problem) > 1000:

        messages.error(
            request,
            'Problem / feedback must be less than 1000 characters.'
        )

        return redirect(
            'worker_dashboard'
        )

    Rating.objects.create(
        complaint=complaint,
        rater=request.user,
        rating_type='worker_to_user',
        stars=stars,
        problem=problem,
    )

    messages.success(
        request,
        'User rating submitted successfully.'
    )

    return redirect(
        'worker_dashboard'
    )


# =========================================================
# WORKER LOGOUT
# =========================================================

def worker_logout(request):

    logout(
        request
    )

    return redirect(
        'worker_login'
    )


# =========================================================
# SAVE FIREBASE DEVICE TOKEN
# USER + WORKER
# =========================================================

@login_required(login_url='login')
@require_POST
def save_device_token(request):

    token = request.POST.get(
        'token',
        ''
    ).strip()

    if not token:

        return JsonResponse(
            {
                'success': False,
                'message': 'FCM token is required.',
            },
            status=400,
        )

    try:

        request.user.worker_profile
        role = 'worker'

    except WorkerProfile.DoesNotExist:

        role = 'user'

    DeviceToken.objects.update_or_create(
        token=token,
        defaults={
            'user': request.user,
            'role': role,
            'is_active': True,
        },
    )

    return JsonResponse(
        {
            'success': True,
            'role': role,
        }
    )


# =========================================================
# RAZORPAY TEST ORDER - BACKEND CONNECTIVITY TEST
# =========================================================

@login_required(login_url='login')
@require_POST
def create_test_payment_order(request):
    """
    Create a fixed ₹1 Razorpay Test Mode order.

    This endpoint is intentionally limited to a fixed server-side amount.
    It verifies that Django can securely talk to Razorpay without trusting
    an amount supplied by the browser or Android WebView.
    """

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    razorpay_key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    razorpay_key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

    if not razorpay_key_id or not razorpay_key_secret:
        return JsonResponse(
            {
                'success': False,
                'message': 'Razorpay configuration is missing.',
            },
            status=503,
        )

    amount_rupees = 1
    amount_paise = amount_rupees * 100

    payment = PaymentTransaction.objects.create(
        payer=request.user,
        payment_for='other',
        amount=amount_rupees,
        currency='INR',
        status='created',
        description='Razorpay Test Mode connectivity order',
    )

    receipt = f'sc_test_{payment.id}'
    payment.receipt = receipt
    payment.save(update_fields=['receipt', 'updated_at'])

    try:
        client = razorpay.Client(
            auth=(razorpay_key_id, razorpay_key_secret)
        )

        razorpay_order = client.order.create(
            {
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': receipt,
                'notes': {
                    'payment_transaction_id': str(payment.id),
                    'purpose': 'Smart Complaint test payment',
                },
            }
        )

        razorpay_order_id = razorpay_order.get('id', '')

        if not razorpay_order_id:
            payment.status = 'failed'
            payment.failed_at = timezone.now()
            payment.save(
                update_fields=[
                    'status',
                    'failed_at',
                    'updated_at',
                ]
            )

            return JsonResponse(
                {
                    'success': False,
                    'message': 'Razorpay did not return an order ID.',
                },
                status=502,
            )

        payment.razorpay_order_id = razorpay_order_id
        payment.status = 'pending'
        payment.save(
            update_fields=[
                'razorpay_order_id',
                'status',
                'updated_at',
            ]
        )

        return JsonResponse(
            {
                'success': True,
                'key_id': razorpay_key_id,
                'order_id': razorpay_order_id,
                'amount': amount_paise,
                'currency': 'INR',
                'transaction_id': payment.id,
            }
        )

    except razorpay.errors.BadRequestError as error:
        payment.status = 'failed'
        payment.failed_at = timezone.now()
        payment.save(
            update_fields=[
                'status',
                'failed_at',
                'updated_at',
            ]
        )
        print('RAZORPAY TEST ORDER BAD REQUEST:', error)

        return JsonResponse(
            {
                'success': False,
                'message': 'Razorpay rejected the test order.',
            },
            status=400,
        )

    except razorpay.errors.ServerError as error:
        payment.status = 'failed'
        payment.failed_at = timezone.now()
        payment.save(
            update_fields=[
                'status',
                'failed_at',
                'updated_at',
            ]
        )
        print('RAZORPAY TEST ORDER SERVER ERROR:', error)

        return JsonResponse(
            {
                'success': False,
                'message': 'Razorpay is temporarily unavailable.',
            },
            status=502,
        )

    except Exception as error:
        payment.status = 'failed'
        payment.failed_at = timezone.now()
        payment.save(
            update_fields=[
                'status',
                'failed_at',
                'updated_at',
            ]
        )
        print('RAZORPAY TEST ORDER ERROR:', error)

        return JsonResponse(
            {
                'success': False,
                'message': 'Unable to create the Razorpay test order.',
            },
            status=500,
        )


# =========================================================
# RAZORPAY PAYMENT VERIFICATION - SERVER SIDE
# =========================================================

@login_required(login_url='login')
@require_POST
def verify_test_payment(request):
    """
    Securely verify a Razorpay Checkout payment on the server.

    A transaction is marked paid only when:
    1. the transaction belongs to the logged-in user,
    2. the submitted Razorpay order ID matches the stored order ID,
    3. Razorpay's payment signature is valid,
    4. the payment really exists at Razorpay,
    5. the provider payment belongs to the same order,
    6. amount and currency match the server-side transaction, and
    7. Razorpay reports the payment as captured.
    """

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    razorpay_key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    razorpay_key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

    if not razorpay_key_id or not razorpay_key_secret:
        return JsonResponse(
            {
                'success': False,
                'message': 'Razorpay configuration is missing.',
            },
            status=503,
        )

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                'success': False,
                'message': 'Invalid payment verification data.',
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {
                'success': False,
                'message': 'Invalid payment verification data.',
            },
            status=400,
        )

    transaction_id = payload.get('transaction_id')
    razorpay_order_id = str(payload.get('razorpay_order_id', '')).strip()
    razorpay_payment_id = str(payload.get('razorpay_payment_id', '')).strip()
    razorpay_signature = str(payload.get('razorpay_signature', '')).strip()

    if (
        not transaction_id
        or not razorpay_order_id
        or not razorpay_payment_id
        or not razorpay_signature
    ):
        return JsonResponse(
            {
                'success': False,
                'message': 'Payment verification data is incomplete.',
            },
            status=400,
        )

    try:
        transaction_id = int(transaction_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {
                'success': False,
                'message': 'Invalid transaction ID.',
            },
            status=400,
        )

    client = razorpay.Client(
        auth=(razorpay_key_id, razorpay_key_secret)
    )

    try:
        with transaction.atomic():
            payment = (
                PaymentTransaction.objects
                .select_for_update()
                .get(
                    id=transaction_id,
                    payer=request.user,
                )
            )

            if payment.status == 'paid':
                if (
                    payment.razorpay_order_id == razorpay_order_id
                    and payment.razorpay_payment_id == razorpay_payment_id
                ):
                    return JsonResponse(
                        {
                            'success': True,
                            'message': 'Payment is already verified.',
                            'transaction_id': payment.id,
                            'status': payment.status,
                        }
                    )

                return JsonResponse(
                    {
                        'success': False,
                        'message': 'This transaction has already been paid.',
                    },
                    status=409,
                )

            if payment.status != 'pending':
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'This transaction is not pending payment.',
                    },
                    status=409,
                )

            if payment.razorpay_order_id != razorpay_order_id:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Razorpay order ID does not match this transaction.',
                    },
                    status=400,
                )

            client.utility.verify_payment_signature(
                {
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature,
                }
            )

            provider_payment = client.payment.fetch(
                razorpay_payment_id
            )

            provider_payment_id = str(
                provider_payment.get('id', '')
            ).strip()

            provider_order_id = str(
                provider_payment.get('order_id', '')
            ).strip()

            provider_currency = str(
                provider_payment.get('currency', '')
            ).strip().upper()

            provider_status = str(
                provider_payment.get('status', '')
            ).strip().lower()

            provider_captured = provider_payment.get(
                'captured',
                False,
            )

            try:
                provider_amount = int(
                    provider_payment.get('amount')
                )
            except (TypeError, ValueError):
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Razorpay returned an invalid payment amount.',
                    },
                    status=502,
                )

            expected_amount = int(
                payment.amount * 100
            )

            expected_currency = str(
                payment.currency
            ).strip().upper()

            if provider_payment_id != razorpay_payment_id:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Razorpay payment ID verification failed.',
                    },
                    status=400,
                )

            if provider_order_id != payment.razorpay_order_id:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Razorpay payment does not belong to this order.',
                    },
                    status=400,
                )

            if provider_amount != expected_amount:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Razorpay payment amount does not match this transaction.',
                    },
                    status=400,
                )

            if provider_currency != expected_currency:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Razorpay payment currency does not match this transaction.',
                    },
                    status=400,
                )

            if (
                provider_status != 'captured'
                or provider_captured is not True
            ):
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Payment has not been captured by Razorpay.',
                    },
                    status=409,
                )

            payment.razorpay_payment_id = razorpay_payment_id
            payment.status = 'paid'
            payment.paid_at = timezone.now()
            payment.failed_at = None
            payment.save(
                update_fields=[
                    'razorpay_payment_id',
                    'status',
                    'paid_at',
                    'failed_at',
                    'updated_at',
                ]
            )

            return JsonResponse(
                {
                    'success': True,
                    'message': 'Payment verified successfully.',
                    'transaction_id': payment.id,
                    'status': payment.status,
                }
            )

    except PaymentTransaction.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'message': 'Payment transaction was not found.',
            },
            status=404,
        )

    except razorpay.errors.SignatureVerificationError:
        return JsonResponse(
            {
                'success': False,
                'message': 'Payment signature verification failed.',
            },
            status=400,
        )

    except razorpay.errors.BadRequestError as error:
        print('RAZORPAY PAYMENT FETCH BAD REQUEST:', error)

        return JsonResponse(
            {
                'success': False,
                'message': 'Razorpay could not verify this payment.',
            },
            status=400,
        )

    except razorpay.errors.ServerError as error:
        print('RAZORPAY PAYMENT FETCH SERVER ERROR:', error)

        return JsonResponse(
            {
                'success': False,
                'message': 'Razorpay is temporarily unavailable.',
            },
            status=502,
        )

    except Exception as error:
        print('RAZORPAY PAYMENT VERIFICATION ERROR:', error)

        return JsonResponse(
            {
                'success': False,
                'message': 'Unable to verify the payment.',
            },
            status=500,
        )


# =========================================================
# PAYMENT DETAILS - UI ONLY
# =========================================================

@login_required(login_url='login')
def user_payment_details(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect
    """Render the user payment details UI. Backend payment data will be connected later."""
    return render(
        request,
        'complaints/User_Folder/user_payment_details.html',
    )


@login_required(login_url='worker_login')
def worker_payment_details(request):
    """Render the worker payment details UI. Backend payout data will be connected later."""
    try:
        worker = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        messages.error(
            request,
            'Worker access required.'
        )
        return redirect('worker_login')

    if not worker.is_approved:
        messages.error(
            request,
            'Your worker account is not approved yet.'
        )
        return redirect('worker_login')

    return render(
        request,
        'complaints/Worker_Folder/worker_payment_details.html',
        {
            'worker': worker,
        },
    )


# =========================================================
# WORKER CHAT INBOX
# =========================================================

@login_required(login_url='worker_login')
def worker_chats(request):

    try:
        worker = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        messages.error(
            request,
            'Worker access required.'
        )
        return redirect('worker_login')

    if not worker.is_approved:
        messages.error(
            request,
            'Your worker account is not approved yet.'
        )
        return redirect('worker_dashboard')

    worker_chat_complaints = (
        Complaint.objects
        .filter(assigned_worker=worker)
        .select_related(
            'user',
            'assigned_worker',
            'assigned_worker__user',
        )
        .order_by('-created_at')
    )

    return render(
        request,
        'complaints/chat.html',
        {
            'chat_inbox': True,
            'worker': worker,
            'worker_chat_complaints': worker_chat_complaints,
        }
    )


# =========================================================
# USER + WORKER COMPLAINT CHAT
# =========================================================

@login_required(login_url='login')
def complaint_chat(request, complaint_id):

    try:

        complaint = (
            Complaint.objects
            .select_related(
                'user',
                'assigned_worker',
                'assigned_worker__user',
            )
            .get(
                id=complaint_id
            )
        )

    except Complaint.DoesNotExist:

        messages.error(
            request,
            'Complaint not found.'
        )

        return redirect(
            'home'
        )

    # =====================================================
    # CHAT PERMISSION
    # =====================================================

    is_complaint_user = (
        complaint.user_id
        == request.user.id
    )

    is_assigned_worker = (
        complaint.assigned_worker
        and
        complaint.assigned_worker.user_id
        == request.user.id
    )

    if (
        not is_complaint_user
        and not is_assigned_worker
    ):

        messages.error(
            request,
            'You do not have permission to open this chat.'
        )

        return redirect(
            'home'
        )

    # =====================================================
    # POST ACTIONS
    # =====================================================

    if request.method == 'POST':

        action = request.POST.get(
            'action',
            'send'
        ).strip()

        # =================================================
        # SEND MESSAGE / IMAGE
        # =================================================

        if action == 'send':

            message_text = request.POST.get(
                'message',
                ''
            ).strip()

            chat_image = request.FILES.get(
                'image'
            )

            if (
                not message_text
                and not chat_image
            ):

                messages.error(
                    request,
                    'Please type a message or select an image.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            if len(message_text) > 2000:

                messages.error(
                    request,
                    'Message cannot be longer than 2000 characters.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            # =================================================
            # IMAGE VALIDATION
            # =================================================

            if chat_image:

                allowed_types = [
                    'image/jpeg',
                    'image/png',
                    'image/webp',
                    'image/gif',
                ]

                if (
                    chat_image.content_type
                    not in allowed_types
                ):

                    messages.error(
                        request,
                        'Only JPG, PNG, WEBP or GIF images are allowed.'
                    )

                    return redirect(
                        'complaint_chat',
                        complaint_id=complaint.id
                    )

                if (
                    chat_image.size
                    > 5 * 1024 * 1024
                ):

                    messages.error(
                        request,
                        'Image size cannot be more than 5 MB.'
                    )

                    return redirect(
                        'complaint_chat',
                        complaint_id=complaint.id
                    )

            ChatMessage.objects.create(
                complaint=complaint,
                sender=request.user,
                message=message_text,
                image=chat_image,
            )

            return redirect(
                'complaint_chat',
                complaint_id=complaint.id
            )

        # =================================================
        # EDIT OWN MESSAGE - ONLY ONE TIME
        # =================================================

        elif action == 'edit':

            message_id = request.POST.get(
                'message_id',
                ''
            ).strip()

            new_message = request.POST.get(
                'message',
                ''
            ).strip()

            try:

                chat_message = (
                    ChatMessage.objects.get(
                        id=message_id,
                        complaint=complaint,
                        sender=request.user,
                    )
                )

            except (
                ChatMessage.DoesNotExist,
                ValueError,
                TypeError
            ):

                messages.error(
                    request,
                    'Message not found.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            if (
                chat_message.edit_count
                >= 1
            ):

                messages.error(
                    request,
                    'This message has already been edited once.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            if not new_message:

                messages.error(
                    request,
                    'Edited message cannot be empty.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            if len(new_message) > 2000:

                messages.error(
                    request,
                    'Message cannot be longer than 2000 characters.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            chat_message.message = (
                new_message
            )

            chat_message.is_edited = True

            chat_message.edit_count += 1

            chat_message.edited_at = (
                timezone.now()
            )

            chat_message.save(
                update_fields=[
                    'message',
                    'is_edited',
                    'edit_count',
                    'edited_at',
                ]
            )

            messages.success(
                request,
                'Message edited successfully.'
            )

            return redirect(
                'complaint_chat',
                complaint_id=complaint.id
            )

        # =================================================
        # DELETE OWN MESSAGE
        # =================================================

        elif action == 'delete':

            message_id = request.POST.get(
                'message_id',
                ''
            ).strip()

            try:

                chat_message = (
                    ChatMessage.objects.get(
                        id=message_id,
                        complaint=complaint,
                        sender=request.user,
                    )
                )

            except (
                ChatMessage.DoesNotExist,
                ValueError,
                TypeError
            ):

                messages.error(
                    request,
                    'Message not found.'
                )

                return redirect(
                    'complaint_chat',
                    complaint_id=complaint.id
                )

            # Image file bhi storage se delete hoga.
            if chat_message.image:

                image_name = (
                    chat_message.image.name
                )

                if (
                    image_name
                    and default_storage.exists(
                        image_name
                    )
                ):

                    default_storage.delete(
                        image_name
                    )

            chat_message.delete()

            messages.success(
                request,
                'Message deleted successfully.'
            )

            return redirect(
                'complaint_chat',
                complaint_id=complaint.id
            )

        # =================================================
        # INVALID ACTION
        # =================================================

        else:

            messages.error(
                request,
                'Invalid chat action.'
            )

            return redirect(
                'complaint_chat',
                complaint_id=complaint.id
            )

    # =====================================================
    # GET CHAT MESSAGES
    # =====================================================

    chat_messages = (
        ChatMessage.objects
        .filter(
            complaint=complaint
        )
        .select_related(
            'sender'
        )
        .order_by(
            'created_at'
        )
    )

    # =====================================================
    # MARK RECEIVED MESSAGES AS READ
    # =====================================================

    ChatMessage.objects.filter(
        complaint=complaint,
        is_read=False,
    ).exclude(
        sender=request.user
    ).update(
        is_read=True
    )

    return render(
        request,
        'complaints/chat.html',
        {
            'complaint': complaint,
            'chat_messages': chat_messages,
            'is_complaint_user':
                is_complaint_user,
            'is_assigned_worker':
                is_assigned_worker,
        }
    )

# =========================================================
# COMMUNITY / WORKER LEAGUE
# =========================================================
# The league is calculated from existing verified app activity.
# No new database table is required, so this feature is safe to
# deploy without an additional migration.

LEAGUE_LEVELS = (
    ("Bronze", 0, 500),
    ("Silver", 500, 1000),
    ("Gold", 1000, 2000),
    ("Platinum", 2000, 3500),
    ("Diamond", 3500, None),
)


# =========================================================
# RESPONSIBLE CITIZEN XP RULES
# =========================================================
# Important:
# - Submitting a complaint gives 0 XP.
# - Raw complaint quantity gives 0 XP.
# - Repeated complaints in the same month cannot be used to
#   continuously farm XP.
# - XP rewards responsible, verified participation instead.
#
# Monthly maximum:
#   Verified participation       = 10 XP
#   Helpful feedback given       = 10 XP
#   Quality report bonus         =  5 XP
#   Positive worker feedback     = 10 XP
#   Responsible-month bonus      = 10 XP
#   ------------------------------------
#   Maximum                      = 45 XP / month
#
# Lifetime XP is the sum of each month's capped score.

USER_XP_VERIFIED_MONTHLY = 10
USER_XP_FEEDBACK_EACH = 5
USER_XP_FEEDBACK_MONTHLY_CAP = 10
USER_XP_QUALITY_REPORT_MONTHLY = 5
USER_XP_POSITIVE_WORKER_RATING_EACH = 5
USER_XP_POSITIVE_WORKER_RATING_MONTHLY_CAP = 10
USER_XP_RESPONSIBLE_MONTH_BONUS = 10

USER_QUALITY_DESCRIPTION_MIN_LENGTH = 40


def _league_level(xp):
    xp = max(int(xp or 0), 0)

    for name, floor, ceiling in LEAGUE_LEVELS:

        if ceiling is None or xp < ceiling:

            next_xp = ceiling

            progress = (
                100
                if ceiling is None
                else int(
                    (
                        (xp - floor)
                        / max(
                            ceiling - floor,
                            1,
                        )
                    )
                    * 100
                )
            )

            return {
                "name": name,
                "floor": floor,
                "next_xp": next_xp,
                "progress": max(
                    0,
                    min(
                        progress,
                        100,
                    ),
                ),
                "xp_left": (
                    0
                    if next_xp is None
                    else max(
                        next_xp - xp,
                        0,
                    )
                ),
            }

    return {
        "name": "Diamond",
        "floor": 3500,
        "next_xp": None,
        "progress": 100,
        "xp_left": 0,
    }


def _month_start():
    now = timezone.localtime(
        timezone.now()
    )

    return now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _month_key(dt):
    local_dt = timezone.localtime(dt)

    return (
        local_dt.year,
        local_dt.month,
    )


def _empty_user_month():
    return {
        "resolved": 0,
        "verified": 0,
        "ratings": 0,
        "detailed": 0,
        "positive_worker_ratings": 0,
    }


def _score_user_month(data):
    """
    Score one calendar month.

    Complaint count itself never earns XP.
    """

    verified_points = (
        USER_XP_VERIFIED_MONTHLY
        if data["verified"] > 0
        else 0
    )

    feedback_points = min(
        data["ratings"]
        * USER_XP_FEEDBACK_EACH,
        USER_XP_FEEDBACK_MONTHLY_CAP,
    )

    quality_points = (
        USER_XP_QUALITY_REPORT_MONTHLY
        if data["detailed"] > 0
        else 0
    )

    positive_worker_rating_points = min(
        data["positive_worker_ratings"]
        * USER_XP_POSITIVE_WORKER_RATING_EACH,
        USER_XP_POSITIVE_WORKER_RATING_MONTHLY_CAP,
    )

    responsible_month = (
        data["verified"] > 0
        and data["ratings"] > 0
        and data["positive_worker_ratings"] > 0
    )

    responsible_bonus = (
        USER_XP_RESPONSIBLE_MONTH_BONUS
        if responsible_month
        else 0
    )

    total = (
        verified_points
        + feedback_points
        + quality_points
        + positive_worker_rating_points
        + responsible_bonus
    )

    return {
        "xp": total,
        "verified_points": verified_points,
        "feedback_points": feedback_points,
        "quality_points": quality_points,
        "positive_worker_rating_points":
            positive_worker_rating_points,
        "responsible_bonus": responsible_bonus,
        "responsible_month": responsible_month,
    }


def _user_participation_summary(user):
    """
    Build monthly responsible-participation buckets for one user.

    Resolution month comes from ComplaintStatusHistory where available.
    Existing/legacy resolved complaints fall back to Complaint.updated_at.
    """

    buckets = {}

    def bucket_for(dt):
        key = _month_key(dt)

        if key not in buckets:
            buckets[key] = _empty_user_month()

        return buckets[key]

    # -----------------------------------------------------
    # Resolved / verified / quality reports
    # -----------------------------------------------------

    resolved_complaints = list(
        Complaint.objects
        .filter(
            user=user,
            status="Resolved",
        )
        .only(
            "id",
            "photo",
            "latitude",
            "longitude",
            "description",
            "otp_verified",
            "updated_at",
        )
    )

    resolution_dates = {}

    histories = (
        ComplaintStatusHistory.objects
        .filter(
            complaint__user=user,
            new_status="Resolved",
        )
        .values(
            "complaint_id",
            "changed_at",
        )
        .order_by(
            "complaint_id",
            "-changed_at",
        )
    )

    for item in histories:

        complaint_id = item["complaint_id"]

        if complaint_id not in resolution_dates:
            resolution_dates[complaint_id] = item["changed_at"]

    for complaint in resolved_complaints:

        resolved_at = (
            resolution_dates.get(
                complaint.id
            )
            or complaint.updated_at
        )

        month = bucket_for(
            resolved_at
        )

        # This count is shown as a stat only.
        # It does NOT add XP by itself.
        month["resolved"] += 1

        if complaint.otp_verified:
            month["verified"] += 1

        description = (
            complaint.description
            or ""
        ).strip()

        is_quality_report = (
            bool(complaint.photo)
            and complaint.latitude is not None
            and complaint.longitude is not None
            and len(description)
            >= USER_QUALITY_DESCRIPTION_MIN_LENGTH
        )

        if is_quality_report:
            month["detailed"] += 1

    # -----------------------------------------------------
    # Helpful feedback GIVEN to workers
    # -----------------------------------------------------

    given_ratings = (
        Rating.objects
        .filter(
            rater=user,
            rating_type="user_to_worker",
            complaint__status="Resolved",
        )
        .only(
            "created_at",
        )
    )

    for rating in given_ratings:
        bucket_for(
            rating.created_at
        )["ratings"] += 1

    # -----------------------------------------------------
    # Positive feedback RECEIVED from workers
    # -----------------------------------------------------
    # A 4- or 5-star worker_to_user rating is treated as a
    # positive trust signal. Users cannot directly award this
    # score to themselves.

    positive_worker_ratings = (
        Rating.objects
        .filter(
            complaint__user=user,
            rating_type="worker_to_user",
            stars__gte=4,
        )
        .only(
            "created_at",
        )
    )

    for rating in positive_worker_ratings:
        bucket_for(
            rating.created_at
        )["positive_worker_ratings"] += 1

    # -----------------------------------------------------
    # Score each month after caps are applied.
    # -----------------------------------------------------

    for data in buckets.values():
        data.update(
            _score_user_month(
                data
            )
        )

    return buckets


def _user_rows(monthly=False):

    current_month_key = _month_key(
        timezone.now()
    )

    users = User.objects.filter(
        worker_profile__isnull=True,
        is_staff=False,
        is_superuser=False,
    )

    rows = []

    for user in users.select_related(
        "user_profile"
    ):

        buckets = _user_participation_summary(
            user
        )

        if monthly:

            selected = buckets.get(
                current_month_key,
                _empty_user_month(),
            ).copy()

            if "xp" not in selected:
                selected.update(
                    _score_user_month(
                        selected
                    )
                )

            xp = selected["xp"]
            resolved_count = selected["resolved"]
            rating_count = selected["ratings"]
            detailed_count = selected["detailed"]
            verified_count = selected["verified"]
            positive_worker_rating_count = (
                selected[
                    "positive_worker_ratings"
                ]
            )
            responsible_months = (
                1
                if selected.get(
                    "responsible_month"
                )
                else 0
            )

        else:

            xp = sum(
                data.get(
                    "xp",
                    0,
                )
                for data in buckets.values()
            )

            resolved_count = sum(
                data["resolved"]
                for data in buckets.values()
            )

            rating_count = sum(
                data["ratings"]
                for data in buckets.values()
            )

            detailed_count = sum(
                data["detailed"]
                for data in buckets.values()
            )

            verified_count = sum(
                data["verified"]
                for data in buckets.values()
            )

            positive_worker_rating_count = sum(
                data["positive_worker_ratings"]
                for data in buckets.values()
            )

            responsible_months = sum(
                1
                for data in buckets.values()
                if data.get(
                    "responsible_month"
                )
            )

        rows.append(
            {
                "user": user,
                "name": (
                    user.get_full_name()
                    or user.username
                ),
                "xp": xp,

                # Informational stats only.
                "resolved": resolved_count,
                "ratings": rating_count,
                "detailed": detailed_count,
                "verified": verified_count,

                # Responsible participation signals.
                "positive_worker_ratings":
                    positive_worker_rating_count,
                "responsible_months":
                    responsible_months,
            }
        )

    # Tie-breakers also prioritise positive participation,
    # not complaint quantity.
    rows.sort(
        key=lambda item: (
            -item["xp"],
            -item[
                "positive_worker_ratings"
            ],
            -item["ratings"],
            item["name"].lower(),
        )
    )

    for index, row in enumerate(
        rows,
        1,
    ):
        row["rank"] = index
        row["level"] = _league_level(
            row["xp"]
        )

    return rows


def _worker_rows(monthly=False):
    start = _month_start() if monthly else None
    workers = WorkerProfile.objects.filter(is_approved=True).select_related("user")
    rows = []
    for worker in workers:
        resolved = Complaint.objects.filter(assigned_worker=worker, status="Resolved")
        ratings = Rating.objects.filter(complaint__assigned_worker=worker, rating_type="user_to_worker")
        if start:
            resolved = resolved.filter(updated_at__gte=start)
            ratings = ratings.filter(created_at__gte=start)
        resolved_count = resolved.count()
        verified_count = resolved.filter(otp_verified=True).count()
        five_star_count = ratings.filter(stars=5).count()
        rating_data = ratings.aggregate(avg=Avg("stars"), total=Count("id"))
        xp = resolved_count * 10 + verified_count * 2 + five_star_count * 5
        rows.append({
            "worker": worker,
            "name": worker.name or worker.user.username,
            "xp": xp,
            "resolved": resolved_count,
            "verified": verified_count,
            "five_star": five_star_count,
            "rating_avg": round(rating_data["avg"] or 0, 1),
            "rating_count": rating_data["total"] or 0,
        })
    rows.sort(key=lambda item: (-item["xp"], -item["rating_avg"], item["name"].lower()))
    for index, row in enumerate(rows, 1):
        row["rank"] = index
        row["level"] = _league_level(row["xp"])
    return rows


def _find_user_row(user, monthly=False):
    rows = _user_rows(monthly=monthly)
    row = next((item for item in rows if item["user"].pk == user.pk), None)
    return row or {
        "user": user,
        "name": user.get_full_name() or user.username,
        "xp": 0,
        "resolved": 0,
        "ratings": 0,
        "detailed": 0,
        "verified": 0,
        "positive_worker_ratings": 0,
        "responsible_months": 0,
        "rank": len(rows) + 1,
        "level": _league_level(0),
    }


def _find_worker_row(worker, monthly=False):
    rows = _worker_rows(monthly=monthly)
    row = next((item for item in rows if item["worker"].pk == worker.pk), None)
    return row or {"worker": worker, "name": worker.name, "xp": 0, "resolved": 0, "verified": 0, "five_star": 0, "rating_avg": 0, "rating_count": 0, "rank": len(rows) + 1, "level": _league_level(0)}


def _user_league_snapshot(user):
    return _find_user_row(user, monthly=True)


def _worker_league_snapshot(worker):
    return _find_worker_row(worker, monthly=True)


def _user_activity_snapshot(user):
    qs = Complaint.objects.filter(user=user)
    return {
        "total": qs.count(),
        "pending": qs.filter(status="Pending").count(),
        "in_progress": qs.filter(status="In Progress").count(),
        "resolved": qs.filter(status="Resolved").count(),
    }


def _user_achievement_cards(row):
    return [
        {
            "title": "First Verified Resolution",
            "detail": "Complete your first OTP-verified resolution",
            "icon": "V",
            "unlocked": row["verified"] >= 1,
        },
        {
            "title": "Helpful Citizen",
            "detail": "Give useful feedback on 5 completed services",
            "icon": "5",
            "unlocked": row["ratings"] >= 5,
        },
        {
            "title": "Trusted Citizen",
            "detail": "Receive 5 positive ratings from workers",
            "icon": "H",
            "unlocked": row["positive_worker_ratings"] >= 5,
        },
        {
            "title": "Detailed Reporter",
            "detail": "Create 5 quality reports with photo, location and useful details",
            "icon": "S",
            "unlocked": row["detailed"] >= 5,
        },
        {
            "title": "Responsible Regular",
            "detail": "Complete 3 balanced responsible-participation months",
            "icon": "D",
            "unlocked": row["responsible_months"] >= 3,
        },
        {
            "title": "Community Role Model",
            "detail": "Complete 6 balanced responsible-participation months",
            "icon": "Q",
            "unlocked": row["responsible_months"] >= 6,
        },
        {
            "title": "Community Champion",
            "detail": "Reach Gold Citizen league",
            "icon": "C",
            "unlocked": row["xp"] >= 1000,
        },
        {
            "title": "City Care Leader",
            "detail": "Reach Platinum Citizen league",
            "icon": "P",
            "unlocked": row["xp"] >= 2000,
        },
        {
            "title": "Top Supporter",
            "detail": "Reach Diamond Citizen league",
            "icon": "T",
            "unlocked": row["xp"] >= 3500,
        },
    ]


def _worker_achievement_cards(row):
    return [
        {"title": "First 10 Jobs", "detail": "Complete 10 resolved jobs", "icon": "10", "unlocked": row["resolved"] >= 10},
        {"title": "50 Jobs", "detail": "Complete 50 resolved jobs", "icon": "50", "unlocked": row["resolved"] >= 50},
        {"title": "100 Jobs", "detail": "Complete 100 resolved jobs", "icon": "100", "unlocked": row["resolved"] >= 100},
        {"title": "5-Star Pro", "detail": "Receive 10 five-star ratings", "icon": "5", "unlocked": row["five_star"] >= 10},
        {"title": "Verified Finisher", "detail": "Complete 25 OTP-verified jobs", "icon": "V", "unlocked": row["verified"] >= 25},
        {"title": "Gold Worker", "detail": "Reach Gold league", "icon": "G", "unlocked": row["xp"] >= 1000},
        {"title": "Platinum Worker", "detail": "Reach Platinum league", "icon": "P", "unlocked": row["xp"] >= 2000},
        {"title": "City Champion", "detail": "Reach Diamond league", "icon": "C", "unlocked": row["xp"] >= 3500},
        {"title": "Quality Expert", "detail": "Maintain 4.8+ rating with 20 ratings", "icon": "Q", "unlocked": row["rating_count"] >= 20 and row["rating_avg"] >= 4.8},
    ]



# =========================================================
# PUBLIC LEADERBOARD
# =========================================================

def public_leaderboard(request):
    """
    Public monthly leaderboard.

    Safe public fields only:
    rank, display name, league level, XP, resolved count,
    ratings / verified jobs and worker rating statistics.
    """
    user_rows = _user_rows(monthly=True)[:100]
    worker_rows = _worker_rows(monthly=True)[:100]

    viewer_user_id = None
    viewer_worker_id = None
    is_worker_viewer = False

    if request.user.is_authenticated:
        viewer_user_id = request.user.pk

        try:
            viewer_worker = request.user.worker_profile
            viewer_worker_id = viewer_worker.pk
            is_worker_viewer = True
        except WorkerProfile.DoesNotExist:
            pass

    return render(
        request,
        "complaints/public_leaderboard.html",
        {
            "user_rows": user_rows,
            "worker_rows": worker_rows,
            "viewer_user_id": viewer_user_id,
            "viewer_worker_id": viewer_worker_id,
            "is_worker_viewer": is_worker_viewer,
            "user_count": len(user_rows),
            "worker_count": len(worker_rows),
        },
    )


def user_leaderboard(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect
    """Backward-compatible route for the old user leaderboard URL."""
    return redirect("public_leaderboard")


def worker_leaderboard(request):
    """Backward-compatible route for the old worker leaderboard URL."""
    return redirect("public_leaderboard")



@login_required(login_url="login")
def user_achievements(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect
    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    try:
        request.user.worker_profile
        return redirect("worker_achievements")
    except WorkerProfile.DoesNotExist:
        pass

    me = _find_user_row(request.user, monthly=False)

    return render(
        request,
        "complaints/User_Folder/user_achievements.html",
        {
            "me": me,
            "achievements": _user_achievement_cards(me),
        },
    )


@login_required(login_url="login")
def user_rewards(request):

    role_redirect = _citizen_area_guard(request)
    if role_redirect:
        return role_redirect
    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    try:
        request.user.worker_profile
        return redirect("worker_rewards")
    except WorkerProfile.DoesNotExist:
        pass

    me = _find_user_row(request.user, monthly=False)

    return render(
        request,
        "complaints/User_Folder/user_rewards.html",
        {
            "me": me,
        },
    )


def _current_worker_or_redirect(request):
    try:
        worker = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        return None

    if not worker.is_approved:
        return None

    return worker


@login_required(login_url="worker_login")
def worker_achievements(request):
    worker = _current_worker_or_redirect(request)
    if not worker:
        messages.error(request, "Approved worker access required.")
        return redirect("worker_login")
    me = _find_worker_row(worker, monthly=False)
    return render(request, "complaints/Worker_Folder/worker_achievements.html", {"me": me, "worker": worker, "achievements": _worker_achievement_cards(me)})


@login_required(login_url="worker_login")
def worker_rewards(request):
    worker = _current_worker_or_redirect(request)
    if not worker:
        messages.error(request, "Approved worker access required.")
        return redirect("worker_login")
    me = _find_worker_row(worker, monthly=False)
    return render(request, "complaints/Worker_Folder/worker_rewards.html", {"me": me, "worker": worker})
