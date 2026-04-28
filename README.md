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

---

## 🛠️ Technical Architecture

### App Structure
- **[authentication](file:///e:/APNI%20FACTORY/ApniFactoryCRM/authentication)**: Custom User model, role-based permissions, and invitation systems.
- **[core](file:///e:/APNI%20FACTORY/ApniFactoryCRM/core)**: The engine of the CRM. Contains Customer models, WhatsApp bot logic, GST verification utilities, and API endpoints.
- **[ApniFactoryCRM](file:///e:/APNI%20FACTORY/ApniFactoryCRM/ApniFactoryCRM)**: Project configuration, settings (with IST timezone support), and root URL routing.

### Key API Endpoints
- `/core/whatsapp/webhook/`: Handles incoming messages from the Meta WhatsApp API.
- `/core/api/mobile/gst-check/`: Specialized JSON endpoint for the mobile application.
- `/core/api/my-customers/`: Retrieves assigned customers for the logged-in user.

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
