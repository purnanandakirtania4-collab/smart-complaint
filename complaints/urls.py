from django.contrib.auth import views as auth_views
from django.urls import path

from . import ai_views
from . import views


urlpatterns = [

    # =====================================================
    # USER
    # =====================================================

    path("", views.home, name="home"),
    path("login/", views.user_login, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.user_logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("settings/", views.user_settings, name="user_settings"),

    # =====================================================
    # USER PAYMENT DETAILS
    # =====================================================

    path(
        "payment-details/",
        views.user_payment_details,
        name="user_payment_details",
    ),

    # =====================================================
    # RAZORPAY TEST PAYMENT
    # =====================================================

    path(
        "payment/create-order/",
        views.create_test_payment_order,
        name="create_test_payment_order",
    ),
    path(
        "payment/verify/",
        views.verify_test_payment,
        name="verify_test_payment",
    ),
    path(
        "change-password/",
        views.user_change_password,
        name="user_change_password",
    ),
    path(
        "update-address/",
        views.user_update_address,
        name="user_update_address",
    ),
    path(
        "support-request/",
        views.user_support_request,
        name="user_support_request",
    ),
    path(
        "delete-account/",
        views.user_delete_account,
        name="user_delete_account",
    ),

    # =====================================================
    # FORGOT / RESET PASSWORD
    # =====================================================

    path(
        "forgot-password/",
        auth_views.PasswordResetView.as_view(
            template_name="complaints/User_Folder/password_reset_form.html",
            email_template_name="complaints/User_Folder/password_reset_email.txt",
            subject_template_name="complaints/User_Folder/password_reset_subject.txt",
            success_url="/forgot-password/done/",
        ),
        name="password_reset",
    ),
    path(
        "forgot-password/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="complaints/User_Folder/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset-password/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="complaints/User_Folder/password_reset_confirm.html",
            success_url="/reset-password/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset-password/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="complaints/User_Folder/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # =====================================================
    # COMPLAINT
    # =====================================================

    path(
        "submit_complaint/",
        views.submit_complaint,
        name="submit_complaint",
    ),

    # =====================================================
    # AI COMPLAINT ANALYZER
    # =====================================================

    path(
        "analyze-complaint-ai/",
        ai_views.analyze_complaint_ai,
        name="analyze_complaint_ai",
    ),

    path(
        "check-status/",
        views.check_status,
        name="check_status",
    ),
    path(
        "my-complaints/",
        views.my_complaints,
        name="my_complaints",
    ),
    path(
        "notifications/",
        views.notifications,
        name="notifications",
    ),
    path(
        "success/",
        views.success,
        name="success",
    ),

    # =====================================================
    # RATINGS
    # =====================================================

    path(
        "rate-worker/<int:complaint_id>/",
        views.rate_worker,
        name="rate_worker",
    ),
    path(
        "rate-user/<int:complaint_id>/",
        views.rate_user,
        name="rate_user",
    ),

    # =====================================================
    # WORKER
    # =====================================================

    path(
        "worker-details/",
        views.worker_details,
        name="worker_details",
    ),
    path(
        "worker-profile/<int:worker_id>/",
        views.worker_profile,
        name="worker_profile",
    ),
    path(
        "worker-register/",
        views.worker_register,
        name="worker_register",
    ),
    path(
        "worker-login/",
        views.worker_login,
        name="worker_login",
    ),
    path(
        "worker-logout/",
        views.worker_logout,
        name="worker_logout",
    ),
    path(
        "worker-dashboard/",
        views.worker_dashboard,
        name="worker_dashboard",
    ),
    path(
        "worker-settings/",
        views.worker_settings,
        name="worker_settings",
    ),

    # =====================================================
    # WORKER PAYMENT DETAILS
    # =====================================================

    path(
        "worker-payment-details/",
        views.worker_payment_details,
        name="worker_payment_details",
    ),

    path(
        "worker-delete-account/",
        views.worker_delete_account,
        name="worker_delete_account",
    ),

    # =====================================================
    # WORKER CHAT INBOX
    # =====================================================

    path(
        "worker-chats/",
        views.worker_chats,
        name="worker_chats",
    ),

    # =====================================================
    # WORKER CHANGE PASSWORD
    # =====================================================

    path(
        "worker-change-password/",
        views.worker_change_password,
        name="worker_change_password",
    ),

    # =====================================================
    # WORKER APP TERMS - READ ONLY
    # =====================================================

    path(
        "worker/app-terms/",
        views.worker_app_terms,
        name="worker_app_terms",
    ),

    # =====================================================
    # WORKER SUBSCRIPTION
    # =====================================================

    path(
        "worker-subscription/terms/",
        views.terms_conditions,
        name="terms_conditions",
    ),
    path(
        "worker-subscription/payment/",
        views.worker_subscription_payment,
        name="worker_subscription_payment",
    ),
    path(
        "worker-subscription/webhook/",
        views.worker_subscription_webhook,
        name="worker_subscription_webhook",
    ),

    # =====================================================
    # FIREBASE DEVICE TOKEN
    # =====================================================

    path(
        "save-device-token/",
        views.save_device_token,
        name="save_device_token",
    ),

    # =====================================================
    # COMPLAINT CHAT
    # =====================================================

    path(
        "complaint-chat/<int:complaint_id>/",
        views.complaint_chat,
        name="complaint_chat",
    ),
]
