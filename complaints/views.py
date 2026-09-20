import calendar
import secrets
import re
import json
import os
from datetime import timedelta

import razorpay

from django.conf import settings
from django.shortcuts import render, redirect
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
from django.db.models import Avg, Count, Case, When, Value, IntegerField
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Complaint,
    WorkerProfile,
    UserProfile,
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

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    return render(
        request,
        'complaints/User_Folder/home.html'
    )


# =========================================================
# USER LOGIN
# =========================================================

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

    user_profile, created = (
        UserProfile.objects.get_or_create(
            user=user
        )
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

    user_average_rating = (
        user_rating_data['average']
    )

    user_rating_count = (
        user_rating_data['total']
    )

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

                old_photo = (
                    user_profile.photo.name
                )

                if default_storage.exists(
                    old_photo
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

    return render(
        request,
        'complaints/User_Folder/profile.html',
        {
            'profile_user': user,
            'user_profile': user_profile,
            'user_average_rating': user_average_rating,
            'user_rating_count': user_rating_count,
        }
    )


# =========================================================
# USER SETTINGS
# =========================================================

@login_required(login_url='login')
def user_settings(request):

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

    user_profile, created = (
        UserProfile.objects.get_or_create(
            user=request.user
        )
    )

    return render(
        request,
        'complaints/User_Folder/user_settings.html',
        {
            'user_profile': user_profile,
            'user_is_premium': user_profile.is_premium,
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

@login_required(login_url='login')
def worker_profile(request, worker_id):

    admin_redirect = _admin_account_redirect(request)
    if admin_redirect:
        return admin_redirect

    try:

        worker = (
            WorkerProfile.objects
            .select_related(
                'user'
            )
            .get(
                id=worker_id,
                is_approved=True
            )
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker profile not found.'
        )

        return redirect(
            'worker_details'
        )

    is_owner = (
        request.user.id
        == worker.user.id
    )

    worker_rating_data = (
        Rating.objects
        .filter(
            complaint__assigned_worker=worker,
            rating_type='user_to_worker'
        )
        .aggregate(
            average=Avg('stars'),
            total=Count('id')
        )
    )

    worker_average_rating = (
        worker_rating_data['average']
    )

    worker_rating_count = (
        worker_rating_data['total']
    )

    if request.method == 'POST':

        if not is_owner:

            messages.error(
                request,
                'You cannot edit this worker profile.'
            )

            return redirect(
                'worker_profile',
                worker_id=worker.id
            )

        name = request.POST.get(
            'name',
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

        experience = request.POST.get(
            'experience',
            ''
        ).strip()

        photo = request.FILES.get(
            'photo'
        )

        free_avatar = request.POST.get(
            'free_avatar',
            ''
        ).strip()

        if (
            not name
            or not email
            or not phone
            or not experience
        ):

            messages.error(
                request,
                'Please fill all required fields.'
            )

            return redirect(
                'worker_profile',
                worker_id=worker.id
            )

        if (
            User.objects
            .filter(
                email=email
            )
            .exclude(
                id=worker.user.id
            )
            .exists()
        ):

            messages.error(
                request,
                'This email is already registered.'
            )

            return redirect(
                'worker_profile',
                worker_id=worker.id
            )

        valid_experience = [
            choice[0]
            for choice
            in WorkerProfile.EXPERIENCE_CHOICES
        ]

        if experience not in valid_experience:

            messages.error(
                request,
                'Invalid experience selected.'
            )

            return redirect(
                'worker_profile',
                worker_id=worker.id
            )

        if photo:

            if photo.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    'Profile photo must be less than 5 MB.'
                )

                return redirect(
                    'worker_profile',
                    worker_id=worker.id
                )

            if not photo.content_type.startswith(
                'image/'
            ):

                messages.error(
                    request,
                    'Please select a valid image.'
                )

                return redirect(
                    'worker_profile',
                    worker_id=worker.id
                )

            if worker.photo:

                old_photo = (
                    worker.photo.name
                )

                if default_storage.exists(
                    old_photo
                ):

                    default_storage.delete(
                        old_photo
                    )

            worker.photo = photo

        elif free_avatar:

            if not _apply_free_profile_avatar(
                worker,
                'photo',
                free_avatar,
                f'worker_{worker.id}',
            ):

                messages.error(
                    request,
                    'Please select a valid free avatar.'
                )

                return redirect(
                    'worker_profile',
                    worker_id=worker.id
                )

        worker.name = name
        worker.phone = phone
        worker.experience = experience

        worker.user.email = email
        worker.user.save()

        worker.save()

        messages.success(
            request,
            'Worker profile updated successfully.'
        )

        return redirect(
            'worker_profile',
            worker_id=worker.id
        )

    return render(
        request,
        'complaints/Worker_Folder/worker_profile.html',
        {
            'worker': worker,
            'is_owner': is_owner,
            'experience_choices':
                WorkerProfile.EXPERIENCE_CHOICES,
            'worker_average_rating':
                worker_average_rating,
            'worker_rating_count':
                worker_rating_count,
        }
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

        return redirect(
            'worker_dashboard'
        )

    return render(
        request,
        'complaints/Worker_Folder/worker_login.html'
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
                    f'is now Resolved.'
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

    complaints = list(
        Complaint.objects
        .filter(
            assigned_worker=worker
        )
        .select_related(
            'user',
            'user__user_profile'
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

    return render(
        request,
        'complaints/Worker_Folder/worker_dashboard.html',
        {
            'worker': worker,
            'complaints': complaints,
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

        subscription.terms_version = '1.0'

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

def _razorpay_timestamp_to_datetime(value):
    """Convert a Razorpay Unix timestamp to a timezone-aware datetime."""
    if value in (None, ""):
        return None

    try:
        return timezone.datetime.fromtimestamp(
            int(value),
            tz=timezone.get_current_timezone(),
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _sync_worker_subscription_from_razorpay(
    subscription,
    razorpay_subscription,
):
    """Synchronise our WorkerSubscription with a verified Razorpay subscription."""
    razorpay_status = str(
        razorpay_subscription.get('status', '')
    ).lower()

    customer_id = razorpay_subscription.get('customer_id') or ''
    plan_id = razorpay_subscription.get('plan_id') or ''

    if customer_id:
        subscription.razorpay_customer_id = customer_id

    if plan_id:
        subscription.razorpay_plan_id = plan_id

    now = timezone.now()

    # Our ₹49 introductory month starts as soon as Razorpay authenticates
    # the mandate. The ₹149 plan itself starts on next_billing_at.
    if razorpay_status in {'authenticated', 'active'}:
        subscription.status = 'active'

        if not subscription.started_at:
            subscription.started_at = now

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
        elif not subscription.current_period_start:
            subscription.current_period_start = subscription.started_at

        if current_end:
            subscription.current_period_end = current_end
        elif (
            not subscription.current_period_end
            and subscription.next_billing_at
        ):
            subscription.current_period_end = subscription.next_billing_at

        if charge_at:
            subscription.next_billing_at = charge_at

    elif razorpay_status in {'created', 'pending', 'halted'}:
        subscription.status = 'pending'

    elif razorpay_status == 'cancelled':
        subscription.status = 'cancelled'

        if not subscription.cancelled_at:
            subscription.cancelled_at = now

    elif razorpay_status in {'completed', 'expired'}:
        subscription.status = 'expired'

    subscription.save()


# =========================================================
# WORKER SUBSCRIPTION PAYMENT
# ₹49 NOW + ₹149/MONTH FROM NEXT MONTH
# =========================================================

@login_required(login_url='worker_login')
def worker_subscription_payment(request):

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
            'Your worker account is not approved.'
        )
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

    razorpay_key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    razorpay_key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    razorpay_plan_id = getattr(settings, 'RAZORPAY_WORKER_PLAN_ID', '')

    # Whenever the worker returns to this page, synchronise an existing
    # Razorpay subscription. This also handles the future-start case where
    # Razorpay reports "authenticated" after the ₹49 introductory payment.
    if (
        subscription.razorpay_subscription_id
        and razorpay_key_id
        and razorpay_key_secret
    ):
        try:
            client = razorpay.Client(
                auth=(razorpay_key_id, razorpay_key_secret)
            )
            existing_subscription = client.subscription.fetch(
                subscription.razorpay_subscription_id
            )
            _sync_worker_subscription_from_razorpay(
                subscription,
                existing_subscription,
            )
        except Exception as error:
            print('RAZORPAY SUBSCRIPTION SYNC ERROR:', error)

    if request.method == 'POST':

        if (
            not razorpay_key_id
            or not razorpay_key_secret
            or not razorpay_plan_id
        ):
            messages.error(
                request,
                'Razorpay subscription configuration is missing.'
            )
            return redirect('worker_subscription_payment')

        try:
            client = razorpay.Client(
                auth=(razorpay_key_id, razorpay_key_secret)
            )

            if subscription.razorpay_subscription_id:
                try:
                    existing_subscription = client.subscription.fetch(
                        subscription.razorpay_subscription_id
                    )

                    _sync_worker_subscription_from_razorpay(
                        subscription,
                        existing_subscription,
                    )

                    razorpay_status = existing_subscription.get(
                        'status',
                        ''
                    )
                    short_url = existing_subscription.get('short_url')

                    if razorpay_status in {'authenticated', 'active'}:
                        messages.success(
                            request,
                            'Your worker subscription is active.'
                        )
                        return redirect('worker_dashboard')

                    if (
                        razorpay_status
                        in {
                            'created',
                            'pending',
                            'halted',
                        }
                        and short_url
                    ):
                        return redirect(short_url)

                except Exception as error:
                    print('RAZORPAY EXISTING SUBSCRIPTION ERROR:', error)

            now = timezone.now()
            first_regular_billing_date = add_one_month(now)
            start_at_timestamp = int(
                first_regular_billing_date.timestamp()
            )

            razorpay_subscription = client.subscription.create(
                {
                    'plan_id': razorpay_plan_id,
                    'total_count': 12,
                    'quantity': 1,
                    'customer_notify': True,
                    'start_at': start_at_timestamp,
                    'addons': [
                        {
                            'item': {
                                'name': 'First Month Subscription Fee',
                                'amount': 4900,
                                'currency': 'INR',
                            }
                        }
                    ],
                    'notes': {
                        'worker_id': str(worker.id),
                        'worker_name': worker.name,
                        'django_user_id': str(request.user.id),
                        'subscription_type': 'worker_monthly',
                    },
                }
            )

            razorpay_subscription_id = razorpay_subscription.get(
                'id',
                ''
            )
            razorpay_short_url = razorpay_subscription.get(
                'short_url',
                ''
            )

            if not razorpay_subscription_id:
                messages.error(
                    request,
                    'Razorpay did not return a subscription ID.'
                )
                return redirect('worker_subscription_payment')

            subscription.razorpay_subscription_id = (
                razorpay_subscription_id
            )
            subscription.razorpay_plan_id = razorpay_plan_id
            subscription.first_month_price = 49
            subscription.monthly_price = 149
            subscription.status = 'pending'
            subscription.started_at = None
            subscription.current_period_start = None
            subscription.current_period_end = None
            subscription.cancelled_at = None
            subscription.next_billing_at = first_regular_billing_date
            subscription.save()

            if razorpay_short_url:
                return redirect(razorpay_short_url)

            messages.success(
                request,
                'Subscription created successfully.'
            )
            return redirect('worker_subscription_payment')

        except razorpay.errors.BadRequestError as error:
            print('RAZORPAY BAD REQUEST ERROR:', error)
            messages.error(
                request,
                'Razorpay rejected the subscription request. Please check the subscription settings.'
            )
            return redirect('worker_subscription_payment')

        except razorpay.errors.ServerError as error:
            print('RAZORPAY SERVER ERROR:', error)
            messages.error(
                request,
                'Razorpay server is temporarily unavailable. Please try again.'
            )
            return redirect('worker_subscription_payment')

        except Exception as error:
            print('RAZORPAY GENERAL ERROR:', error)
            messages.error(
                request,
                'Unable to start subscription payment. Please try again.'
            )
            return redirect('worker_subscription_payment')

    return render(
        request,
        'complaints/Worker_Folder/worker_subscription_payment.html',
        {
            'worker': worker,
            'subscription': subscription,
            'first_month_price': 49,
            'monthly_price': 149,
        }
    )


# =========================================================
# RAZORPAY WORKER SUBSCRIPTION WEBHOOK
# =========================================================

@csrf_exempt
@require_POST
def worker_subscription_webhook(request):
    webhook_secret = (
        getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        or os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
    )
    razorpay_key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    razorpay_key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

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