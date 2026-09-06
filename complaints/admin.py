from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Complaint, ComplaintStatusHistory, WorkerProfile


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "worker_id",
        "name",
        "user",
        "phone",
        "experience",
        "is_approved",
        "created_at",
    )
    list_filter = ("is_approved", "experience", "created_at")
    search_fields = (
        "worker_id",
        "name",
        "phone",
        "user__username",
        "user__email",
    )
    readonly_fields = ("worker_id", "created_at")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_id",
        "name",
        "subject",
        "assigned_worker",
        "status",
        "update_button",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "tracking_id",
        "name",
        "email",
        "subject",
        "assigned_worker__name",
        "assigned_worker__worker_id",
    )
    readonly_fields = ("tracking_id", "created_at", "updated_at")

    def update_button(self, obj):
        url = reverse(
            "admin:complaints_complaint_change",
            args=[obj.pk],
        )
        return format_html(
            '<a class="button" href="{}">Update</a>',
            url,
        )

    update_button.short_description = "Action"


@admin.register(ComplaintStatusHistory)
class ComplaintStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "complaint",
        "old_status",
        "new_status",
        "changed_at",
    )
    list_filter = ("new_status", "changed_at")
    search_fields = ("complaint__tracking_id",)
    readonly_fields = ("changed_at",)
