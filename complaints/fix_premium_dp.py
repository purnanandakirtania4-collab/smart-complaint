from pathlib import Path


# =========================================================
# CONFIG
# =========================================================

VIEWS_FILE = Path("complaints/views.py")


if not VIEWS_FILE.exists():
    raise SystemExit(
        "ERROR: complaints/views.py not found. "
        "Run this script from your Django project root."
    )


text = VIEWS_FILE.read_text(
    encoding="utf-8"
)


# =========================================================
# 1. CONTENTFILE IMPORT
# =========================================================

content_file_import = (
    "from django.core.files.base import ContentFile\n"
)


if content_file_import not in text:

    marker = (
        "from django.core.files.storage "
        "import default_storage\n"
    )

    if marker not in text:
        raise SystemExit(
            "ERROR: default_storage import not found."
        )

    text = text.replace(
        marker,
        marker + content_file_import,
        1,
    )


# =========================================================
# 2. FULL PROFILE AVATAR HELPER SECTION
# =========================================================

avatar_start_marker = """# =========================================================
# PROFILE AVATAR HELPERS
# =========================================================
"""


avatar_end_marker = """# =========================================================
# APP FRONT PAGE / ACCOUNT GATEWAY
# =========================================================
"""


if avatar_start_marker not in text:
    raise SystemExit(
        "ERROR: PROFILE AVATAR HELPERS section not found."
    )


if avatar_end_marker not in text:
    raise SystemExit(
        "ERROR: APP FRONT PAGE section not found."
    )


avatar_start = text.index(
    avatar_start_marker
)


avatar_end = text.index(
    avatar_end_marker,
    avatar_start,
)


new_avatar_section = r'''# =========================================================
# PROFILE AVATAR HELPERS
# =========================================================

FREE_PROFILE_AVATARS = {
    "avatar_01",
    "avatar_02",
    "avatar_03",
    "avatar_04",
    "avatar_05",
    "avatar_06",
    "avatar_07",
    "avatar_08",
    "avatar_09",
    "avatar_10",
    "avatar_11",
    "avatar_12",
    "avatar_13",
    "avatar_14",
    "avatar_15",
    "avatar_16",
    "avatar_17",
    "avatar_18",
    "avatar_19",
    "avatar_20",
    "avatar_21",
    "avatar_22",
    "avatar_23",
    "avatar_24",
    "avatar_25",
    "avatar_26",
    "avatar_27",
    "avatar_28",
    "avatar_29",
    "avatar_30",
    "avatar_31",
    "avatar_32",
    "avatar_33",
    "avatar_34",
    "avatar_35",
    "avatar_36",
    "avatar_37",
    "avatar_38",
    "avatar_39",
    "avatar_40",
}


PREMIUM_PROFILE_AVATARS = {
    "premium_01",
    "premium_02",
    "premium_03",
    "premium_04",
    "premium_05",
    "premium_06",
    "premium_07",
    "premium_08",
    "premium_09",
    "premium_10",
    "premium_11",
    "premium_12",
}


def _apply_profile_avatar(
    instance,
    field_name,
    avatar_id,
    filename_prefix,
    avatar_type="free",
):
    """
    Save one bundled Smart Complaint avatar
    into the existing ImageField.

    Free:
    complaints/avatars/free/

    Premium:
    complaints/avatars/premium/
    """

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


    image_field = getattr(
        instance,
        field_name,
    )


    if image_field:

        old_name = image_field.name

        if (
            old_name
            and
            default_storage.exists(
                old_name
            )
        ):

            default_storage.delete(
                old_name
            )


    with open(
        source_path,
        "rb",
    ) as avatar_file:

        avatar_bytes = (
            avatar_file.read()
        )


    filename = (
        f"{filename_prefix}_"
        f"{avatar_id}.png"
    )


    getattr(
        instance,
        field_name,
    ).save(
        filename,
        ContentFile(
            avatar_bytes
        ),
        save=False,
    )


    return True


def _apply_free_profile_avatar(
    instance,
    field_name,
    avatar_id,
    filename_prefix,
):
    """
    Keep all existing free-avatar code working.
    """

    return _apply_profile_avatar(
        instance,
        field_name,
        avatar_id,
        filename_prefix,
        avatar_type="free",
    )


def _apply_premium_profile_avatar(
    instance,
    field_name,
    avatar_id,
    filename_prefix,
):
    """
    Apply Premium DP after Premium
    membership has been verified.
    """

    return _apply_profile_avatar(
        instance,
        field_name,
        avatar_id,
        filename_prefix,
        avatar_type="premium",
    )


def _profile_uses_premium_avatar(
    profile
):
    """
    Detect whether the current saved photo
    is one of Smart Complaint's bundled
    Premium DPs.
    """

    photo = getattr(
        profile,
        "photo",
        None,
    )


    if (
        not photo
        or not photo.name
    ):
        return False


    filename = os.path.basename(
        photo.name
    )


    return any(
        (
            f"_{avatar_id}.png"
            in filename
        )
        or
        (
            f"_{avatar_id}_"
            in filename
        )
        for avatar_id
        in PREMIUM_PROFILE_AVATARS
    )


'''


text = (
    text[:avatar_start]
    + new_avatar_section
    + text[avatar_end:]
)


# =========================================================
# 3. FULL USER PROFILE VIEW
# =========================================================

profile_start_marker = """# =========================================================
# USER PROFILE
# =========================================================
"""


profile_end_marker = """# =========================================================
# USER COMMUNITY / FOLLOW SYSTEM
# =========================================================
"""


if profile_start_marker not in text:
    raise SystemExit(
        "ERROR: USER PROFILE section not found."
    )


if profile_end_marker not in text:
    raise SystemExit(
        "ERROR: USER COMMUNITY section not found."
    )


profile_start = text.index(
    profile_start_marker
)


profile_end = text.index(
    profile_end_marker,
    profile_start,
)


new_profile_section = r'''# =========================================================
# USER PROFILE
# =========================================================

@login_required(login_url='login')
def profile(request):

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
            'worker_profile',
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
            rating_type='worker_to_user'
        )
        .aggregate(
            average=Avg('stars'),
            total=Count('id')
        )
    )


    user_average_rating = (
        user_rating_data[
            'average'
        ]
    )


    user_rating_count = (
        user_rating_data[
            'total'
        ]
    )


    # =====================================================
    # UPDATE PROFILE
    # =====================================================

    if request.method == 'POST':

        first_name = (
            request.POST.get(
                'first_name',
                ''
            ).strip()
        )


        last_name = (
            request.POST.get(
                'last_name',
                ''
            ).strip()
        )


        email = (
            request.POST.get(
                'email',
                ''
            ).strip()
        )


        phone = (
            request.POST.get(
                'phone',
                ''
            ).strip()
        )


        gender = (
            request.POST.get(
                'gender',
                ''
            ).strip()
        )


        photo = (
            request.FILES.get(
                'photo'
            )
        )


        free_avatar = (
            request.POST.get(
                'free_avatar',
                ''
            ).strip()
        )


        premium_avatar = (
            request.POST.get(
                'premium_avatar',
                ''
            ).strip()
        )


        # =================================================
        # EMAIL
        # =================================================

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


        # =================================================
        # PHONE
        # =================================================

        if (
            phone
            and len(phone) > 15
        ):

            messages.error(
                request,
                'Phone number is too long.'
            )

            return redirect(
                'profile'
            )


        # =================================================
        # GENDER
        # =================================================

        allowed_genders = {
            'Male',
            'Female',
            'Other',
            'Prefer not to say',
            '',
        }


        if (
            gender
            not in allowed_genders
        ):

            messages.error(
                request,
                'Please select a valid gender.'
            )

            return redirect(
                'profile'
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
                        'Profile photo must '
                        'be less than 5 MB.'
                    )
                )

                return redirect(
                    'profile'
                )


            if not (
                photo.content_type
                or ''
            ).startswith(
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

                old_photo = (
                    user_profile
                    .photo
                    .name
                )


                if (
                    old_photo
                    and
                    default_storage.exists(
                        old_photo
                    )
                ):

                    default_storage.delete(
                        old_photo
                    )


            user_profile.photo = (
                photo
            )


        # =================================================
        # PREMIUM DP
        # =================================================

        elif premium_avatar:

            # ---------------------------------------------
            # IMPORTANT:
            # Backend Premium protection.
            #
            # HTML/JavaScript bypass karne ke baad bhi
            # Free user Premium DP save nahi kar sakta.
            # ---------------------------------------------

            if not premium_active:

                messages.info(
                    request,
                    (
                        'Citizen Premium is required '
                        'to use Premium profile pictures.'
                    )
                )

                return redirect(
                    'citizen_premium'
                )


            if (
                premium_avatar
                not in PREMIUM_PROFILE_AVATARS
            ):

                messages.error(
                    request,
                    (
                        'Please select a valid '
                        'Premium profile picture.'
                    )
                )

                return redirect(
                    'profile'
                )


            if not (
                _apply_premium_profile_avatar(
                    user_profile,
                    'photo',
                    premium_avatar,
                    f'user_{user.id}',
                )
            ):

                messages.error(
                    request,
                    (
                        'Premium profile picture '
                        'could not be found.'
                    )
                )

                return redirect(
                    'profile'
                )


        # =================================================
        # FREE AVATAR
        # =================================================

        elif free_avatar:

            if (
                free_avatar
                not in FREE_PROFILE_AVATARS
            ):

                messages.error(
                    request,
                    (
                        'Please select a '
                        'valid free avatar.'
                    )
                )

                return redirect(
                    'profile'
                )


            if not (
                _apply_free_profile_avatar(
                    user_profile,
                    'photo',
                    free_avatar,
                    f'user_{user.id}',
                )
            ):

                messages.error(
                    request,
                    (
                        'Please select a '
                        'valid free avatar.'
                    )
                )

                return redirect(
                    'profile'
                )


        # =================================================
        # SAVE DJANGO USER
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
        # SAVE USER PROFILE
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
            'Profile updated successfully.'
        )


        return redirect(
            'profile'
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
                row['user'].pk
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
    # FOLLOWERS / FOLLOWING
    # =====================================================

    followers_count = (
        UserFollow.objects
        .filter(
            following=user
        )
        .count()
    )


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
            'following_id',
            flat=True,
        )
    )


    network_user_ids.update(
        UserFollow.objects
        .filter(
            following=user
        )
        .values_list(
            'follower_id',
            flat=True,
        )
    )


    network_count = len(
        network_user_ids
    )


    following_ids = set(
        UserFollow.objects
        .filter(
            follower=user
        )
        .values_list(
            'following_id',
            flat=True,
        )
    )


    # =====================================================
    # PEOPLE SUGGESTIONS
    # =====================================================

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
                and
                (
                    item.city
                    or ''
                )
                .strip()
                .lower()
                == current_city
            )
            else 1,
            (
                item.user.get_full_name()
                or
                item.user.username
            ).lower(),
        )
    )


    row_map = {
        row['user'].pk:
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

                'level':
                    _league_level(
                        0
                    ),

                'xp':
                    0,

                'resolved':
                    0,
            }


        suggestions.append(
            {
                'user':
                    item.user,

                'profile':
                    item,

                'league':
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
        if item['unlocked']
    ]


    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        'complaints/User_Folder/profile.html',
        {
            'profile_user':
                user,

            'user_profile':
                user_profile,

            'user_average_rating':
                user_average_rating,

            'user_rating_count':
                user_rating_count,

            'league':
                league,

            'followers_count':
                followers_count,

            'following_count':
                following_count,

            'network_count':
                network_count,

            'suggestions':
                suggestions,

            'unlocked_achievements':
                unlocked_achievements[:4],

            'unlocked_achievement_count':
                len(
                    unlocked_achievements
                ),

            # Citizen Premium
            'user_is_premium':
                premium_active,

            'premium_membership':
                premium_membership,
        }
    )


'''


text = (
    text[:profile_start]
    + new_profile_section
    + text[profile_end:]
)


# =========================================================
# 4. PREMIUM EXPIRY PROTECTION
# =========================================================

sync_start_text = (
    "def _sync_citizen_premium(user):"
)


activate_start_text = (
    "\ndef _activate_citizen_premium("
)


if sync_start_text not in text:
    raise SystemExit(
        "ERROR: _sync_citizen_premium not found."
    )


sync_start = text.index(
    sync_start_text
)


try:

    sync_end = text.index(
        activate_start_text,
        sync_start,
    )

except ValueError:

    raise SystemExit(
        "ERROR: _activate_citizen_premium not found."
    )


sync_block = text[
    sync_start:
    sync_end
]


expiry_code = r'''
    # -----------------------------------------------------
    # PREMIUM DP EXPIRY PROTECTION
    # -----------------------------------------------------
    #
    # Agar Premium expire ho gaya aur current DP bundled
    # Premium DP hai, to wo Premium DP remove ho jayegi.
    #
    # User ki normal uploaded photo ya free DP ko touch
    # nahi kiya jayega.
    # -----------------------------------------------------

    if (
        not active
        and
        _profile_uses_premium_avatar(
            profile
        )
    ):

        old_photo = (
            profile.photo.name
        )


        if (
            old_photo
            and
            default_storage.exists(
                old_photo
            )
        ):

            default_storage.delete(
                old_photo
            )


        profile.photo = None

        profile.save(
            update_fields=[
                "photo",
                "updated_at",
            ]
        )

'''


if (
    "PREMIUM DP EXPIRY PROTECTION"
    not in sync_block
):

    return_line = (
        "    return profile, membership, active"
    )


    if return_line not in sync_block:

        raise SystemExit(
            "ERROR: Premium sync return line not found."
        )


    sync_block = sync_block.replace(
        return_line,
        expiry_code
        + return_line,
        1,
    )


    text = (
        text[:sync_start]
        + sync_block
        + text[sync_end:]
    )


# =========================================================
# 5. WRITE BACK
# =========================================================

backup_file = Path(
    "complaints/views_before_premium_dp.py"
)


backup_file.write_text(
    VIEWS_FILE.read_text(
        encoding="utf-8"
    ),
    encoding="utf-8",
)


VIEWS_FILE.write_text(
    text,
    encoding="utf-8",
)


print()
print(
    "========================================"
)

print(
    " PREMIUM DP BACKEND INSTALLED"
)

print(
    "========================================"
)

print()

print(
    "Updated:"
)

print(
    VIEWS_FILE
)

print()

print(
    "Backup:"
)

print(
    backup_file
)

print()

print(
    "Free user + Premium DP -> Citizen Premium"
)

print(
    "Premium user + Premium DP -> Allowed"
)

print(
    "Expired Premium -> Bundled Premium DP removed"
)

print()

print(
    "DONE."
)