# Apni Factory CRM

A Django-based CRM system with WhatsApp integration and GST verification features.

## Features
- WhatsApp Webhook integration for automated messaging.
- GST Verification via external API.
- Customer management and lead tracking.
- Mobile API endpoints for GST verification.

## Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file from the template and add your credentials.
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the server:
   ```bash
   python manage.py runserver
   ```
