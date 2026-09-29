# =========================================================
# CITIZEN PROFILE VIEW
# =========================================================

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.contrib.staticfiles import finders

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from django.db.models import Avg, Count

from django.shortcuts import (
    render,
    redirect,
)

from .models import (
    Rating,
    UserFollow,
    UserProfile,
    WorkerProfile,
)

from .views import (
    _admin_account_redirect,
    _find_user_row,
    _league_level,
    _sync_citizen_premium,
    _user_achievement_cards,
    _user_rows,
)


# =========================================================
# PROFILE AVATAR OPTIONS
# =========================================================

FREE_PROFILE_AVATARS = {
    f"avatar_{number:02d}"
    for number in range(1, 41)
}


PREMIUM_PROFILE_AVATARS = {
    f"premium_avatar_{number:02d}"
    for number in range(1, 41)
}


FREE_AVATAR_OPTIONS = [
    {
        "id": f"avatar_{number:02d}",
        "label": f"Free avatar {number}",
        "static_path": (
            f"complaints/avatars/free/"
            f"avatar_{number:02d}.png"
        ),
    }
    for number in range(1, 41)
]


PREMIUM_AVATAR_OPTIONS = [
    {
        "id": f"premium_avatar_{number:02d}",
        "label": f"Premium avatar {number}",
        "static_path": (
            f"complaints/avatars/premium/"
            f"premium_avatar_{number:02d}.png"
        ),
    }
    for number in range(1, 41)
]


# =========================================================
# DELETE OLD PROFILE PHOTO
# =========================================================

def _delete_old_profile_photo(profile):

    if not profile.photo:
        return

    old_name = profile.photo.name

    if (
        old_name
        and default_storage.exists(
            old_name
        )
    ):
        default_storage.delete(
            old_name
        )


# =========================================================
# APPLY BUNDLED AVATAR
# =========================================================

def _apply_bundled_avatar(
    profile,
    avatar_id,
    avatar_type,
):

    if avatar_type == "premium":

        allowed_avatars = (
            PREMIUM_PROFILE_AVATARS
        )

        folder = "premium"

    else:

        allowed_avatars = (
            FREE_PROFILE_AVATARS
        )

        folder = "free"


    if avatar_id not in allowed_avatars:
        return False


    relative_path = (
        f"complaints/avatars/"
        f"{folder}/"
        f"{avatar_id}.png"
    )


    source_path = finders.find(
        relative_path
    )


    if not source_path:
        return False


    _delete_old_profile_photo(
        profile
    )


    with open(
        source_path,
        "rb",
    ) as avatar_file:

        avatar_bytes = (
            avatar_file.read()
        )


    filename = (
        f"user_{profile.user_id}_"
        f"{avatar_id}.png"
    )


    profile.photo.save(
        filename,
        ContentFile(
            avatar_bytes
        ),
        save=False,
    )


    return True


# =========================================================
# USER PROFILE
# =========================================================

@login_required(login_url="login")
def profile(request):

    # =====================================================
    # ADMIN PROTECTION
    # =====================================================

    admin_redirect = (
        _admin_account_redirect(
            request
        )
    )

    if admin_redirect:
        return admin_redirect


    user = request.user


    # =====================================================
    # WORKER ACCOUNT
    # =====================================================

    if WorkerProfile.objects.filter(
        user=user
    ).exists():

        worker = (
            user.worker_profile
        )

        return redirect(
            "worker_profile",
            worker_id=worker.id,
        )


    # =====================================================
    # CITIZEN PROFILE + PREMIUM STATUS
    # =====================================================

    (
        user_profile,
        premium_membership,
        premium_active,
    ) = _sync_citizen_premium(
        user
    )


    # =====================================================
    # USER RATING
    # =====================================================

    user_rating_data = (
        Rating.objects
        .filter(
            complaint__user=user,
            rating_type="worker_to_user",
        )
        .aggregate(
            average=Avg("stars"),
            total=Count("id"),
        )
    )


    user_average_rating = (
        user_rating_data[
            "average"
        ]
    )


    user_rating_count = (
        user_rating_data[
            "total"
        ]
    )


    # =====================================================
    # PROFILE UPDATE
    # =====================================================

    if request.method == "POST":

        first_name = (
            request.POST.get(
                "first_name",
                "",
            ).strip()
        )


        last_name = (
            request.POST.get(
                "last_name",
                "",
            ).strip()
        )


        email = (
            request.POST.get(
                "email",
                "",
            ).strip()
        )


        phone = (
            request.POST.get(
                "phone",
                "",
            ).strip()
        )


        gender = (
            request.POST.get(
                "gender",
                "",
            ).strip()
        )


        photo = (
            request.FILES.get(
                "photo"
            )
        )


        free_avatar = (
            request.POST.get(
                "free_avatar",
                "",
            ).strip()
        )


        premium_avatar = (
            request.POST.get(
                "premium_avatar",
                "",
            ).strip()
        )


        # =================================================
        # EMAIL REQUIRED
        # =================================================

        if not email:

            messages.error(
                request,
                "Email address is required.",
            )

            return redirect(
                "profile"
            )


        # =================================================
        # EMAIL UNIQUE
        # =================================================

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
                "This email is already registered.",
            )

            return redirect(
                "profile"
            )


        # =================================================
        # PHONE
        # =================================================

        if (
            phone
            and len(phone) > 15
        ):

            messages.error(
                request,
                "Phone number is too long.",
            )

            return redirect(
                "profile"
            )


        # =================================================
        # GENDER
        # =================================================

        allowed_genders = {
            "Male",
            "Female",
            "Other",
            "Prefer not to say",
            "",
        }


        if (
            gender
            not in allowed_genders
        ):

            messages.error(
                request,
                "Please select a valid gender.",
            )

            return redirect(
                "profile"
            )


        # =================================================
        # NORMAL UPLOADED PHOTO
        # =================================================

        if photo:

            if (
                photo.size
                > 5 * 1024 * 1024
            ):

                messages.error(
                    request,
                    (
                        "Profile photo must "
                        "be less than 5 MB."
                    ),
                )

                return redirect(
                    "profile"
                )


            content_type = (
                photo.content_type
                or ""
            )


            if not (
                content_type.startswith(
                    "image/"
                )
            ):

                messages.error(
                    request,
                    "Please select a valid image.",
                )

                return redirect(
                    "profile"
                )


            _delete_old_profile_photo(
                user_profile
            )


            user_profile.photo = (
                photo
            )


        # =================================================
        # PREMIUM DP
        # =================================================

        elif premium_avatar:

            # ---------------------------------------------
            # PREMIUM SECURITY
            # ---------------------------------------------

            if not premium_active:

                messages.info(
                    request,
                    (
                        "Citizen Premium is required "
                        "to use Premium profile pictures."
                    ),
                )

                return redirect(
                    "citizen_premium"
                )


            # ---------------------------------------------
            # PREMIUM AVATAR VALIDATION
            # ---------------------------------------------

            if (
                premium_avatar
                not in PREMIUM_PROFILE_AVATARS
            ):

                messages.error(
                    request,
                    (
                        "Please select a valid "
                        "Premium profile picture."
                    ),
                )

                return redirect(
                    "profile"
                )


            # ---------------------------------------------
            # APPLY PREMIUM DP
            # ---------------------------------------------

            premium_saved = (
                _apply_bundled_avatar(
                    user_profile,
                    premium_avatar,
                    "premium",
                )
            )


            if not premium_saved:

                messages.error(
                    request,
                    (
                        "Premium profile picture "
                        "file could not be found."
                    ),
                )

                return redirect(
                    "profile"
                )


        # =================================================
        # FREE DP
        # =================================================

        elif free_avatar:

            if (
                free_avatar
                not in FREE_PROFILE_AVATARS
            ):

                messages.error(
                    request,
                    (
                        "Please select a valid "
                        "free avatar."
                    ),
                )

                return redirect(
                    "profile"
                )


            free_saved = (
                _apply_bundled_avatar(
                    user_profile,
                    free_avatar,
                    "free",
                )
            )


            if not free_saved:

                messages.error(
                    request,
                    (
                        "Free avatar file "
                        "could not be found."
                    ),
                )

                return redirect(
                    "profile"
                )


        # =================================================
        # SAVE USER
        # =================================================

        user.first_name = (
            first_name
        )

        user.last_name = (
            last_name
        )

        user.email = (
            email
        )

        user.save()


        # =================================================
        # SAVE PROFILE
        # =================================================

        user_profile.phone = (
            phone
        )

        user_profile.gender = (
            gender
        )

        user_profile.save()


        messages.success(
            request,
            "Profile updated successfully.",
        )


        return redirect(
            "profile"
        )


    # =====================================================
    # LEAGUE
    # =====================================================

    lifetime_rows = (
        _user_rows(
            monthly=False
        )
    )


    league = next(
        (
            row
            for row
            in lifetime_rows
            if (
                row["user"].pk
                == user.pk
            )
        ),
        None,
    )


    if league is None:

        league = (
            _find_user_row(
                user,
                monthly=False,
            )
        )


    # =====================================================
    # FOLLOWERS
    # =====================================================

    followers_count = (
        UserFollow.objects
        .filter(
            following=user
        )
        .count()
    )


    # =====================================================
    # FOLLOWING
    # =====================================================

    following_count = (
        UserFollow.objects
        .filter(
            follower=user
        )
        .count()
    )


    # =====================================================
    # NETWORK
    # =====================================================

    network_user_ids = set(
        UserFollow.objects
        .filter(
            follower=user
        )
        .values_list(
            "following_id",
            flat=True,
        )
    )


    network_user_ids.update(
        UserFollow.objects
        .filter(
            following=user
        )
        .values_list(
            "follower_id",
            flat=True,
        )
    )


    network_count = (
        len(
            network_user_ids
        )
    )


    following_ids = set(
        UserFollow.objects
        .filter(
            follower=user
        )
        .values_list(
            "following_id",
            flat=True,
        )
    )


    # =====================================================
    # PEOPLE YOU MAY KNOW
    # =====================================================

    candidate_profiles = list(
        UserProfile.objects
        .select_related(
            "user"
        )
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
        or ""
    ).strip().lower()


    candidate_profiles.sort(
        key=lambda item: (

            0
            if (
                current_city
                and
                (
                    item.city
                    or ""
                )
                .strip()
                .lower()
                == current_city
            )
            else 1,

            (
                item.user
                .get_full_name()
                or
                item.user.username
            ).lower(),
        )
    )


    row_map = {
        row["user"].pk:
            row

        for row
        in lifetime_rows
    }


    suggestions = []


    for item in (
        candidate_profiles[:4]
    ):

        suggestion_league = (
            row_map.get(
                item.user_id
            )
        )


        if (
            suggestion_league
            is None
        ):

            suggestion_league = {

                "level":
                    _league_level(
                        0
                    ),

                "xp":
                    0,

                "resolved":
                    0,
            }


        suggestions.append(
            {

                "user":
                    item.user,

                "profile":
                    item,

                "league":
                    suggestion_league,
            }
        )


    # =====================================================
    # ACHIEVEMENTS
    # =====================================================

    achievement_cards = (
        _user_achievement_cards(
            league
        )
    )


    unlocked_achievements = [

        item

        for item
        in achievement_cards

        if item["unlocked"]
    ]


    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "complaints/User_Folder/profile.html",
        {

            "profile_user":
                user,

            "user_profile":
                user_profile,

            "user_average_rating":
                user_average_rating,

            "user_rating_count":
                user_rating_count,

            "league":
                league,

            "followers_count":
                followers_count,

            "following_count":
                following_count,

            "network_count":
                network_count,

            "suggestions":
                suggestions,

            "unlocked_achievements":
                unlocked_achievements[:4],

            "unlocked_achievement_count":
                len(
                    unlocked_achievements
                ),

            # =================================================
            # AVATARS
            # =================================================

            "free_avatar_options":
                FREE_AVATAR_OPTIONS,

            "premium_avatar_options":
                PREMIUM_AVATAR_OPTIONS,

            # =================================================
            # CITIZEN PREMIUM
            # =================================================

            "user_is_premium":
                premium_active,

            "premium_membership":
                premium_membership,
        },
    )