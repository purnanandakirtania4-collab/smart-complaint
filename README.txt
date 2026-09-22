SMART COMPLAINT - FULL UI POLISH + SESSION ROLE + PROFILE PHOTO PERSISTENCE FIX
=============================================================================

WHAT THIS PACKAGE FIXES
-----------------------
1. All 43 Django HTML templates are included as full replacement files.
2. Shared mobile-first polish is applied through complaints/base_style.html.
3. Secondary pages automatically receive a professional SVG Back button at
   the bottom-left when that page does not already have a back control.
4. No project UI emoji characters remain in the supplied HTML templates.
5. Worker Dashboard identity/name card is moved slightly lower below the fixed
   Worker navbar, especially on mobile.
6. Safe-area handling is added for Android status/navigation bars.
7. Mixed user/worker session bug is fixed:
   - one WebView cookie jar can only have one active Django login at a time;
   - whichever account was logged in last remains the authenticated account;
   - if that account is a worker, opening the app root now redirects to the
     Worker Dashboard instead of rendering citizen UI with the worker name.
8. Login pages are marked never-cache + ensure_csrf_cookie to reduce stale
   CSRF-token 403 errors after deploy/reopen.
9. Android WebView now loads fresh pages instead of stale cached HTML and
   flushes cookies after page load.
10. User profile photo URL receives a cache-busting version value.
11. Production media can be served from a persistent Railway Volume.
12. MariaDB Strict Mode is enabled in Django DB OPTIONS.
13. Railway defaults DEBUG to False when Railway environment variables are
    present, while local development defaults to True.

IMPORTANT ACCOUNT NOTE
----------------------
A single Android WebView uses one cookie/session store. It cannot keep a citizen
account and a worker account simultaneously authenticated in the same WebView.
To switch accounts, log out of the current account and log into the other one.
This update makes the active account route to the correct side consistently.

DJANGO FILES TO REPLACE
-----------------------
Replace the complete folder:
    complaints/templates/complaints/

Also replace:
    complaints/views.py
    complaint_system/settings.py
    complaint_system/urls.py

No migration is required for this package.

ANDROID FILES TO REPLACE
------------------------
Copy from this package's android/ folder into your Android Studio project:

    app/src/main/java/com/smartcomplaint/app/MainActivity.kt
    app/src/main/res/layout/activity_main.xml
    app/src/main/res/values/themes.xml
    app/src/main/res/values-night/themes.xml

RAILWAY PROFILE PHOTO PERSISTENCE
---------------------------------
User-uploaded photos must NOT depend on Railway's temporary filesystem.
Create/mount a Railway Volume at:

    /app/media

Then add/update Railway Variables:

    MEDIA_ROOT=/app/media
    SERVE_MEDIA_WITH_DJANGO=True
    DEBUG=False

Without a persistent Volume, uploaded profile photos may disappear after a
Railway restart/redeploy even if the Django code is correct.

AFTER COPYING FILES
-------------------
Run:

    python manage.py check
    python manage.py migrate

Expected migration result for this update:
    No migrations to apply.

Then test locally/mobile:

A. Citizen login -> Profile -> upload DP -> close app -> reopen -> DP remains.
B. Login as Worker -> close app -> reopen -> Worker Dashboard opens, not citizen Home.
C. Logout Worker -> login Citizen -> close/reopen -> Citizen Home opens.
D. Open secondary pages -> bottom-left SVG Back button appears where needed.
E. Worker Dashboard -> navbar and worker identity/name card no longer overlap phone status bar.
F. User login after deploy -> no stale CSRF 403 from cached login HTML.

GIT
---
After python manage.py check succeeds:

    git add .
    git commit -m "Polish mobile UI and fix role session and profile media"
    git push origin main

SECURITY
--------
Do not add .env, Razorpay secrets, Gemini keys, Firebase private keys, or webhook
secrets to GitHub. Keep them in environment variables only.
