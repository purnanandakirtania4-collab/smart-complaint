from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

import uuid


def generate_tracking_id():
    return f"CMP-{uuid.uuid4().hex[:8].upper()}"


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
        ("Prefer not to say", "Prefer not to say"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_profile",
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        default="",
    )
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        default="",
    )
    address = models.TextField(
        blank=True,
        default="",
        max_length=500,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    pincode = models.CharField(
        max_length=6,
        blank=True,
        default="",
    )

    photo = models.ImageField(
        upload_to="user_profile_photos/",
        null=True,
        blank=True,
    )

    # Premium theme entitlement for normal users.
    # This can be switched by admin now and connected to a user payment plan later.
    is_premium = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username


class UserFollow(models.Model):
    """
    Community follow relationship for normal Smart Complaint users.

    follower  -> the user who follows
    following -> the user being followed
    """

    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following_links",
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_user_follow",
            ),
            models.CheckConstraint(
                check=~models.Q(follower=models.F("following")),
                name="prevent_self_follow",
            ),
        ]

    def __str__(self):
        return f"{self.follower.username} -> {self.following.username}"


class SupportRequest(models.Model):
    ISSUE_TYPE_CHOICES = [
        ("Complaint Issue", "Complaint Issue"),
        ("Worker Issue", "Worker Issue"),
        ("Payment Issue", "Payment Issue"),
        ("Account Issue", "Account Issue"),
        ("Technical Problem", "Technical Problem"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="support_requests",
    )
    issue_type = models.CharField(
        max_length=50,
        choices=ISSUE_TYPE_CHOICES,
    )
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=2000)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.issue_type} - {self.subject}"


class WorkerProfile(models.Model):
    EXPERIENCE_CHOICES = [
        ("1 Month", "1 Month"),
        ("2 Months", "2 Months"),
        ("3 Months", "3 Months"),
        ("6 Months", "6 Months"),
        ("1 Year", "1 Year"),
        ("2 Years", "2 Years"),
        ("3 Years", "3 Years"),
        ("4 Years", "4 Years"),
        ("5 Years", "5 Years"),
        ("More than 5 Years", "More than 5 Years"),
    ]

    SKILL_CHOICES = [
        ("Electrician", "Electrician"),
        ("Plumber", "Plumber"),
        ("Carpenter", "Carpenter"),
        ("Cleaner", "Cleaner"),
        ("Painter", "Painter"),
        ("Mason", "Mason"),
        ("AC/Refrigeration", "AC / Refrigeration Technician"),
        ("Appliance Repair", "Appliance Repair Technician"),
        ("General Technician", "General Technician"),
        ("Other", "Other"),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ("Pending", "Pending Verification"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Suspended", "Suspended"),
    ]

    AVAILABILITY_STATUS_CHOICES = [
        ("available", "Available"),
        ("busy", "Busy"),
        ("offline", "Offline"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="worker_profile",
    )

    name = models.CharField(
        max_length=100,
        default="Unknown Worker",
    )

    phone = models.CharField(
        max_length=15,
        default="Not Provided",
    )

    experience = models.CharField(
        max_length=30,
        choices=EXPERIENCE_CHOICES,
        default="1 Year",
    )

    skill_category = models.CharField(
        max_length=50,
        choices=SKILL_CHOICES,
        default="General Technician",
    )

    photo = models.ImageField(
        upload_to="worker_profile_photos/",
        null=True,
        blank=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    area = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        default="",
    )

    # Only the last 4 digits are stored in the database.
    # The full Aadhaar number entered during registration is never saved.
    aadhaar_last4 = models.CharField(
        max_length=4,
        blank=True,
        default="",
    )

    aadhaar_front_photo = models.ImageField(
        upload_to="worker_verification/aadhaar_front/",
        null=True,
        blank=True,
    )

    aadhaar_back_photo = models.ImageField(
        upload_to="worker_verification/aadhaar_back/",
        null=True,
        blank=True,
    )

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="Approved",
    )

    admin_verification_note = models.TextField(
        blank=True,
        default="",
        max_length=1000,
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    probation_completed = models.BooleanField(
        default=False,
    )

    probation_target = models.PositiveSmallIntegerField(
        default=5,
    )

    worker_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        null=True,
        blank=True,
    )

    # New registrations are explicitly created with is_approved=False.
    # Existing approved workers remain safe during migration.
    is_approved = models.BooleanField(
        default=False,
    )

    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_STATUS_CHOICES,
        default="available",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def save(self, *args, **kwargs):
        if self.verification_status == "Approved":
            self.is_approved = True

            if not self.approved_at:
                self.approved_at = timezone.now()

            if not self.worker_id:
                self.worker_id = f"WRK-{uuid.uuid4().hex[:8].upper()}"

        else:
            self.is_approved = False

        super().save(*args, **kwargs)

    @property
    def completed_jobs_count(self):
        if not self.pk:
            return 0

        return self.assigned_complaints.filter(
            status="Resolved",
        ).count()

    @property
    def probation_remaining(self):
        remaining = (
            self.probation_target
            - self.completed_jobs_count
        )

        return max(
            remaining,
            0,
        )

    @property
    def masked_aadhaar(self):
        if not self.aadhaar_last4:
            return "Not Provided"

        return f"XXXX XXXX {self.aadhaar_last4}"

    def __str__(self):
        worker_label = (
            self.worker_id
            or "PENDING"
        )

        return f"{worker_label} - {self.name}"


class WorkerFollow(models.Model):
    """
    A logged-in Smart Complaint user can follow an approved worker.

    The follower can be either a normal citizen account or a worker account.
    A worker cannot follow their own WorkerProfile; that rule is enforced
    in the view because it spans the User and WorkerProfile tables.
    """

    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="worker_following_links",
    )
    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="social_followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "worker"],
                name="unique_worker_follow",
            ),
        ]

    def __str__(self):
        return f"{self.follower.username} -> {self.worker.name}"


class WorkerProfileLike(models.Model):
    """
    One profile appreciation/like per logged-in user per worker.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="liked_worker_profiles",
    )
    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="profile_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "worker"],
                name="unique_worker_profile_like",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} likes {self.worker.name}"


class WorkerPayoutDetails(models.Model):
    PAYOUT_METHOD_CHOICES = [
        ("upi", "UPI"),
        ("bank", "Bank Account"),
    ]

    worker = models.OneToOneField(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="payout_details",
    )

    payout_method = models.CharField(
        max_length=20,
        choices=PAYOUT_METHOD_CHOICES,
        blank=True,
        default="",
    )

    upi_id = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    account_holder_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    bank_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    # For safety, only the last 4 digits are stored locally.
    # Full bank account number is never stored in this model.
    bank_account_last4 = models.CharField(
        max_length=4,
        blank=True,
        default="",
    )

    ifsc_code = models.CharField(
        max_length=11,
        blank=True,
        default="",
    )

    is_verified = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def masked_bank_account(self):
        if not self.bank_account_last4:
            return ""

        return f"XXXXXX{self.bank_account_last4}"

    @property
    def display_summary(self):
        if self.payout_method == "upi":
            return self.upi_id or "UPI details not provided"

        if self.payout_method == "bank":
            if self.bank_account_last4:
                return f"{self.bank_name or 'Bank'} • {self.masked_bank_account}"

            return "Bank details not provided"

        return "Not configured"

    def __str__(self):
        return f"{self.worker.worker_id or 'PENDING'} - {self.get_payout_method_display() or 'Not configured'}"


class WorkerSubscription(models.Model):
    STATUS_CHOICES = [
        ("inactive", "Inactive"),
        ("pending", "Pending"),
        ("active", "Active"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    PLAN_CHOICES = [
        ("monthly", "Worker Pro Monthly"),
        ("four_month", "Worker Pro 4 Months"),
        ("yearly", "Worker Pro Yearly"),
    ]

    worker = models.OneToOneField(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="inactive")

    # Plan code is the durable entitlement identifier. Existing workers are
    # migrated to the current monthly Worker Pro plan by default.
    plan_code = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="monthly",
    )

    # Kept for backward compatibility with the existing admin/UI code.
    # For longer plans these fields store the first/upfront price and the
    # recurring renewal price, even though the old field names say monthly.
    first_month_price = models.PositiveIntegerField(default=49)
    monthly_price = models.PositiveIntegerField(default=149)
    razorpay_customer_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_subscription_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_plan_id = models.CharField(max_length=100, blank=True, default="")
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, default="1.0")
    started_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    next_billing_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    cancel_at_period_end = models.BooleanField(
        default=False,
    )

    last_gateway_status = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def plan_label(self):
        labels = {
            "monthly": "Worker Pro Monthly",
            "four_month": "Worker Pro 4 Months",
            "yearly": "Worker Pro Yearly",
        }
        return labels.get(self.plan_code, labels["monthly"])

    @property
    def billing_interval_months(self):
        return {
            "monthly": 1,
            "four_month": 4,
            "yearly": 12,
        }.get(self.plan_code, 1)

    @property
    def renewal_price(self):
        return {
            "monthly": 149,
            "four_month": 589,
            "yearly": 1769,
        }.get(self.plan_code, 149)

    @property
    def upfront_price(self):
        return {
            "monthly": 49,
            "four_month": 589,
            "yearly": 1769,
        }.get(self.plan_code, 49)

    @property
    def ai_credits_per_cycle(self):
        return {
            "monthly": 150,
            "four_month": 155,
            "yearly": 160,
        }.get(self.plan_code, 150)

    @property
    def billing_period_label(self):
        return {
            "monthly": "month",
            "four_month": "4 months",
            "yearly": "year",
        }.get(self.plan_code, "month")

    @property
    def is_premium_active(self):
        """Return True only while the worker subscription is usable."""
        now = timezone.now()

        if (
            self.cancel_at_period_end
            and self.current_period_end
            and self.current_period_end > now
        ):
            return True

        if self.status != "active":
            return False

        if (
            self.current_period_end
            and self.current_period_end <= now
        ):
            return False

        return True

    def __str__(self):
        return f"{self.worker.worker_id or 'PENDING'} - {self.status}"


class UserPremiumMembership(models.Model):
    """
    Citizen Premium is intentionally a prepaid 30-day pass.

    It does NOT auto-renew. A new verified Razorpay payment extends
    access by another 30 days and starts a fresh AI-credit cycle.
    """

    STATUS_CHOICES = [
        ("inactive", "Inactive"),
        ("active", "Active"),
        ("expired", "Expired"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="citizen_premium_membership",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="inactive",
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=79,
    )

    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    activated_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    last_paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    renewal_count = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def is_active(self):
        if self.status != "active":
            return False

        if not self.current_period_end:
            return False

        return self.current_period_end > timezone.now()

    @property
    def days_remaining(self):
        if not self.is_active:
            return 0

        seconds = (
            self.current_period_end
            - timezone.now()
        ).total_seconds()

        return max(
            int(
                (seconds + 86399)
                // 86400
            ),
            0,
        )

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.status} - "
            f"{self.current_period_end or 'No expiry'}"
        )


class AIMonthlyBudget(models.Model):
    """
    Internal AI safety ledger.

    This does not replace Google/Gemini billing controls.
    It gives Smart Complaint an app-side monthly spending guard.
    """

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(12),
        ]
    )

    budget_inr = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=100,
    )

    total_reserved_inr = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )
    total_spent_inr = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )

    free_reserved_inr = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )
    free_spent_inr = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "month"],
                name="unique_ai_monthly_budget",
            ),
        ]

    def __str__(self):
        return (
            f"AI Budget {self.year}-{self.month:02d} "
            f"₹{self.total_spent_inr}/₹{self.budget_inr}"
        )


class AIUsageLog(models.Model):
    FEATURE_CHOICES = [
        ("complaint_analysis", "Complaint Analysis"),
        ("translation", "Translation"),
        ("category_suggestion", "Category Suggestion"),
        ("detailed_analysis", "Detailed Complaint Analysis"),
        ("worker_summary", "Worker Complaint Summary"),
        ("worker_checklist", "Worker Work Checklist"),
        ("worker_reply", "Worker Reply Generator"),
        ("photo_analysis", "Photo Analysis"),
        ("help_chat", "AI Help Chat"),
    ]

    PLAN_CHOICES = [
        ("free", "Free Citizen"),
        ("citizen_premium", "Citizen Premium"),
        ("worker_free", "Free Worker"),
        ("worker_pro", "Worker Pro"),
    ]

    STATUS_CHOICES = [
        ("reserved", "Reserved"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_usage_logs",
    )

    feature = models.CharField(
        max_length=40,
        choices=FEATURE_CHOICES,
    )
    plan = models.CharField(
        max_length=30,
        choices=PLAN_CHOICES,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="reserved",
    )

    credit_cost = models.PositiveSmallIntegerField(
        default=1,
    )

    model_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    request_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    reserved_cost_inr = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )
    estimated_cost_inr = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )

    input_tokens = models.PositiveIntegerField(
        default=0,
    )
    output_tokens = models.PositiveIntegerField(
        default=0,
    )
    total_tokens = models.PositiveIntegerField(
        default=0,
    )

    # Only the safe structured AI result is cached here.
    # Raw complaint text / prompts are intentionally not stored.
    response_json = models.JSONField(
        null=True,
        blank=True,
    )

    error_code = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "status", "created_at"],
                name="ai_user_status_idx",
            ),
            models.Index(
                fields=["feature", "created_at"],
                name="ai_feature_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.feature} - "
            f"{self.status}"
        )


class Complaint(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("Resolved", "Resolved"),
    ]

    PRIORITY_CHOICES = [
        ("Normal", "Normal"),
        ("High", "High Priority"),
        ("Emergency", "Emergency"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaints",
    )
    tracking_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_tracking_id,
        editable=False,
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    description = models.TextField()

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="Normal",
    )

    photo = models.ImageField(
        upload_to="complaint_photos/",
        null=True,
        blank=True,
    )
    after_photo = models.ImageField(
        upload_to="complaint_after_photos/",
        null=True,
        blank=True,
    )
    after_photo_uploaded_at = models.DateTimeField(null=True, blank=True)

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    completion_otp = models.CharField(max_length=6, blank=True, default="")
    otp_created_at = models.DateTimeField(null=True, blank=True)
    otp_verified = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None

        if not is_new:
            old_status = (
                Complaint.objects
                .filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if is_new:
            ComplaintStatusHistory.objects.create(
                complaint=self,
                old_status="Pending",
                new_status="Pending",
            )
        elif old_status != self.status:
            ComplaintStatusHistory.objects.create(
                complaint=self,
                old_status=old_status or "Pending",
                new_status=self.status,
            )

    def __str__(self):
        return f"{self.tracking_id} - {self.subject}"


class ComplaintStatusHistory(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="history",
    )
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.complaint.tracking_id} : {self.old_status} → {self.new_status}"


class Rating(models.Model):
    RATING_TYPE_CHOICES = [
        ("user_to_worker", "User to Worker"),
        ("worker_to_user", "Worker to User"),
    ]

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rater = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="given_ratings",
    )
    rating_type = models.CharField(max_length=30, choices=RATING_TYPE_CHOICES)
    stars = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    problem = models.TextField(blank=True, default="", max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["complaint", "rating_type"],
                name="unique_complaint_rating_type",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.complaint.tracking_id} - {self.rating_type} - {self.stars} Stars"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ("status_update", "Status Update"),
        ("assignment", "Assignment"),
        ("otp", "OTP"),
        ("system", "System"),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPE_CHOICES,
        default="system",
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"


class DeviceToken(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("worker", "Worker"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    token = models.CharField(max_length=255, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class ChatMessage(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_chat_messages",
    )
    message = models.TextField(blank=True, default="", max_length=2000)
    image = models.ImageField(upload_to="chat_images/", null=True, blank=True)
    is_read = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    edit_count = models.PositiveSmallIntegerField(default=0)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    @property
    def can_edit(self):
        return self.edit_count < 1

    def __str__(self):
        return f"{self.complaint.tracking_id} - {self.sender.username}"


class PaymentTransaction(models.Model):
    PAYMENT_FOR_CHOICES = [
        ("complaint", "Complaint / Service"),
        ("worker_subscription", "Worker Subscription"),
        ("citizen_premium", "Citizen Premium"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("created", "Created"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
    ]

    payer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    worker_subscription = models.ForeignKey(
        WorkerSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )

    user_premium_membership = models.ForeignKey(
        UserPremiumMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )

    payment_for = models.CharField(
        max_length=30,
        choices=PAYMENT_FOR_CHOICES,
        default="other",
    )

    # Store money as Decimal, never float.
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(
        max_length=3,
        default="INR",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created",
    )

    # Gateway identifiers are safe to store.
    # Razorpay key secret/signature secret must NEVER be stored here.
    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )
    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )

    receipt = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payer", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.payer.username} - "
            f"{self.payment_for} - "
            f"{self.currency} {self.amount} - "
            f"{self.status}"
        )


class PaymentEvent(models.Model):
    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(
        max_length=100,
    )
    gateway_event_id = models.CharField(
        max_length=150,
        blank=True,
        default="",
        unique=True,
        null=True,
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_id} - {self.event_type}"
# =========================================================
# JOB MARKETPLACE
# =========================================================

class EmployerProfile(models.Model):
    """
    Shop / company profile used only for the Job Marketplace.

    Registration and verification are intentionally separate:
    creating this profile does not automatically make an employer verified.
    """

    BUSINESS_TYPE_CHOICES = [
        ("retail", "Retail Shop"),
        ("company", "Company / Office"),
        ("restaurant", "Restaurant"),
        ("warehouse", "Warehouse"),
        ("service", "Service Business"),
        ("other", "Other"),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending Verification"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employer_profile",
    )

    business_name = models.CharField(
        max_length=150,
    )

    business_type = models.CharField(
        max_length=30,
        choices=BUSINESS_TYPE_CHOICES,
        default="other",
    )

    contact_person = models.CharField(
        max_length=100,
    )

    business_phone = models.CharField(
        max_length=15,
        blank=True,
        default="",
    )

    business_email = models.EmailField(
        blank=True,
        default="",
    )

    address = models.TextField(
        blank=True,
        default="",
        max_length=500,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        default="",
    )

    about = models.TextField(
        blank=True,
        default="",
        max_length=2000,
    )

    logo = models.ImageField(
        upload_to="job_marketplace/employer_logos/",
        null=True,
        blank=True,
    )

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    gst_number = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    website_url = models.URLField(
        blank=True,
        default="",
    )

    verification_document = models.FileField(
        upload_to="job_marketplace/employer_verification/",
        null=True,
        blank=True,
    )

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    verification_note = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["business_name", "id"]
        indexes = [
            models.Index(
                fields=[
                    "verification_status",
                    "is_active",
                ]
            ),
            models.Index(
                fields=[
                    "city",
                    "is_active",
                ]
            ),
        ]

    @property
    def is_verified(self):
        return (
            self.is_active
            and self.verification_status == "approved"
        )

    def __str__(self):
        return self.business_name


class WorkerJobProfile(models.Model):
    """
    Job-marketplace preferences for an existing approved WorkerProfile.

    Keeping these fields separate means the civic complaint worker profile
    remains independent from private job-search preferences.
    """

    JOB_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("daily", "Daily Work"),
        ("any", "Any"),
    ]

    worker = models.OneToOneField(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="job_profile",
    )

    is_available_for_jobs = models.BooleanField(
        default=False,
        db_index=True,
    )

    headline = models.CharField(
        max_length=160,
        blank=True,
        default="",
    )

    bio = models.TextField(
        blank=True,
        default="",
        max_length=1500,
    )

    preferred_job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE_CHOICES,
        default="any",
    )

    preferred_city = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    preferred_area = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    expected_salary_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    expected_salary_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    linkedin_url = models.URLField(
        blank=True,
        default="",
    )

    show_linkedin_to_employers = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-is_available_for_jobs",
            "worker__name",
        ]

    def __str__(self):
        return (
            f"{self.worker.worker_id or 'PENDING'} "
            f"- Job Profile"
        )


class JobPost(models.Model):
    JOB_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("daily", "Daily Work"),
    ]

    SALARY_PERIOD_CHOICES = [
        ("hour", "Per Hour"),
        ("day", "Per Day"),
        ("week", "Per Week"),
        ("month", "Per Month"),
        ("year", "Per Year"),
        ("fixed", "Fixed Amount"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("paused", "Paused"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="job_posts",
    )

    title = models.CharField(
        max_length=160,
    )

    category = models.CharField(
        max_length=100,
        db_index=True,
    )

    required_skill = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE_CHOICES,
        default="full_time",
    )

    description = models.TextField(
        max_length=5000,
    )

    requirements = models.TextField(
        blank=True,
        default="",
        max_length=3000,
    )

    salary_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    salary_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    salary_period = models.CharField(
        max_length=20,
        choices=SALARY_PERIOD_CHOICES,
        default="month",
    )

    salary_is_negotiable = models.BooleanField(
        default=False,
    )

    vacancies = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    location_name = models.CharField(
        max_length=200,
    )

    city = models.CharField(
        max_length=100,
        db_index=True,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        default="",
    )

    work_timing = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    weekly_off = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    joining_note = models.CharField(
        max_length=160,
        blank=True,
        default="",
    )

    experience_required = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "created_at",
                ]
            ),
            models.Index(
                fields=[
                    "city",
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "category",
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "employer",
                    "status",
                ]
            ),
        ]

    @property
    def is_open_for_applications(self):
        if self.status != "published":
            return False

        if (
            self.expires_at
            and self.expires_at <= timezone.now()
        ):
            return False

        return True

    @property
    def salary_display(self):
        if (
            self.salary_min is None
            and self.salary_max is None
        ):
            return (
                "Negotiable"
                if self.salary_is_negotiable
                else "Not disclosed"
            )

        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min != self.salary_max
        ):
            amount = (
                f"₹{self.salary_min:,.0f} - "
                f"₹{self.salary_max:,.0f}"
            )

        else:
            value = (
                self.salary_min
                if self.salary_min is not None
                else self.salary_max
            )

            amount = (
                f"₹{value:,.0f}"
                if value is not None
                else ""
            )

        period_map = {
            "hour": "hour",
            "day": "day",
            "week": "week",
            "month": "month",
            "year": "year",
            "fixed": "job",
        }

        period = period_map.get(
            self.salary_period,
            self.salary_period,
        )

        if amount:
            return f"{amount} / {period}"

        return "Negotiable"

    def __str__(self):
        return (
            f"{self.title} - "
            f"{self.employer.business_name}"
        )


class SavedJob(models.Model):
    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="saved_jobs",
    )

    job = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        related_name="saved_by_workers",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "worker",
                    "job",
                ],
                name="unique_saved_job_per_worker",
            ),
        ]

    def __str__(self):
        return (
            f"{self.worker.worker_id or 'PENDING'} "
            f"saved {self.job.title}"
        )


class JobApplication(models.Model):
    STATUS_CHOICES = [
        ("applied", "Applied"),
        ("shortlisted", "Shortlisted"),
        ("interview", "Interview"),
        ("offer_received", "Offer Received"),
        ("hired", "Hired"),
        ("rejected", "Not Selected"),
        ("withdrawn", "Withdrawn"),
    ]

    job = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        related_name="applications",
    )

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="job_applications",
    )

    cover_note = models.TextField(
        blank=True,
        default="",
        max_length=1500,
    )

    expected_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="applied",
        db_index=True,
    )

    employer_note = models.TextField(
        blank=True,
        default="",
        max_length=1500,
    )

    interview_scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
    )

    interview_location = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    interview_note = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    applied_at = models.DateTimeField(
        auto_now_add=True,
    )

    shortlisted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    hired_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    withdrawn_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-applied_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "job",
                    "worker",
                ],
                name="unique_worker_job_application",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "job",
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "worker",
                    "status",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.worker.name} -> "
            f"{self.job.title} "
            f"({self.status})"
        )


class JobOffer(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("withdrawn", "Withdrawn"),
        ("expired", "Expired"),
    ]

    application = models.OneToOneField(
        JobApplication,
        on_delete=models.CASCADE,
        related_name="offer",
    )

    salary_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    salary_period = models.CharField(
        max_length=20,
        choices=JobPost.SALARY_PERIOD_CHOICES,
        default="month",
    )

    joining_date = models.DateField(
        null=True,
        blank=True,
    )

    shift = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    work_location = models.CharField(
        max_length=255,
    )

    terms = models.TextField(
        max_length=4000,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    sent_at = models.DateTimeField(
        auto_now_add=True,
    )

    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-sent_at",
        ]

    @property
    def is_actionable(self):
        if self.status != "pending":
            return False

        if (
            self.expires_at
            and self.expires_at <= timezone.now()
        ):
            return False

        return True

    def __str__(self):
        return (
            f"Offer: "
            f"{self.application.worker.name} - "
            f"{self.application.job.title}"
        )


class JobEmployment(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("ended", "Ended"),
    ]

    application = models.OneToOneField(
        JobApplication,
        on_delete=models.PROTECT,
        related_name="employment",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )

    started_at = models.DateTimeField(
        default=timezone.now,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ended_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    end_note = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-started_at",
        ]

    @property
    def worker(self):
        return self.application.worker

    @property
    def employer(self):
        return self.application.job.employer

    @property
    def job(self):
        return self.application.job

    def __str__(self):
        return (
            f"{self.application.worker.name} - "
            f"{self.application.job.title}"
        )


class JobChatMessage(models.Model):
    application = models.ForeignKey(
        JobApplication,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_job_chat_messages",
    )

    message = models.TextField(
        blank=True,
        default="",
        max_length=2000,
    )

    attachment = models.FileField(
        upload_to="job_marketplace/chat_attachments/",
        null=True,
        blank=True,
    )

    is_read = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "application",
                    "created_at",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.application.job.title} - "
            f"{self.sender.username}"
        )


class JobReview(models.Model):
    REVIEW_TYPE_CHOICES = [
        ("employer_to_worker", "Employer to Worker"),
        ("worker_to_employer", "Worker to Employer"),
    ]

    employment = models.ForeignKey(
        JobEmployment,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="given_job_reviews",
    )

    review_type = models.CharField(
        max_length=30,
        choices=REVIEW_TYPE_CHOICES,
    )

    stars = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ]
    )

    comment = models.TextField(
        blank=True,
        default="",
        max_length=1500,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "employment",
                    "review_type",
                ],
                name="unique_job_review_type",
            ),
        ]

    def __str__(self):
        return (
            f"{self.employment.application.job.title} - "
            f"{self.review_type} - "
            f"{self.stars} stars"
        )
