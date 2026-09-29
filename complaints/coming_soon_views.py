from django.shortcuts import render, redirect


# =========================================================
# COMING SOON
# =========================================================

def coming_soon(request):

    # Admin / Superuser ko admin panel par bhejo.
    if (
        request.user.is_authenticated
        and (
            request.user.is_staff
            or request.user.is_superuser
        )
    ):
        return redirect('/admin/')

    # Coming Soon page public hai.
    # Isliye Citizen, Worker, Shop Owner aur logged-out
    # sab users is page ko open kar sakte hain.
    return render(
        request,
        'complaints/User_Folder/coming_soon.html'
    )