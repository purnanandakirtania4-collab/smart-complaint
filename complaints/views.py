from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.files.storage import default_storage

from .models import (
    Complaint,
    WorkerProfile,
    UserProfile,
)


# =========================================================
# HOME
# =========================================================

@login_required(login_url='login')
def home(request):

    return render(
        request,
        'complaints/home.html'
    )


# =========================================================
# USER LOGIN
# =========================================================

def user_login(request):

    if request.user.is_authenticated:

        try:
            request.user.worker_profile
            return redirect('worker_dashboard')

        except WorkerProfile.DoesNotExist:
            return redirect('home')

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

            return redirect('login')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            # Worker ko normal user login se login nahi karayenge
            try:
                user.worker_profile

                messages.error(
                    request,
                    'Worker account detected. Please use Worker Login.'
                )

                return redirect('worker_login')

            except WorkerProfile.DoesNotExist:
                pass

            login(
                request,
                user
            )

            return redirect('home')

        messages.error(
            request,
            'Invalid username or password.'
        )

        return redirect('login')

    return render(
        request,
        'complaints/login_register.html'
    )


# =========================================================
# USER REGISTER
# =========================================================

def register(request):

    if request.method != 'POST':
        return redirect('login')

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

        return redirect('login')

    if User.objects.filter(
        username=username
    ).exists():

        messages.error(
            request,
            'Username already exists.'
        )

        return redirect('login')

    if User.objects.filter(
        email=email
    ).exists():

        messages.error(
            request,
            'This email is already registered.'
        )

        return redirect('login')

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

    return redirect('login')


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

            return redirect('profile')

        if (
            User.objects
            .filter(email=email)
            .exclude(id=user.id)
            .exists()
        ):

            messages.error(
                request,
                'This email is already registered.'
            )

            return redirect('profile')

        if phone and len(phone) > 15:

            messages.error(
                request,
                'Phone number is too long.'
            )

            return redirect('profile')

        if photo:

            if photo.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    'Profile photo must be less than 5 MB.'
                )

                return redirect('profile')

            if not photo.content_type.startswith(
                'image/'
            ):

                messages.error(
                    request,
                    'Please select a valid image.'
                )

                return redirect('profile')

            if user_profile.photo:

                old_photo = user_profile.photo.name

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

        return redirect('profile')

    return render(
        request,
        'complaints/profile.html',
        {
            'profile_user': user,
            'user_profile': user_profile,
        }
    )


# =========================================================
# USER LOGOUT
# =========================================================

def user_logout(request):

    logout(request)

    return redirect('login')


# =========================================================
# SUBMIT COMPLAINT
# NO PAYMENT - DIRECT SUBMIT
# =========================================================

@login_required(login_url='login')
def submit_complaint(request):

    workers = (
        WorkerProfile.objects
        .filter(is_approved=True)
        .select_related('user')
        .order_by('-created_at')
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

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

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
                'complaints/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        # -------------------------------------------------
        # LOCATION VALIDATION
        # -------------------------------------------------

        if not latitude or not longitude:

            messages.error(
                request,
                'Please select complaint location.'
            )

            return render(
                request,
                'complaints/submit_complaint.html',
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

        except (ValueError, TypeError):

            messages.error(
                request,
                'Invalid complaint location.'
            )

            return render(
                request,
                'complaints/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        # -------------------------------------------------
        # PHOTO VALIDATION
        # -------------------------------------------------

        if not photo:

            messages.error(
                request,
                'Please upload complaint photo.'
            )

            return render(
                request,
                'complaints/submit_complaint.html',
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
                'complaints/submit_complaint.html',
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
                'complaints/submit_complaint.html',
                {
                    'workers': workers
                }
            )

        # -------------------------------------------------
        # WORKER
        # -------------------------------------------------

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
                    'complaints/submit_complaint.html',
                    {
                        'workers': workers
                    }
                )

        # -------------------------------------------------
        # DIRECT COMPLAINT SAVE
        # -------------------------------------------------

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
            'complaints/success.html',
            {
                'complaint': complaint
            }
        )

    return render(
        request,
        'complaints/submit_complaint.html',
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
        'complaints/success.html'
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
        'complaints/check_status.html',
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

    complaints = (
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

    return render(
        request,
        'complaints/my_complaints.html',
        {
            'complaints': complaints
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
        'complaints/worker_details.html',
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
            .select_related('user')
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
            .filter(email=email)
            .exclude(id=worker.user.id)
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

                old_photo = worker.photo.name

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
        'complaints/worker_profile.html',
        {
            'worker': worker,
            'is_owner': is_owner,
            'experience_choices':
                WorkerProfile.EXPERIENCE_CHOICES,
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
        'complaints/worker_register.html',
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

            worker = request.user.worker_profile

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

            worker = user.worker_profile

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
        'complaints/worker_login.html'
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

    # -----------------------------------------------------
    # UPDATE COMPLAINT STATUS
    # -----------------------------------------------------

    if request.method == 'POST':

        complaint_id = request.POST.get(
            'complaint_id',
            ''
        ).strip()

        new_status = request.POST.get(
            'status',
            ''
        ).strip()

        valid_statuses = [
            'Pending',
            'In Progress',
            'Resolved',
        ]

        if not complaint_id:

            messages.error(
                request,
                'Complaint not found.'
            )

            return redirect(
                'worker_dashboard'
            )

        if new_status not in valid_statuses:

            messages.error(
                request,
                'Invalid complaint status.'
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

        if complaint.status == new_status:

            messages.info(
                request,
                f'Complaint is already {new_status}.'
            )

            return redirect(
                'worker_dashboard'
            )

        complaint.status = new_status

        complaint.save()

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

    # -----------------------------------------------------
    # ASSIGNED COMPLAINTS
    # -----------------------------------------------------

    complaints = (
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

    return render(
        request,
        'complaints/worker_dashboard.html',
        {
            'worker': worker,
            'complaints': complaints,
        }
    )


# =========================================================
# WORKER LOGOUT
# =========================================================

def worker_logout(request):

    logout(request)

    return redirect(
        'worker_login'
    )