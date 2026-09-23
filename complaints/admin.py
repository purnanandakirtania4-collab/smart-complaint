from django.contrib import admin
from django.utils import timezone

from .models import (
    UserProfile,
    WorkerProfile,
    WorkerSubscription,
    Complaint,
    ComplaintStatusHistory,
    Rating,
    Notification,
    DeviceToken,
    ChatMessage,
    EmployerProfile,
)


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "worker_id",
        "skill_category",
        "verification_status",
        "is_approved",
        "probation_completed",
        "created_at",
    )

    list_filter = (
        "verification_status",
        "is_approved",
        "probation_completed",
        "skill_category",
        "experience",
        "city",
    )

    search_fields = (
        "name",
        "worker_id",
        "user__username",
        "user__email",
        "phone",
        "city",
        "area",
        "pincode",
        "aadhaar_last4",
    )

    readonly_fields = (
        "worker_id",
        "is_approved",
        "approved_at",
        "created_at",
        "aadhaar_last4",
    )

    actions = (
        "approve_selected_workers",
        "reject_selected_workers",
        "suspend_selected_workers",
        "mark_selected_workers_pending",
    )

    fieldsets = (
        (
            "Worker Account",
            {
                "fields": (
                    "user",
                    "worker_id",
                    "name",
                    "phone",
                    "photo",
                )
            },
        ),
        (
            "Work Details",
            {
                "fields": (
                    "skill_category",
                    "experience",
                    "city",
                    "area",
                    "pincode",
                )
            },
        ),
        (
            "Aadhaar Verification",
            {
                "fields": (
                    "aadhaar_last4",
                    "aadhaar_front_photo",
                    "aadhaar_back_photo",
                )
            },
        ),
        (
            "Verification Control",
            {
                "fields": (
                    "verification_status",
                    "is_approved",
                    "admin_verification_note",
                    "approved_at",
                )
            },
        ),
        (
            "Probation",
            {
                "fields": (
                    "probation_completed",
                    "probation_target",
                )
            },
        ),
        (
            "System",
            {
                "fields": (
                    "created_at",
                )
            },
        ),
    )

    @admin.action(
        description="Approve selected workers"
    )
    def approve_selected_workers(
        self,
        request,
        queryset,
    ):
        count = 0

        for worker in queryset:
            worker.verification_status = "Approved"
            worker.save()
            count += 1

        self.message_user(
            request,
            f"{count} worker(s) approved successfully.",
        )

    @admin.action(
        description="Reject selected workers"
    )
    def reject_selected_workers(
        self,
        request,
        queryset,
    ):
        count = 0

        for worker in queryset:
            worker.verification_status = "Rejected"
            worker.save()
            count += 1

        self.message_user(
            request,
            f"{count} worker(s) rejected.",
        )

    @admin.action(
        description="Suspend selected workers"
    )
    def suspend_selected_workers(
        self,
        request,
        queryset,
    ):
        count = 0

        for worker in queryset:
            worker.verification_status = "Suspended"
            worker.save()
            count += 1

        self.message_user(
            request,
            f"{count} worker(s) suspended.",
        )

    @admin.action(
        description="Move selected workers to Pending Verification"
    )
    def mark_selected_workers_pending(
        self,
        request,
        queryset,
    ):
        count = 0

        for worker in queryset:
            worker.verification_status = "Pending"
            worker.save()
            count += 1

        self.message_user(
            request,
            f"{count} worker(s) moved to pending verification.",
        )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "phone",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "phone",
    )


@admin.register(WorkerSubscription)
class WorkerSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "worker",
        "status",
        "first_month_price",
        "monthly_price",
        "next_billing_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "terms_accepted",
    )

    search_fields = (
        "worker__worker_id",
        "worker__name",
        "worker__user__username",
        "razorpay_subscription_id",
    )


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_id",
        "subject",
        "user",
        "assigned_worker",
        "priority",
        "status",
        "created_at",
    )

    list_filter = (
        "priority",
        "status",
        "created_at",
    )

    search_fields = (
        "tracking_id",
        "subject",
        "name",
        "email",
        "user__username",
        "assigned_worker__worker_id",
        "assigned_worker__name",
    )


@admin.register(ComplaintStatusHistory)
class ComplaintStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "complaint",
        "old_status",
        "new_status",
        "changed_at",
    )

    list_filter = (
        "old_status",
        "new_status",
    )


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = (
        "complaint",
        "rating_type",
        "rater",
        "stars",
        "created_at",
    )

    list_filter = (
        "rating_type",
        "stars",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "notification_type",
        "title",
        "is_read",
        "created_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
    )

    search_fields = (
        "recipient__username",
        "title",
        "message",
    )


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "role",
        "is_active",
    )

    search_fields = (
        "user__username",
        "token",
    )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "complaint",
        "sender",
        "is_read",
        "is_edited",
        "created_at",
    )

    list_filter = (
        "is_read",
        "is_edited",
    )

    search_fields = (
        "complaint__tracking_id",
        "sender__username",
        "message",
    )



@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "business_type",
        "contact_person",
        "city",
        "verification_status",
        "is_active",
        "created_at",
    )

    list_filter = (
        "business_type",
        "verification_status",
        "is_active",
        "city",
        "state",
    )

    search_fields = (
        "business_name",
        "contact_person",
        "user__username",
        "business_email",
        "business_phone",
        "registration_number",
        "gst_number",
        "city",
        "pincode",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "verified_at",
    )

    actions = (
        "approve_selected_employers",
        "reject_selected_employers",
        "suspend_selected_employers",
        "mark_selected_employers_pending",
    )

    fieldsets = (
        (
            "Account",
            {
                "fields": (
                    "user",
                    "business_name",
                    "business_type",
                    "contact_person",
                    "business_phone",
                    "business_email",
                    "logo",
                )
            },
        ),
        (
            "Business Address",
            {
                "fields": (
                    "address",
                    "city",
                    "state",
                    "pincode",
                )
            },
        ),
        (
            "Business Details",
            {
                "fields": (
                    "registration_number",
                    "gst_number",
                    "website_url",
                    "about",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "verification_document",
                    "verification_status",
                    "verification_note",
                    "verified_at",
                    "is_active",
                )
            },
        ),
        (
            "System",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.action(
        description="Approve selected employers"
    )
    def approve_selected_employers(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            verification_status="approved",
            verified_at=timezone.now(),
            is_active=True,
        )
        self.message_user(
            request,
            f"{count} employer(s) approved.",
        )

    @admin.action(
        description="Reject selected employers"
    )
    def reject_selected_employers(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            verification_status="rejected",
            verified_at=None,
        )
        self.message_user(
            request,
            f"{count} employer(s) rejected.",
        )

    @admin.action(
        description="Suspend selected employers"
    )
    def suspend_selected_employers(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            verification_status="suspended",
            is_active=False,
            verified_at=None,
        )
        self.message_user(
            request,
            f"{count} employer(s) suspended.",
        )

    @admin.action(
        description="Move selected employers to Pending Verification"
    )
    def mark_selected_employers_pending(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            verification_status="pending",
            verified_at=None,
            is_active=True,
        )
        self.message_user(
            request,
            f"{count} employer(s) moved to pending verification.",
        )
