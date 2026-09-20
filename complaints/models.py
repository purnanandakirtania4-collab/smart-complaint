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

    worker = models.OneToOneField(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="inactive")
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_premium_active(self):
        """Return True only while the worker subscription is usable."""
        if self.status != "active":
            return False

        if self.current_period_end and self.current_period_end <= timezone.now():
            return False

        return True

    def __str__(self):
        return f"{self.worker.worker_id or 'PENDING'} - {self.status}"


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
