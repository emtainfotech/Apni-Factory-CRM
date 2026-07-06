# Apni Factory CRM

A comprehensive Django-based Customer Relationship Management (CRM) system designed for the Indian B2B market, featuring automated WhatsApp lead generation, real-time GST verification, and a multi-role user management system.

## 🚀 Core Functionalities

### 1. Multi-Role User Management
The system supports four distinct roles, each with specialized dashboards:
- **Admin**: Full system access, user management, and global analytics.
- **Manager**: Team oversight, customer assignment, and performance tracking.
- **Employee**: Day-to-day customer interactions and manual GST verification.
- **Field Sales Agent**: On-ground lead capture and customer profile updates via mobile interfaces.

### 2. WhatsApp Bot Integration
Automated lead qualification system via WhatsApp Webhook:
- **Onboarding**: Greets new users and segments them into Sellers, Buyers, or General Enquiries.
- **Automated Qualification**: Collects business details and categorizes sellers (Manufacturer/Distributor/Brand Owner).
- **Human Handoff**: Flags conversations for manual intervention when users request help.

### 3. Real-Time GST Verification
Integrated with `verifya2z` API to validate business credentials:
- **Automated Verification**: The WhatsApp bot validates GST numbers during onboarding.
- **Mobile API**: Dedicated endpoints for the mobile app to perform instant GST checks.
- **Data Enrichment**: Automatically populates company name, business address, and registration status from GST records.

### 4. Lead & Customer Management
- **Lead Tracking**: Monitors the journey from initial WhatsApp contact to verified customer.
- **Bulk Operations**: Supports CSV/Excel uploads for mass customer data importing.
- **Assignment System**: Assigns customers to specific employees for personalized follow-ups.

### 5. App Content Management
Integrated with application database to manage user-facing content:
- **Banner Management**: Monitor and organize active promotional banners (Advertisements) displayed in the application. Supports sequence control and date-based scheduling.
- **Slider Management**: Manage high-impact sliders with image previews, company-specific filtering, and automated start/end date tracking.
- **Status Filtering**: Only active content (status=1) is displayed to admins for streamlined oversight.

### 6. Dedicated CRM Employee Portal
Isolated employee portal workspace (`/employee/` prefix) designed strictly for client management:
- **Duty Lock Enforcements**: Enforces punch-in controls, locking CRM customer listings, sales metrics, and invoice panels unless the employee has punched in for active duty.
- **Attributed Sales Tracking**: Seamlessly maps local client assignments to remote e-commerce shopper transactions in real-time, displaying dynamic revenue analytics.
- **Personal timelines**: Displays daily break timelines, attendance logs, and call tracking history on their personal dashboard.

### 7. Interactive HTMX Lead Kanban Board
A premium visual dashboard for lead lifecycle oversight:
- **Five Progression Columns**: Maps clients across `Leads`, `Prospects`, `Customers`, `Inactive`, and `Lost Leads`.
- **HTMX Progression Engine**: Supports moving cards across stages instantly via HTMX AJAX requests with zero full-page reload.
- **Quick Lead Creation**: Enables rapid lead manual onboarding via an integrated Bootstrap modal.

### 8. HRMS & Attendance Integrity Auditing
Advanced duty integrity and leave tracking system:
- **Integrity Capturing**: Captures the IP Address and browser User-Agent string on every punch event for administrative verification.
- **IST Late Threshold**: Automatically checks punch-ins against 09:30 AM IST (Asia/Kolkata). Late logins are flagged and dispatch instant notifications to the Admin feed.
- **Leave Request Engine**: Implements Casual, Sick, and Earned leave requests for employees, complete with an administrative approval auditing panel.

### 9. Admin Command Center Redesign & App Buyers Workspace (June 2026)
Significant dashboard UX/UI overhaul and e-commerce profile management system:
- **Semantic Card Accents**: Unified and color-coded all analytics metrics using high-contrast HSL/gradient status properties (e.g., Crimson Red for Returns/Tickets, Emerald Green for Active operations, Amber Orange for Pending/Warnings, WhatsApp Brand Green for WhatsApp leads, Cobalt Blue for Sales Volume).
- **Balanced Cards Layout**: Grouped App Dashboard metrics into a uniform 3x4 grid, and HRMS metrics into a 2x3 grid, completely eliminating blank spacing gaps across all viewport layouts.
- **Support Tickets & CRM Invoices Tables**: Added dedicated, side-by-side data tables displaying the 5 most recent CRM invoices and e-commerce support tickets. Support ticket profiles resolve usernames dynamically in the view to optimize database query runs.
- **App Buyer Profile Workspace**: Created a comprehensive workspace at `/core/app-db/buyers/<int:customer_id>/` showcasing buyer details, editable basic information (Name, Email, Phone, GST) via modal forms, shipping address directories, and a full purchase order ledger.
- **Route Namespace Corrections**: Audited and corrected all legacy `hostinger_` endpoints to namespaced app URL routes across the listing and details templates.
- **Tracking & Marketing Tag Panel**: Added a dedicated tracking tag panel at `/core/settings/tracking/` loaded from environment settings to inspect and integrate Meta Pixel, GA4, GTM, Ads Conversion, Search Console, and WhatsApp Chat events.

---

## 🗺️ Page Directory & Descriptions

This CRM application is partitioned into core namespaces managing distinct workspaces and operations:

### 1. Administrative Control Workspace (Core CRM)
- **Admin Dashboard** (`/core/dashboard/admin/`): Central command center showing color-coded operational metrics, employee punch status, and detailed data tables (Recent CRM Invoices, Recent Support Tickets, and New CRM Signups).
- **Manager Dashboard** (`/core/dashboard/manager/`): Panel for manager oversight, assignments, and team KPIs.
- **Agent Dashboard** (`/core/dashboard/agent/`): Operations tracker for field sales representatives.
- **Employee Directory** (`/core/users/`): Index of CRM team members with invitation status.
- **Add Employee** (`/core/users/create/`): Invitation page to onboard new employee members.
- **Employee Profile Details** (`/core/users/<int:user_id>/profile/`): Shows employee details, attendance check-ins, performance KPIs, and attributed sales.
- **Leave Request Manager** (`/core/dashboard/admin/manage-leaves/`): Administrative approval workspace for Casual/Sick/Earned leave requests.
- **Tracking Settings Dashboard** (`/core/settings/tracking/`): Admin page to monitor and verify active analytics, ads, and search tracking keys.

### 2. Customer & Lead Workspace (Core CRM)
- **CRM Buyer Directory** (`/core/customers/`): Directory of CRM customers, B2B profiles, status settings, assignment attributes, and bulk uploading utilities.
- **CRM Customer Details** (`/core/customers/<int:customer_id>/`): Shows communication histories, logged calls, follow-up timers, and customer conversion forms.
- **Interactive Lead Kanban Board** (`/core/leads/kanban/`): Drag-and-drop workspace displaying lead stages (`Leads`, `Prospects`, `Customers`, `Inactive`, and `Lost Leads`) powered by HTMX handlers.

### 3. Application Data Workspace (Hostinger DB)
- **Sellers Directory** (`/core/app-db/sellers/`): Dynamic index of e-commerce vendors registered on the platform.
- **Seller Detail View** (`/core/app-db/sellers/<int:user_id>/`): Comprehensive vendor tracking, brand associations, catalog listings, and order histories.
- **App Buyers Directory** (`/core/app-db/buyers/`): Dynamic index of B2B app buyers.
- **App Buyer Profile Workspace** (`/core/app-db/buyers/<int:customer_id>/`): Dedicated profile workspace showing name, email, mobile, GST/PAN validation, active shipping address cards, and a ledger of historical purchases.
- **App Orders List** (`/core/orders/`): Global order tracking list synced from the platform database.
- **App Order Detail & Invoice** (`/core/orders/<int:order_id>/`): Transaction details, ordered products, invoice layouts, and tracking stages.
- **App Products** (`/core/products/`): General catalog of products, categories, stock tracking, and pricing.
- **Banners Manager** (`/core/banners/`): Layout and scheduling configurations for promotional advertisements.
- **Sliders Manager** (`/core/sliders/`): Slider sequences, company filters, and scheduling dates.
- **Categories Manager** (`/core/categories/`): Dynamic hierarchy indexing main categories, category groups, and subcategories.
- **Support Tickets Index** (`/core/support/tickets/`): Support index linking tickets, messaging logs, client context, and ticket statuses.
- **Wallet History** (`/core/wallet/transactions/`): Audit logs of user wallets (credits, debits, refund allocations, commissions).

### 4. Billing & Invoice Workspace
- **Marketing Invoices List** (`/core/invoices/`): Index of GST invoices created inside the local CRM database.
- **Create Invoice** (`/core/invoices/create/`): Financial tool to generate GST tax invoices with B2B/B2C calculations, CGST/SGST/IGST breakdown, and reverse charge indicators.
- **Invoice Detail View** (`/core/invoices/<int:invoice_id>/`): Detail view allowing finalized rendering, emailing, WhatsApp dispatching, or downloading tax invoices as PDF.

### 5. Employee Portal Workspace (`/employee/` prefix)
- **Employee Dashboard** (`/employee/dashboard/`): Isolated workspace for CRM employees. Enforces dynamic duty locks (punch-in controls) on lead lists and financial dashboards. Contains personal attendance timelines, call logs, and attributed revenue maps.
- **Punch History & Leave Panel** (`/employee/attendance/`): Detailed timeline of personal punch-ins, breaks, late threshold warnings, and leave request forms.
- **Employee Portal Customers** (`/employee/customers/`): Assigned buyers list, calling interfaces, and profile details.
- **Employee Portal Kanban** (`/employee/leads/kanban/`): Kanban board restricted to leads assigned to the logged-in employee.

---

## 🛠️ Technical Architecture

### App Structure
- **[authentication](file:///e:/APNI%20FACTORY/ApniFactoryCRM/authentication)**: Custom User model, role-based permissions, and invitation systems.
- **[core](file:///e:/APNI%20FACTORY/ApniFactoryCRM/core)**: The engine of the CRM. Contains Customer models, WhatsApp bot qualification logic, GST verification utilities, API endpoints, and App Content (Banners/Sliders) views.
- **[employee_portal](file:///e:/APNI%20FACTORY/ApniFactoryCRM/employee_portal)**: Isolated employee workspace, customer relationship operations, attendance timelines, and sales attributors.
- **[hostinger_data](file:///e:/APNI%20FACTORY/ApniFactoryCRM/hostinger_data)**: Application-specific data like Products, Orders, Banners, and Sliders.
- **[ApniFactoryCRM](file:///e:/APNI%20FACTORY/ApniFactoryCRM/ApniFactoryCRM)**: Project configuration, settings (with IST timezone support), and root URL routing.

### Key API & Content Endpoints
- `/core/whatsapp/webhook/`: Handles incoming messages from the Meta WhatsApp API.
- `/core/api/mobile/gst-check/`: Specialized JSON endpoint for the mobile application.
- `/core/api/my-customers/`: Retrieves assigned customers for the logged-in user.
- `/banners/`: View all active promotional banners.
- `/sliders/`: View all active application sliders.

---

## ⚙️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/emtainfotech/Apni-Factory-CRM.git
   cd Apni-Factory-CRM
   ```

2. **Environment Configuration**:
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your_django_secret
   DEBUG=True
   GST_SECRET_KEY=your_gst_api_key
   WHATSAPP_TOKEN=your_meta_token
   META_VERIFY_TOKEN=your_webhook_verify_token
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Database Setup**:
   ```bash
   python manage.py migrate
   ```

5. **Run the Server**:
   ```bash
   python manage.py runserver
   ```

---

## 📊 Workflow Overview
1. **Lead Ingress**: A user messages the WhatsApp number.
2. **Bot Interaction**: The bot qualifies the user (Seller/Buyer) and asks for GST.
3. **Verification**: GST is verified via API; a `Customer` record is automatically created in the CRM.
4. **Assignment**: The Manager assigns the new customer to an Employee.
5. **Follow-up**: The Employee manages the customer via the Dashboard, adding notes and tracking status.
