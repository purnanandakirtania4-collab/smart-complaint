import calendar
import secrets
from datetime import timedelta

import razorpay

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db.models import Avg, Count
from django.utils import timezone

from .models import (
    Complaint,
    WorkerProfile,
    UserProfile,
    Rating,
    WorkerSubscription,
    Notification,
)


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
# HOME
# =========================================================

@login_required(login_url='login')
def home(request):

    return render(
        request,
        'complaints/User_Folder/home.html'
    )


# =========================================================
# USER LOGIN
# =========================================================

def user_login(request):

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

        photo = request.FILES.get(
            'photo'
        )

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

        user.first_name = first_name
        user.last_name = last_name
        user.email = email

        user.save()

        user_profile.phone = phone
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
        }
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
# SUBMIT COMPLAINT
# =========================================================

@login_required(login_url='login')
def submit_complaint(request):

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

    if request.method == 'POST':

        name = request.POST.get(
            'name',
            ''
        ).strip()

        email = request.POST.get(
            'email',
            ''
        ).strip()

        subject = request.POST.get(
            'subject',
            ''
        ).strip()

        description = request.POST.get(
            'description',
            ''
        ).strip()

        worker_id = request.POST.get(
            'worker',
            ''
        ).strip()

        latitude = request.POST.get(
            'latitude',
            ''
        ).strip()

        longitude = request.POST.get(
            'longitude',
            ''
        ).strip()

        photo = request.FILES.get(
            'photo'
        )

        if (
            not name
            or not email
            or not subject
            or not description
        ):

            messages.error(
                request,
                'Please fill all complaint fields.'
            )

            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        if not latitude or not longitude:

            messages.error(
                request,
                'Please select complaint location.'
            )

            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        try:

            latitude_value = float(
                latitude
            )

            longitude_value = float(
                longitude
            )

            if not (
                -90 <= latitude_value <= 90
                and
                -180 <= longitude_value <= 180
            ):

                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            messages.error(
                request,
                'Invalid complaint location.'
            )

            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        if not photo:

            messages.error(
                request,
                'Please upload complaint photo.'
            )

            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        if photo.size > 5 * 1024 * 1024:

            messages.error(
                request,
                'Complaint photo must be less than 5 MB.'
            )

            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        if not photo.content_type.startswith(
            'image/'
        ):

            messages.error(
                request,
                'Please upload a valid image.'
            )

            return render(
                request,
                'complaints/User_Folder/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        selected_worker = None

        if worker_id:

            try:

                selected_worker = (
                    WorkerProfile.objects.get(
                        id=worker_id,
                        is_approved=True
                    )
                )

            except (
                WorkerProfile.DoesNotExist,
                ValueError,
                TypeError
            ):

                messages.error(
                    request,
                    'Selected worker is not available.'
                )

                return render(
                    request,
                    'complaints/User_Folder/submit_complaint.html',
                    {
                        'workers': workers
                    }
                )

        complaint = Complaint.objects.create(
            user=request.user,
            assigned_worker=selected_worker,
            name=name,
            email=email,
            subject=subject,
            description=description,
            photo=photo,
            latitude=latitude,
            longitude=longitude,
            status='Pending',
        )

        messages.success(
            request,
            'Complaint submitted successfully.'
        )

        return render(
            request,
            'complaints/User_Folder/success.html',
            {
                'complaint': complaint
            }
        )

    return render(
        request,
        'complaints/User_Folder/submit_complaint.html',
        {
            'workers': workers
        }
    )


# =========================================================
# SUCCESS PAGE
# =========================================================

@login_required(login_url='login')
def success(request):

    return render(
        request,
        'complaints/User_Folder/success.html'
    )


# =========================================================
# CHECK COMPLAINT STATUS
# =========================================================

def check_status(request):

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
        'complaints/Worker_Folder/worker_details.html',
        {
            'workers': workers
        }
    )


# =========================================================
# WORKER PROFILE
# =========================================================

@login_required(login_url='login')
def worker_profile(request, worker_id):

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

        password = request.POST.get(
            'password',
            ''
        )

        if (
            not username
            or not email
            or not phone
            or not name
            or not experience
            or not password
        ):

            messages.error(
                request,
                'Please fill all worker registration fields.'
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
            is_approved=True
        )

        messages.success(
            request,
            'Worker registration successful. Please login.'
        )

        return redirect(
            'worker_login'
        )

    return render(
        request,
        'complaints/Worker_Folder/worker_register.html',
        {
            'experience_choices':
                WorkerProfile.EXPERIENCE_CHOICES
        }
    )


# =========================================================
# WORKER LOGIN
# =========================================================

def worker_login(request):

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

        worker = (
            request.user.worker_profile
        )

    except WorkerProfile.DoesNotExist:

        messages.error(
            request,
            'Worker access required.'
        )

        logout(
            request
        )

        return redirect(
            'worker_login'
        )

    if not worker.is_approved:

        messages.error(
            request,
            'Your worker account is not approved.'
        )

        logout(
            request
        )

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

            complaint = (
                Complaint.objects.get(
                    id=complaint_id,
                    assigned_worker=worker
                )
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

            messages.success(
                request,
                (
                    f'OTP verified successfully. '
                    f'Complaint {complaint.tracking_id} is now Resolved.'
                )
            )

            return redirect(
                'worker_dashboard'
            )

        # =====================================================
        # NORMAL STATUS UPDATE
        # =====================================================

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

        # =====================================================
        # RESOLVED REQUIRES USER OTP
        # =====================================================

        if new_status == 'Resolved':

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

                complaint.otp_created_at = (
                    timezone.now()
                )

                complaint.otp_verified = False

                complaint.save(
                    update_fields=[
                        'completion_otp',
                        'otp_created_at',
                        'otp_verified',
                        'updated_at',
                    ]
                )

                Notification.objects.create(
                    recipient=complaint.user,
                    complaint=complaint,
                    notification_type='otp',
                    title='Completion OTP Ready',
                    message=(
                        f'Worker requested completion for complaint '
                        f'{complaint.tracking_id}. '
                        f'Open My Complaints to view the OTP. '
                        f'The OTP is valid for 10 minutes.'
                    ),
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

        # Moving back to Pending / In Progress invalidates any old OTP.
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

    complaints = list(
        Complaint.objects
        .filter(
            assigned_worker=worker
        )
        .select_related(
            'user'
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

    return render(
        request,
        'complaints/Worker_Folder/worker_settings.html',
        {
            'worker': worker,
            'subscription': subscription,
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
# WORKER SUBSCRIPTION PAYMENT
# ₹49 NOW + ₹149/MONTH FROM NEXT MONTH
# =========================================================

@login_required(login_url='worker_login')
def worker_subscription_payment(request):

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

    if not subscription.terms_accepted:

        messages.error(
            request,
            'Please accept the Terms & Conditions first.'
        )

        return redirect(
            'terms_conditions'
        )

    # =====================================================
    # CREATE RAZORPAY SUBSCRIPTION
    # =====================================================

    if request.method == 'POST':

        razorpay_key_id = getattr(
            settings,
            'RAZORPAY_KEY_ID',
            ''
        )

        razorpay_key_secret = getattr(
            settings,
            'RAZORPAY_KEY_SECRET',
            ''
        )

        razorpay_plan_id = getattr(
            settings,
            'RAZORPAY_WORKER_PLAN_ID',
            ''
        )

        if (
            not razorpay_key_id
            or not razorpay_key_secret
            or not razorpay_plan_id
        ):

            messages.error(
                request,
                'Razorpay subscription configuration is missing.'
            )

            return redirect(
                'worker_subscription_payment'
            )

        try:

            client = razorpay.Client(
                auth=(
                    razorpay_key_id,
                    razorpay_key_secret
                )
            )

            # =================================================
            # REUSE EXISTING SUBSCRIPTION
            # =================================================

            if (
                subscription
                .razorpay_subscription_id
            ):

                try:

                    existing_subscription = (
                        client.subscription.fetch(
                            subscription
                            .razorpay_subscription_id
                        )
                    )

                    razorpay_status = (
                        existing_subscription.get(
                            'status',
                            ''
                        )
                    )

                    short_url = (
                        existing_subscription.get(
                            'short_url'
                        )
                    )

                    if (
                        razorpay_status
                        in [
                            'created',
                            'authenticated',
                            'active',
                            'pending',
                            'halted',
                        ]
                        and short_url
                    ):

                        return redirect(
                            short_url
                        )

                except Exception:
                    pass

            # =================================================
            # ₹149 BILLING STARTS AFTER ONE MONTH
            # =================================================

            now = (
                timezone.now()
            )

            first_regular_billing_date = (
                add_one_month(
                    now
                )
            )

            start_at_timestamp = int(
                first_regular_billing_date
                .timestamp()
            )

            # =================================================
            # CREATE RAZORPAY SUBSCRIPTION
            # =================================================

            razorpay_subscription = (
                client.subscription.create(
                    {
                        'plan_id':
                            razorpay_plan_id,

                        'total_count':
                            12,

                        'quantity':
                            1,

                        'customer_notify':
                            True,

                        'start_at':
                            start_at_timestamp,

                        'addons': [
                            {
                                'item': {
                                    'name':
                                        'First Month Subscription Fee',

                                    'amount':
                                        4900,

                                    'currency':
                                        'INR',
                                }
                            }
                        ],

                        'notes': {
                            'worker_id':
                                str(worker.id),

                            'worker_name':
                                worker.name,

                            'django_user_id':
                                str(request.user.id),

                            'subscription_type':
                                'worker_monthly',
                        },
                    }
                )
            )

            razorpay_subscription_id = (
                razorpay_subscription.get(
                    'id',
                    ''
                )
            )

            razorpay_short_url = (
                razorpay_subscription.get(
                    'short_url',
                    ''
                )
            )

            if not razorpay_subscription_id:

                messages.error(
                    request,
                    'Razorpay did not return a subscription ID.'
                )

                return redirect(
                    'worker_subscription_payment'
                )

            # =================================================
            # SAVE SUBSCRIPTION
            # =================================================

            subscription.razorpay_subscription_id = (
                razorpay_subscription_id
            )

            subscription.razorpay_plan_id = (
                razorpay_plan_id
            )

            subscription.first_month_price = 49
            subscription.monthly_price = 149
            subscription.status = 'pending'

            subscription.next_billing_at = (
                first_regular_billing_date
            )

            subscription.save()

            # =================================================
            # OPEN RAZORPAY PAYMENT PAGE
            # =================================================

            if razorpay_short_url:

                return redirect(
                    razorpay_short_url
                )

            messages.success(
                request,
                'Subscription created successfully.'
            )

            return redirect(
                'worker_subscription_payment'
            )

        except razorpay.errors.BadRequestError as e:

            print("RAZORPAY BAD REQUEST ERROR:", e)

            messages.error(
                request,
                'Razorpay rejected the subscription request. Please check the subscription settings.'
            )

            return redirect(
                'worker_subscription_payment'
            )

        except razorpay.errors.ServerError as e:

            print("RAZORPAY SERVER ERROR:", e)

            messages.error(
                request,
                'Razorpay server is temporarily unavailable. Please try again.'
            )

            return redirect(
                'worker_subscription_payment'
            )

        except Exception as e:

            print("RAZORPAY GENERAL ERROR:", e)

            messages.error(
                request,
                'Unable to start subscription payment. Please try again.'
            )

            return redirect(
                'worker_subscription_payment'
            )

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