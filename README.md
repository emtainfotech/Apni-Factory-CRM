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
