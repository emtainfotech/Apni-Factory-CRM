import urllib.parse
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape

from hostinger_data.models import Companies, Users as HostingerUser
from .models import SellerOnboardingTracker, Customer
from .utils import send_text_message, format_whatsapp_phone


def get_formatted_support_phone():
    """Returns a cleanly formatted support phone number."""
    raw = getattr(settings, 'WHATSAPP_CLICK_TO_CHAT_PHONE', '9340547135')
    digits = ''.join(c for c in str(raw) if c.isdigit())
    if len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    elif len(digits) == 12 and digits.startswith('91'):
        return f"+91 {digits[2:7]} {digits[7:]}"
    return f"+91 {digits}" if digits else "+91 93405 47135"


def get_seller_contact_details(h_user):
    """
    Extracts and standardizes contact and business information for an external Hostinger seller.
    """
    companies = Companies.objects.filter(user_id=h_user.id)
    primary_company = companies.first()

    contact_person = (h_user.name or '').strip()
    if not contact_person and primary_company:
        contact_person = primary_company.name.strip()
    if not contact_person:
        contact_person = "Valued Partner"

    company_name = ""
    if primary_company and primary_company.name:
        company_name = primary_company.name.strip()
    elif h_user.name:
        company_name = h_user.name.strip()
    else:
        company_name = "Your Company"

    seller_id = f"AF-{h_user.id}"

    gstin = ""
    if primary_company and primary_company.gst:
        gstin = primary_company.gst.strip()
    if not gstin:
        gstin = "Under Verification / Not Provided"

    # Resolve phone number (Company mobile -> CRM Customer phone)
    phone = ""
    if primary_company and primary_company.mobile:
        phone = str(primary_company.mobile).strip()
    if not phone and h_user.email:
        crm_cust = Customer.objects.filter(email__iexact=h_user.email).first()
        if crm_cust and crm_cust.phone:
            phone = crm_cust.phone.strip()

    # Resolve email
    email = (h_user.email or '').strip()
    if not email and primary_company and primary_company.email:
        email = str(primary_company.email).strip()

    support_number = get_formatted_support_phone()

    return {
        'user_id': h_user.id,
        'contact_person': contact_person,
        'company_name': company_name,
        'seller_id': seller_id,
        'gstin': gstin,
        'phone': phone,
        'email': email,
        'support_number': support_number,
        'has_company': primary_company is not None,
        'company': primary_company,
    }


def build_welcome_whatsapp_message(details):
    """
    Builds the reassuring welcome message for WhatsApp exactly as requested.
    """
    return (
        f"🎉 *Welcome to Apni Factory!*\n\n"
        f"Dear {details['contact_person']},\n\n"
        f"We are pleased to welcome *{details['company_name']}* as a Manufacturer Partner on Apni Factory.\n\n"
        f"Your company has been successfully onboarded on our platform.\n\n"
        f"*What happens next?*\n\n"
        f"Our team will take care of the process of setting up your products and brands on Apni Factory.\n\n"
        f"You may simply coordinate with our team for:\n"
        f"• Product & brand information\n"
        f"• Pricing & MOQ confirmation\n"
        f"• Any additional information required\n\n"
        f"Once your catalogue is ready and approved, your products will be available for B2B buyers on the Apni Factory platform.\n\n"
        f"*Seller ID:* {details['seller_id']}\n\n"
        f"Our team will stay in touch with you throughout the process.\n\n"
        f"Welcome aboard! 🇮🇳\n\n"
        f"*Apni Factory*\n"
        f"*Bharat Jodo*\n"
        f"India’s B2B Marketplace"
    )


def build_welcome_email_content(details):
    """
    Builds subject, plain text body, and responsive HTML email for seller onboarding.
    """
    subject = f"Welcome to Apni Factory – {details['company_name']} 🎉"

    plain_body = (
        f"Dear {details['contact_person']},\n\n"
        f"Welcome to Apni Factory.\n\n"
        f"We are pleased to confirm that {details['company_name']} has been successfully onboarded as a Manufacturer Partner on our platform.\n\n"
        f"Seller Details\n\n"
        f"Company: {details['company_name']}\n"
        f"Seller ID: {details['seller_id']}\n"
        f"GSTIN: {details['gstin']}\n"
        f"Contact Person: {details['contact_person']}\n\n"
        f"What happens next?\n\n"
        f"You don’t need to worry about setting up everything yourself.\n\n"
        f"Our Apni Factory team will assist with the product catalogue and platform setup. We will coordinate with you whenever we require product information, pricing, MOQ or any other details.\n\n"
        f"Once the catalogue is completed and approved, your products will be made available to B2B buyers on Apni Factory.\n\n"
        f"We look forward to building a successful business relationship with {details['company_name']}.\n\n"
        f"Welcome to the Apni Factory family.\n\n"
        f"Bharat Jodo 🇮🇳\n\n"
        f"Team Apni Factory\n"
        f"India’s B2B Marketplace\n"
        f"🌐 apnifactory.co.in\n"
        f"📱 {details['support_number']}\n"
    )

    safe_contact = escape(details['contact_person'])
    safe_company = escape(details['company_name'])
    safe_seller_id = escape(details['seller_id'])
    safe_gstin = escape(details['gstin'])
    safe_support = escape(details['support_number'])

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(subject)}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f4f6f8;
      color: #2b2d42;
    }}
    .email-wrapper {{
      max-width: 600px;
      margin: 20px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 16px rgba(0,0,0,0.06);
      border: 1px solid #e5e7eb;
    }}
    .header {{
      background: linear-gradient(135deg, #d9381e 0%, #ee4d2d 100%);
      color: #ffffff;
      padding: 30px 24px;
      text-align: center;
    }}
    .header h1 {{
      margin: 0;
      font-size: 26px;
      letter-spacing: -0.5px;
      font-weight: 800;
    }}
    .header .subtitle {{
      margin-top: 6px;
      font-size: 13px;
      opacity: 0.92;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .content {{
      padding: 32px 28px;
      line-height: 1.65;
      font-size: 15px;
    }}
    .badge {{
      display: inline-block;
      background: #eef2ff;
      color: #4338ca;
      font-weight: 700;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 9999px;
      margin-bottom: 12px;
    }}
    .details-card {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 18px 20px;
      margin: 24px 0;
    }}
    .details-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .details-table td {{
      padding: 8px 0;
      border-bottom: 1px dashed #e2e8f0;
    }}
    .details-table tr:last-child td {{
      border-bottom: none;
    }}
    .details-label {{
      color: #64748b;
      font-weight: 600;
      width: 38%;
    }}
    .details-value {{
      color: #0f172a;
      font-weight: 700;
    }}
    .reassurance-box {{
      background: #f0fdf4;
      border-left: 4px solid #22c55e;
      padding: 16px 18px;
      border-radius: 4px;
      margin: 24px 0;
    }}
    .reassurance-box h3 {{
      margin-top: 0;
      margin-bottom: 8px;
      font-size: 16px;
      color: #15803d;
    }}
    .footer {{
      background: #fafafa;
      border-top: 1px solid #e5e7eb;
      padding: 24px;
      text-align: center;
      font-size: 13px;
      color: #6b7280;
    }}
    .footer a {{
      color: #d9381e;
      text-decoration: none;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="header">
      <h1>Apni Factory</h1>
      <div class="subtitle">Bharat Jodo 🇮🇳 | India’s B2B Marketplace</div>
    </div>
    <div class="content">
      <div class="badge">Official Manufacturer Partner</div>
      <p style="font-size: 17px; margin-top: 0;"><strong>Dear {safe_contact},</strong></p>
      <p>Welcome to <strong>Apni Factory</strong>.</p>
      <p>We are pleased to confirm that <strong>{safe_company}</strong> has been successfully onboarded as a Manufacturer Partner on our platform.</p>

      <div class="details-card">
        <h4 style="margin: 0 0 10px 0; color: #1e293b; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Seller Details</h4>
        <table class="details-table">
          <tr>
            <td class="details-label">Company:</td>
            <td class="details-value">{safe_company}</td>
          </tr>
          <tr>
            <td class="details-label">Seller ID:</td>
            <td class="details-value"><span style="background: #fef08a; padding: 2px 6px; border-radius: 4px; color: #854d0e;">{safe_seller_id}</span></td>
          </tr>
          <tr>
            <td class="details-label">GSTIN:</td>
            <td class="details-value">{safe_gstin}</td>
          </tr>
          <tr>
            <td class="details-label">Contact Person:</td>
            <td class="details-value">{safe_contact}</td>
          </tr>
        </table>
      </div>

      <div class="reassurance-box">
        <h3>What happens next?</h3>
        <p style="margin: 0 0 10px 0;"><strong>You don’t need to worry about setting up everything yourself.</strong></p>
        <p style="margin: 0 0 10px 0; font-size: 14px; color: #334155;">
          Our Apni Factory team will assist with the product catalogue and platform setup. We will coordinate with you whenever we require product information, pricing, MOQ or any other details.
        </p>
        <p style="margin: 0; font-size: 14px; color: #334155;">
          Once the catalogue is completed and approved, your products will be made available to B2B buyers across India on Apni Factory.
        </p>
      </div>

      <p>We look forward to building a successful business relationship with <strong>{safe_company}</strong>.</p>
      <p style="margin-bottom: 0;">Welcome to the Apni Factory family!</p>
    </div>

    <div class="footer">
      <p style="font-weight: 700; color: #111827; margin: 0 0 4px 0;">Bharat Jodo 🇮🇳</p>
      <p style="margin: 0 0 10px 0;"><strong>Team Apni Factory</strong> — India’s B2B Marketplace</p>
      <p style="margin: 0 0 4px 0;">🌐 <a href="https://apnifactory.co.in" target="_blank">apnifactory.co.in</a></p>
      <p style="margin: 0;">📱 Support & Operations: <strong>{safe_support}</strong></p>
    </div>
  </div>
</body>
</html>
"""
    return {
        'subject': subject,
        'plain_body': plain_body,
        'html_body': html_body,
    }


def generate_whatsapp_web_url(phone, message_text):
    """
    Generates a direct Click-to-Chat WhatsApp Web / Mobile URL with pre-filled message.
    """
    if not phone:
        return ""
    clean_number = format_whatsapp_phone(phone)
    if not clean_number:
        return ""
    encoded_text = urllib.parse.quote(message_text)
    return f"https://wa.me/{clean_number}?text={encoded_text}"


def send_seller_welcome_communications(h_user, send_whatsapp=True, send_email=True, force=False):
    """
    Dispatches the reassuring welcome WhatsApp and/or Email communications to an external seller.
    Updates the SellerOnboardingTracker in the local database.

    Returns:
        dict: {
            'whatsapp_attempted': bool,
            'whatsapp_success': bool,
            'whatsapp_error': str or None,
            'email_attempted': bool,
            'email_success': bool,
            'email_error': str or None,
            'details': dict,
            'tracker': SellerOnboardingTracker,
            'whatsapp_web_url': str,
        }
    """
    details = get_seller_contact_details(h_user)
    tracker, _ = SellerOnboardingTracker.objects.get_or_create(hostinger_user_id=h_user.id)

    wa_msg = build_welcome_whatsapp_message(details)
    email_data = build_welcome_email_content(details)
    wa_web_url = generate_whatsapp_web_url(details['phone'], wa_msg)

    result = {
        'whatsapp_attempted': False,
        'whatsapp_success': tracker.welcome_whatsapp_sent,
        'whatsapp_error': None,
        'email_attempted': False,
        'email_success': tracker.welcome_email_sent,
        'email_error': None,
        'details': details,
        'tracker': tracker,
        'whatsapp_web_url': wa_web_url,
    }

    # 1. WhatsApp Dispatch via Meta Cloud API
    if send_whatsapp and (force or not tracker.welcome_whatsapp_sent):
        result['whatsapp_attempted'] = True
        if not details['phone']:
            result['whatsapp_success'] = False
            result['whatsapp_error'] = "No valid mobile number found for this seller/company."
            tracker.welcome_whatsapp_error = result['whatsapp_error']
        else:
            success, wamid, error_msg = send_text_message(details['phone'], wa_msg, return_details=True)
            if success:
                result['whatsapp_success'] = True
                result['whatsapp_error'] = None
                tracker.welcome_whatsapp_sent = True
                tracker.welcome_whatsapp_sent_at = timezone.now()
                tracker.welcome_whatsapp_error = ""
            else:
                result['whatsapp_success'] = False
                result['whatsapp_error'] = error_msg or "Meta API returned error"
                tracker.welcome_whatsapp_error = result['whatsapp_error']

    # 2. Email Dispatch via Django SMTP (EmailMultiAlternatives)
    if send_email and (force or not tracker.welcome_email_sent):
        result['email_attempted'] = True
        if not details['email']:
            result['email_success'] = False
            result['email_error'] = "No email address found for this seller."
            tracker.welcome_email_error = result['email_error']
        else:
            try:
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@apnifactory.co.in')
                msg = EmailMultiAlternatives(
                    subject=email_data['subject'],
                    body=email_data['plain_body'],
                    from_email=from_email,
                    to=[details['email']],
                )
                msg.attach_alternative(email_data['html_body'], "text/html")
                msg.send(fail_silently=False)

                result['email_success'] = True
                result['email_error'] = None
                tracker.welcome_email_sent = True
                tracker.welcome_email_sent_at = timezone.now()
                tracker.welcome_email_error = ""
            except Exception as e:
                result['email_success'] = False
                result['email_error'] = str(e)
                tracker.welcome_email_error = str(e)

    tracker.save()
    result['tracker'] = tracker
    return result
