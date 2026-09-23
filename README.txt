SMART COMPLAINT - COMPANY + SHOP OWNER AUTH UPDATE

Purpose:
Create separate Company and Shop Owner registration/login flows for Job Connect.

NEW FLOW
/jobs/employer/
  -> Company Register
  -> Company Login
  -> Shop Owner Register
  -> Shop Owner Login

NEW ROUTES
/jobs/company/register/
/jobs/company/login/
/jobs/shop/register/
/jobs/shop/login/

SECURITY / TRUST BEHAVIOR
- Registration does NOT auto-verify the employer.
- Every new account starts as Pending Verification.
- Business verification proof is required.
- Company registration number is required for the Company route.
- Business phone, email, full address, city, state and pincode are required.
- Company accounts cannot log in from the Shop Owner login page.
- Shop Owner accounts cannot log in from the Company login page.
- Suspended employer accounts are blocked.
- Job posting / hiring pages are server-locked until verification_status = approved.
- Django admin can Approve / Reject / Suspend / move employers back to Pending.

IMPORTANT
This reduces fraud risk but no login/verification system can guarantee that fraud is impossible.
Do not collect unnecessary Aadhaar/PAN data in this flow.

FILES TO REPLACE
complaints/views.py
complaints/urls.py
complaints/admin.py
complaints/templates/complaints/Job_Folder/job_marketplace_style.html
complaints/templates/complaints/Job_Folder/job_marketplace.html
complaints/templates/complaints/Job_Folder/employer_dashboard.html

NEW FILES
complaints/templates/complaints/Job_Folder/employer_portal.html
complaints/templates/complaints/Job_Folder/company_register.html
complaints/templates/complaints/Job_Folder/company_login.html
complaints/templates/complaints/Job_Folder/shop_register.html
complaints/templates/complaints/Job_Folder/shop_login.html

MODEL / MIGRATION
No model change in this step.
No migration required.

NEXT TEST AFTER REPLACEMENT
python manage.py check
