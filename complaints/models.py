from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

import uuid


# =========================================================
# TRACKING ID GENERATOR
# =========================================================

def generate_tracking_id():
    return f"CMP-{uuid.uuid4().hex[:8].upper()}"


# =========================================================
# USER PROFILE
# =========================================================

class UserProfile(models.Model):

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

    photo = models.ImageField(
        upload_to="user_profile_photos/",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.user.username


# =========================================================
# WORKER PROFILE
# =========================================================

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

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="worker_profile",
    )

    name = models.CharField(
        max_length=100,
        default="Unknown Worker"
    )

    phone = models.CharField(
        max_length=15,
        default="Not Provided"
    )

    experience = models.CharField(
        max_length=30,
        choices=EXPERIENCE_CHOICES,
        default="1 Year",
    )

    photo = models.ImageField(
        upload_to="worker_profile_photos/",
        null=True,
        blank=True,
    )

    # =====================================================
    # WORKER SERVICE LOCATION
    # =====================================================

    city = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    area = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        default=""
    )

    worker_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    is_approved = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        if not self.worker_id:

            self.worker_id = (
                f"WRK-{uuid.uuid4().hex[:8].upper()}"
            )

        super().save(
            *args,
            **kwargs
        )

    def __str__(self):

        return (
            f"{self.worker_id} - {self.name}"
        )


# =========================================================
# COMPLAINT
# =========================================================

class Complaint(models.Model):

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("Resolved", "Resolved"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

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

    name = models.CharField(
        max_length=100
    )

    email = models.EmailField()

    subject = models.CharField(
        max_length=200
    )

    description = models.TextField()

    photo = models.ImageField(
        upload_to="complaint_photos/",
        null=True,
        blank=True,
    )

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

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):

        is_new = self.pk is None

        old_status = None

        if not is_new:

            old_status = (
                Complaint.objects
                .filter(pk=self.pk)
                .values_list(
                    "status",
                    flat=True
                )
                .first()
            )

        super().save(
            *args,
            **kwargs
        )

        if is_new:

            ComplaintStatusHistory.objects.create(
                complaint=self,
                old_status="Pending",
                new_status="Pending",
            )

        elif old_status != self.status:

            ComplaintStatusHistory.objects.create(
                complaint=self,
                old_status=(
                    old_status or "Pending"
                ),
                new_status=self.status,
            )

    def __str__(self):

        return (
            f"{self.tracking_id} - "
            f"{self.subject}"
        )


# =========================================================
# COMPLAINT STATUS HISTORY
# =========================================================

class ComplaintStatusHistory(models.Model):

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="history",
    )

    old_status = models.CharField(
        max_length=20
    )

    new_status = models.CharField(
        max_length=20
    )

    changed_at = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):

        return (
            f"{self.complaint.tracking_id} : "
            f"{self.old_status} → "
            f"{self.new_status}"
        )