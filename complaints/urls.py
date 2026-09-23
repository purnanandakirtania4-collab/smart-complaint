from django.contrib.auth import views as auth_views
from django.urls import path

from . import ai_views
from . import views


urlpatterns = [
    # USER
    path("", views.front_page, name="front_page"),
    path("home/", views.home, name="home"),
    path("login/", views.user_login, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.user_logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("settings/", views.user_settings, name="user_settings"),

    # CITIZEN PREMIUM - PREPAID 30 DAY PASS
    path(
        "citizen-premium/",
        views.citizen_premium,
        name="citizen_premium",
    ),
    path(
        "citizen-premium/create-order/",
        views.create_citizen_premium_order,
        name="create_citizen_premium_order",
    ),
    path(
        "citizen-premium/verify/",
        views.verify_citizen_premium_payment,
        name="verify_citizen_premium_payment",
    ),

    # LOCAL DEVELOPMENT ONLY - endpoints enforce DEBUG + env + localhost
    path(
        "citizen-premium/local-test/activate/",
        views.activate_local_test_premium,
        name="activate_local_test_premium",
    ),
    path(
        "citizen-premium/local-test/reset/",
        views.reset_local_test_premium,
        name="reset_local_test_premium",
    ),

    # USER COMMUNITY / SOCIAL
    path(
        "community/<str:username>/",
        views.public_user_profile,
        name="public_user_profile",
    ),
    path(
        "community/<str:username>/follow/",
        views.toggle_user_follow,
        name="toggle_user_follow",
    ),
    path(
        "followers/",
        views.user_followers,
        name="user_followers",
    ),
    path(
        "following/",
        views.user_following,
        name="user_following",
    ),
    path(
        "people/",
        views.people_you_may_know,
        name="people_you_may_know",
    ),

    # PUBLIC LEADERBOARD - NO LOGIN REQUIRED
    path("leaderboard/", views.public_leaderboard, name="public_leaderboard"),
    path("payment-details/", views.user_payment_details, name="user_payment_details"),
    path("payment/create-order/", views.create_test_payment_order, name="create_test_payment_order"),
    path("payment/verify/", views.verify_test_payment, name="verify_test_payment"),
    path("change-password/", views.user_change_password, name="user_change_password"),
    path("update-address/", views.user_update_address, name="user_update_address"),
    path("support-request/", views.user_support_request, name="user_support_request"),
    path("delete-account/", views.user_delete_account, name="user_delete_account"),

    # USER LEAGUE / ACHIEVEMENTS / REWARDS
    path("league/", views.user_leaderboard, name="user_leaderboard"),
    path("achievements/", views.user_achievements, name="user_achievements"),
    path("rewards/", views.user_rewards, name="user_rewards"),

    # PASSWORD RESET
    path("forgot-password/", auth_views.PasswordResetView.as_view(
        template_name="complaints/User_Folder/password_reset_form.html",
        email_template_name="complaints/User_Folder/password_reset_email.txt",
        subject_template_name="complaints/User_Folder/password_reset_subject.txt",
        success_url="/forgot-password/done/",
    ), name="password_reset"),
    path("forgot-password/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="complaints/User_Folder/password_reset_done.html",
    ), name="password_reset_done"),
    path("reset-password/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="complaints/User_Folder/password_reset_confirm.html",
        success_url="/reset-password/complete/",
    ), name="password_reset_confirm"),
    path("reset-password/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="complaints/User_Folder/password_reset_complete.html",
    ), name="password_reset_complete"),

    # COMPLAINT
    path("submit_complaint/", views.submit_complaint, name="submit_complaint"),
    path("analyze-complaint-ai/", ai_views.analyze_complaint_ai, name="analyze_complaint_ai"),
    path("ai/status/", ai_views.ai_status, name="ai_status"),

    # WORKER AI
    path(
        "worker-ai/complaint/<int:complaint_id>/summary/",
        ai_views.worker_ai_summary,
        name="worker_ai_summary",
    ),
    path(
        "worker-ai/complaint/<int:complaint_id>/checklist/",
        ai_views.worker_ai_checklist,
        name="worker_ai_checklist",
    ),
    path(
        "worker-ai/complaint/<int:complaint_id>/reply/",
        ai_views.worker_ai_reply,
        name="worker_ai_reply",
    ),

    # LOCAL DEVELOPMENT ONLY - Worker Pro test controls
    path(
        "worker-pro/local-test/activate/",
        views.activate_local_test_worker_pro,
        name="activate_local_test_worker_pro",
    ),
    path(
        "worker-pro/local-test/reset/",
        views.reset_local_test_worker_pro,
        name="reset_local_test_worker_pro",
    ),
    path("check-status/", views.check_status, name="check_status"),
    path("my-complaints/", views.my_complaints, name="my_complaints"),
    path("notifications/", views.notifications, name="notifications"),
    path("success/", views.success, name="success"),
    path("rate-worker/<int:complaint_id>/", views.rate_worker, name="rate_worker"),
    path("rate-user/<int:complaint_id>/", views.rate_user, name="rate_user"),

    # WORKER
    path("worker-details/", views.worker_details, name="worker_details"),
    path("worker-profile/<int:worker_id>/", views.worker_profile, name="worker_profile"),

    path(
        "worker-profile/<int:worker_id>/follow/",
        views.toggle_worker_follow,
        name="toggle_worker_follow",
    ),
    path(
        "worker-profile/<int:worker_id>/like/",
        views.toggle_worker_profile_like,
        name="toggle_worker_profile_like",
    ),
    path("worker-register/", views.worker_register, name="worker_register"),
    path("worker-login/", views.worker_login, name="worker_login"),
    path("worker-logout/", views.worker_logout, name="worker_logout"),
    path("worker-dashboard/", views.worker_dashboard, name="worker_dashboard"),
    path("worker-settings/", views.worker_settings, name="worker_settings"),
    path("worker-payment-details/", views.worker_payment_details, name="worker_payment_details"),
    path("worker-delete-account/", views.worker_delete_account, name="worker_delete_account"),
    path("worker-chats/", views.worker_chats, name="worker_chats"),
    path("worker-change-password/", views.worker_change_password, name="worker_change_password"),
    path("worker/app-terms/", views.worker_app_terms, name="worker_app_terms"),

    # WORKER LEAGUE / ACHIEVEMENTS / REWARDS
    path("worker-league/", views.worker_leaderboard, name="worker_leaderboard"),
    path("worker-achievements/", views.worker_achievements, name="worker_achievements"),
    path("worker-rewards/", views.worker_rewards, name="worker_rewards"),

    # WORKER SUBSCRIPTION
    path("worker-subscription/terms/", views.terms_conditions, name="terms_conditions"),
    path("worker-subscription/payment/", views.worker_subscription_payment, name="worker_subscription_payment"),
    path("worker-subscription/webhook/", views.worker_subscription_webhook, name="worker_subscription_webhook"),


    # JOB MARKETPLACE
    path("jobs/", views.job_marketplace, name="job_marketplace"),
    path("jobs/find/", views.worker_jobs, name="worker_jobs"),
    path("jobs/details/", views.job_details, name="job_details"),
    path("jobs/applications/", views.worker_applications, name="worker_applications"),

    # EMPLOYER / COMPANY / SHOP OWNER
    path("jobs/employer/", views.employer_portal, name="employer_portal"),

    # Legacy aliases - now open the Company / Shop choice page
    path("jobs/employer/register/", views.employer_register, name="employer_register"),
    path("jobs/employer/login/", views.employer_login, name="employer_login"),

    # Company account
    path("jobs/company/register/", views.company_register, name="company_register"),
    path("jobs/company/login/", views.company_login, name="company_login"),

    # Shop Owner account
    path("jobs/shop/register/", views.shop_register, name="shop_register"),
    path("jobs/shop/login/", views.shop_login, name="shop_login"),

    path("jobs/employer/logout/", views.employer_logout, name="employer_logout"),
    path("jobs/employer/dashboard/", views.employer_dashboard, name="employer_dashboard"),
    path("jobs/employer/post-job/", views.employer_post_job, name="employer_post_job"),
    path("jobs/employer/applicants/", views.employer_applicants, name="employer_applicants"),
    path(
        "jobs/employer/worker-profile/",
        views.employer_worker_profile,
        name="employer_worker_profile",
    ),
    path("jobs/offer/", views.job_offer, name="job_offer"),
    path("jobs/chat/", views.job_chat, name="job_chat"),

    # DEVICE / CHAT
    path("save-device-token/", views.save_device_token, name="save_device_token"),
    path("complaint-chat/<int:complaint_id>/", views.complaint_chat, name="complaint_chat"),
]
