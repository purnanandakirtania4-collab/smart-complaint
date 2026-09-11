from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.user_login, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.user_logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("settings/", views.user_settings, name="user_settings"),

    path("submit_complaint/", views.submit_complaint, name="submit_complaint"),
    path("check-status/", views.check_status, name="check_status"),
    path("my-complaints/", views.my_complaints, name="my_complaints"),
    path("notifications/", views.notifications, name="notifications"),
    path("success/", views.success, name="success"),

    path("rate-worker/<int:complaint_id>/", views.rate_worker, name="rate_worker"),
    path("rate-user/<int:complaint_id>/", views.rate_user, name="rate_user"),

    path("worker-details/", views.worker_details, name="worker_details"),
    path("worker-profile/<int:worker_id>/", views.worker_profile, name="worker_profile"),
    path("worker-register/", views.worker_register, name="worker_register"),
    path("worker-login/", views.worker_login, name="worker_login"),
    path("worker-logout/", views.worker_logout, name="worker_logout"),
    path("worker-dashboard/", views.worker_dashboard, name="worker_dashboard"),
    path("worker-settings/", views.worker_settings, name="worker_settings"),

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
]
