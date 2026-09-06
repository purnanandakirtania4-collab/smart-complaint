from django.urls import path
from . import views


urlpatterns = [

    # =====================================================
    # HOME
    # =====================================================

    path(
        "",
        views.home,
        name="home"
    ),

    # =====================================================
    # USER AUTH
    # =====================================================

    path(
        "login/",
        views.user_login,
        name="login"
    ),

    path(
        "register/",
        views.register,
        name="register"
    ),

    path(
        "logout/",
        views.user_logout,
        name="logout"
    ),

    path(
        "profile/",
        views.profile,
        name="profile"
    ),

    # =====================================================
    # COMPLAINT
    # =====================================================

    path(
        "submit_complaint/",
        views.submit_complaint,
        name="submit_complaint"
    ),

    path(
        "check-status/",
        views.check_status,
        name="check_status"
    ),

    path(
        "my-complaints/",
        views.my_complaints,
        name="my_complaints"
    ),

    path(
        "success/",
        views.success,
        name="success"
    ),

    # =====================================================
    # PAYMENT
    # =====================================================

    #path("payment/",views.payment,name="payment"),

    #path("payment-success/",views.payment_success,name="payment_success"),

    # =====================================================
    # WORKER
    # =====================================================

    path(
        "worker-details/",
        views.worker_details,
        name="worker_details"
    ),

    path(
        "worker-profile/<int:worker_id>/",
        views.worker_profile,
        name="worker_profile"
    ),

    path(
        "worker-register/",
        views.worker_register,
        name="worker_register"
    ),

    path(
        "worker-login/",
        views.worker_login,
        name="worker_login"
    ),

    path(
        "worker-logout/",
        views.worker_logout,
        name="worker_logout"
    ),

    path(
        "worker-dashboard/",
        views.worker_dashboard,
        name="worker_dashboard"
    ),
]