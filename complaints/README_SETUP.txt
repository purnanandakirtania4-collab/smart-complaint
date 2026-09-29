SMART COMPLAINT - CLEAN CONNECT + BUSINESS TEMPLATE SET

1) COPY BACKEND FILES
- views.py -> your complaints app views.py
- urls.py  -> your complaints app urls.py

2) COPY TEMPLATE FOLDERS
- templates/complaints/Business_Folder/
- templates/complaints/Connect_Folder/
- templates/complaints/User_Folder/home_navbar.html

3) CLEAN FINAL STRUCTURE
Business_Folder/
  business_applicants.html
  business_connect.html
  business_dashboard.html
  business_owner_profile.html
  business_post.html
  shop_directory.html

Connect_Folder/
  buy.html
  connect_chat.html
  marketplace.html
  marketplace_style.html
  offer.html
  opportunity_details.html
  shop_login.html
  shop_register.html
  worker_applications.html
  worker_opportunities.html

User_Folder/
  home_navbar.html

4) DELETE OLD DUPLICATE TEMPLATES AFTER COPYING THE CLEAN SET
- Connect_Folder/employer_post_job.html
- Connect_Folder/employer_worker_profile.html
- Connect_Folder/worker_jobs.html

Do NOT delete the new business_post.html, business_owner_profile.html or worker_opportunities.html.

5) HOME NAVBAR BUTTON CONNECTIONS
Home          -> url name: home
My Complaint  -> url name: my_complaints
Submit        -> url name: submit_complaint
Buy           -> url name: buy_marketplace -> /buy/ -> Connect_Folder/buy.html
Business      -> url name: shop_directory -> /business/directory/ -> Business_Folder/shop_directory.html

6) CONNECT / MARKETPLACE CONNECTIONS
job_marketplace      -> Connect_Folder/marketplace.html
worker_jobs          -> Connect_Folder/worker_opportunities.html
job_details          -> Connect_Folder/opportunity_details.html
worker_applications  -> Connect_Folder/worker_applications.html
job_offer            -> Connect_Folder/offer.html
job_chat             -> Connect_Folder/connect_chat.html

7) SHOP OWNER CONNECTIONS
shop_register          -> Connect_Folder/shop_register.html
shop_login             -> Connect_Folder/shop_login.html
business_dashboard     -> Business_Folder/business_dashboard.html
business_post          -> Business_Folder/business_post.html
business_applicants    -> Business_Folder/business_applicants.html
business_owner_profile -> Business_Folder/business_owner_profile.html
business_logout        -> logs out and redirects to shop_login

8) PUBLIC BUSINESS CONNECTIONS
business_connect -> Business_Folder/business_connect.html
shop_directory   -> Business_Folder/shop_directory.html
buy_marketplace  -> Connect_Folder/buy.html

9) IMPORTANT CURRENT BACKEND LIMITATION
The current project has shop-level data in EmployerProfile but no dedicated Product model was available in the supplied backend. Therefore buy.html currently shows:
- shop logo/photo
- shop name
- owner/contact person
- location
- business type
- shop.about as Products & Details
- call/email buttons

A real product catalog with product photo, name, price, stock and per-product details requires a Product model + migration + Shop Owner product management views.

10) JOB/HIRING UI STATUS
The supplied backend verifies worker/shop-owner access and renders marketplace screens, but it does not yet implement JobPost creation or pass live jobs/applications to every UI screen. The templates intentionally show clean empty states rather than pretending data is being saved.
