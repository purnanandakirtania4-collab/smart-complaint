from django.contrib import admin

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
