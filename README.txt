SMART COMPLAINT - WORKER PRO RECURRING TRUST UPDATE
==================================================

WHAT THIS UPDATE DOES
---------------------
- Reuses the existing WorkerSubscription model.
- Keeps ₹49 introductory first period.
- Keeps ₹149/month recurring Worker Pro plan.
- Prevents duplicate Razorpay subscription creation where possible.
- Adds manual "Refresh Razorpay Status".
- Adds "Turn Off Future Renewal".
- Keeps already-paid access until current_period_end after renewal is disabled.
- Shows transparent plan/status information to workers.
- Does not activate Worker Pro when payment/authorisation fails.
- Webhook continues to verify Razorpay signature before syncing.

FILES
-----
complaints/models.py
complaints/views.py
complaints/urls.py
complaints/templates/complaints/Worker_Folder/worker_subscription_payment.html
complaints/migrations/0030_worker_subscription_trust_fields.py

MIGRATION REQUIRED
------------------
python manage.py check
python manage.py migrate
python manage.py runserver

EXPECTED:
Applying complaints.0030_worker_subscription_trust_fields... OK

RAZORPAY PLAN
-------------
Create ONE monthly Razorpay Subscription Plan for the REGULAR price:

Plan name:
Smart Complaint Worker Pro Monthly

Period:
monthly

Interval:
1

Amount:
₹149

Then copy its plan ID (starts with plan_) into:

RAZORPAY_WORKER_PLAN_ID=plan_xxxxxxxxx

The Django code creates a ₹49 upfront introductory add-on and schedules
the ₹149 plan to begin about one month later.

SERVER VARIABLES
----------------
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WORKER_PLAN_ID
RAZORPAY_WEBHOOK_SECRET

Do not put secrets in templates or JavaScript.

WEBHOOK
-------
Production URL:

https://YOUR-DOMAIN/worker-subscription/webhook/

Configure a strong webhook secret in Razorpay and put the same value in:
RAZORPAY_WEBHOOK_SECRET

Useful subscription events include state/payment changes such as:
subscription.activated
subscription.charged
subscription.pending
subscription.halted
subscription.cancelled
subscription.completed

The endpoint verifies X-Razorpay-Signature and then fetches the current
subscription directly from Razorpay before updating local entitlement.

CANCELLATION
------------
The worker can choose "Turn Off Future Renewal".
The app asks Razorpay to cancel at the end of the current billing cycle.
Already-paid Worker Pro access remains until current_period_end.

IMPORTANT
---------
Keep LOCAL_WORKER_PRO_TEST_ENABLED=True only on local development.
Do NOT add it to Railway.

Before live launch, test the full recurring flow with Razorpay TEST keys,
a TEST plan ID and a TEST webhook secret.
