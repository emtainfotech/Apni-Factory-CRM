import os
import json
import time
import random
import jwt
import requests
from django.conf import settings

GST_PARTNER_ID = getattr(settings, 'GST_PARTNER_ID', 'CORP00002370')
GST_SECRET_KEY = getattr(settings, 'GST_SECRET_KEY', '')
GST_LIVE_URL = getattr(settings, 'GST_LIVE_URL', 'https://api.verifya2z.com/api/v1/verification/gst_verify')
META_API_URL = getattr(settings, 'META_API_URL', 'https://graph.facebook.com/v17.0/960010463853608/messages')
META_ACCESS_TOKEN = getattr(settings, 'META_ACCESS_TOKEN', '')

def generate_live_token():
    """Generates JWT Token for SprintVerify"""
    payload = {
        "timestamp": int(time.time()),
        "partnerId": GST_PARTNER_ID,
        "reqid": str(random.randint(100000, 9999999))
    }
    token = jwt.encode(payload, GST_SECRET_KEY, algorithm="HS256")
    return token

DEFAULT_SELLER_ONBOARDING_TEXT = """🌟 *Welcome to Apni Factory!* 🌟

Dear Sir/Madam,

Greetings from *Apni Factory*! 👋
We are delighted to invite you to join Apni Factory as a Seller/Vendor and showcase your products to customers across India. 🛍️📦

To complete your Seller Registration & Verification, kindly keep the following documents/details ready:

🔗 *Complete Seller Registration Here:*
https://panel.apnifactory.co.in/register

Once you have completed the registration, please share the required documents/details with our team for verification and onboarding.

🤝 *Join Apni Factory and grow your business with a digital B2B marketplace.*

Thank you for choosing Apni Factory.
We look forward to welcoming you to our seller network! 🚀

*Apni Factory*
H Bose E-Commerce Pvt. Ltd.
📞 +91 7648911811
🌐 https://apnifactory.co.in/
📘 https://www.facebook.com/apnifactoryapp/
📷 https://www.instagram.com/apnifactory_app/
📧 communication@apnifactory.co.in"""

DEFAULT_SELLER_GUIDE_PDF_FILENAME = "Apni_Factory_Seller_Onboarding_Guide_Final.pdf"
DEFAULT_SELLER_GUIDE_PDF_PATH = "whatsapp_attachments/Apni_Factory_Seller_Onboarding_Guide_Final.pdf"
DEFAULT_SELLER_GUIDE_PUBLIC_URL = "https://crm.apnifactory.co.in/media/documents/Apni_Factory_Seller_Onboarding_Guide_Final.pdf"

def format_whatsapp_phone(raw_phone):
    """Normalizes phone number to international E.164 without leading plus."""
    digits = ''.join(c for c in str(raw_phone) if c.isdigit())
    if len(digits) == 10:
        return '91' + digits
    elif len(digits) == 11 and digits.startswith('0'):
        return '91' + digits[1:]
    elif len(digits) == 12 and digits.startswith('91'):
        return digits
    return digits

def send_text_message(to_number, text, return_details=False):
    """
    Sends a standard WhatsApp text message via Meta Cloud API.
    If return_details=True: returns (success: bool, wamid: str, error_msg: str)
    If return_details=False: returns success: bool
    """
    clean_number = format_whatsapp_phone(to_number)
    if not clean_number:
        return (False, None, "Invalid phone number") if return_details else False

    meta_url = getattr(settings, 'META_API_URL', os.environ.get('META_API_URL', 'https://graph.facebook.com/v17.0/960010463853608/messages'))
    meta_token = getattr(settings, 'META_ACCESS_TOKEN', os.environ.get('META_ACCESS_TOKEN', ''))

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_number,
        "type": "text",
        "text": {"body": text}
    }
    try:
        headers = {
            "Authorization": f"Bearer {meta_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(meta_url, headers=headers, json=payload, timeout=10)
        resp_data = response.json() if response.text else {}
        if response.status_code == 200:
            messages = resp_data.get('messages', [])
            wamid = messages[0].get('id') if messages else None
            return (True, wamid, None) if return_details else True
        else:
            err_msg = resp_data.get('error', {}).get('message') or response.text
            print(f"Meta API Error ({response.status_code}): {err_msg}")
            return (False, None, err_msg) if return_details else False
    except Exception as e:
        print(f"Meta API Dispatch Exception: {e}")
        return (False, None, str(e)) if return_details else False

def upload_media_to_meta(file_content, filename, mime_type):
    """
    Uploads a media file directly to Meta WhatsApp Media endpoint.
    Returns: (success: bool, media_id: str, error_msg: str)
    """
    meta_url = getattr(settings, 'META_API_URL', os.environ.get('META_API_URL', 'https://graph.facebook.com/v17.0/960010463853608/messages'))
    # Extract base graph URL up to phone number ID: e.g. https://graph.facebook.com/v17.0/960010463853608/media
    media_url = meta_url.rstrip('/').rsplit('/', 1)[0] + '/media'
    meta_token = getattr(settings, 'META_ACCESS_TOKEN', os.environ.get('META_ACCESS_TOKEN', ''))

    headers = {
        "Authorization": f"Bearer {meta_token}",
    }
    files = {
        'file': (filename, file_content, mime_type),
    }
    data = {
        'messaging_product': 'whatsapp',
        'type': mime_type,
    }
    try:
        response = requests.post(media_url, headers=headers, files=files, data=data, timeout=25)
        resp_data = response.json() if response.text else {}
        if response.status_code == 200 and resp_data.get('id'):
            return (True, resp_data.get('id'), None)
        else:
            err_msg = resp_data.get('error', {}).get('message') or response.text
            print(f"Meta API Media Upload Error ({response.status_code}): {err_msg}")
            return (False, None, err_msg)
    except Exception as e:
        print(f"Meta API Media Upload Exception: {e}")
        return (False, None, str(e))

def send_image_message(to_number, image_url=None, media_id=None, caption=None, return_details=False):
    """
    Sends a WhatsApp image via Meta Cloud API using either public link or media_id.
    """
    clean_number = format_whatsapp_phone(to_number)
    if not clean_number:
        return (False, None, "Invalid phone number") if return_details else False

    meta_url = getattr(settings, 'META_API_URL', os.environ.get('META_API_URL', 'https://graph.facebook.com/v17.0/960010463853608/messages'))
    meta_token = getattr(settings, 'META_ACCESS_TOKEN', os.environ.get('META_ACCESS_TOKEN', ''))

    img_obj = {}
    if media_id:
        img_obj["id"] = media_id
    elif image_url:
        img_obj["link"] = image_url
    else:
        return (False, None, "Neither image_url nor media_id provided") if return_details else False

    if caption:
        img_obj["caption"] = caption[:1024]

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_number,
        "type": "image",
        "image": img_obj
    }
    try:
        headers = {
            "Authorization": f"Bearer {meta_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(meta_url, headers=headers, json=payload, timeout=12)
        resp_data = response.json() if response.text else {}
        if response.status_code == 200:
            messages = resp_data.get('messages', [])
            wamid = messages[0].get('id') if messages else None
            return (True, wamid, None) if return_details else True
        else:
            err_msg = resp_data.get('error', {}).get('message') or response.text
            print(f"Meta API Image Error ({response.status_code}): {err_msg}")
            return (False, None, err_msg) if return_details else False
    except Exception as e:
        print(f"Meta API Image Exception: {e}")
        return (False, None, str(e)) if return_details else False

def send_document_message(to_number, document_url=None, filename=None, caption=None, media_id=None, return_details=False):
    """
    Sends a WhatsApp document (e.g. PDF, Word, Excel) via Meta Cloud API using either public link or media_id.
    If return_details=True: returns (success: bool, wamid: str, error_msg: str)
    If return_details=False: returns success: bool
    """
    clean_number = format_whatsapp_phone(to_number)
    if not clean_number:
        return (False, None, "Invalid phone number") if return_details else False

    meta_url = getattr(settings, 'META_API_URL', os.environ.get('META_API_URL', 'https://graph.facebook.com/v17.0/960010463853608/messages'))
    meta_token = getattr(settings, 'META_ACCESS_TOKEN', os.environ.get('META_ACCESS_TOKEN', ''))

    # Meta limits document caption to 1024 characters
    truncated_caption = None
    if caption:
        truncated_caption = caption[:1024]

    doc_obj = {}
    if media_id:
        doc_obj["id"] = media_id
    elif document_url:
        doc_obj["link"] = document_url
    else:
        return (False, None, "Neither document_url nor media_id provided") if return_details else False

    if filename:
        doc_obj["filename"] = filename
    if truncated_caption:
        doc_obj["caption"] = truncated_caption

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_number,
        "type": "document",
        "document": doc_obj
    }
    try:
        headers = {
            "Authorization": f"Bearer {meta_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(meta_url, headers=headers, json=payload, timeout=12)
        resp_data = response.json() if response.text else {}
        if response.status_code == 200:
            messages = resp_data.get('messages', [])
            wamid = messages[0].get('id') if messages else None
            return (True, wamid, None) if return_details else True
        else:
            err_msg = resp_data.get('error', {}).get('message') or response.text
            print(f"Meta API Document Error ({response.status_code}): {err_msg}")
            return (False, None, err_msg) if return_details else False
    except Exception as e:
        print(f"Meta API Document Exception: {e}")
        return (False, None, str(e)) if return_details else False

def send_template_message(to_number, template_name, language_code='en', components=None, return_details=False):
    """
    Sends an approved Meta WhatsApp template message via Meta Cloud API.
    Handles language fallback (en <-> en_US).
    """
    clean_number = format_whatsapp_phone(to_number)
    if not clean_number:
        return (False, None, "Invalid phone number") if return_details else False

    meta_url = getattr(settings, 'META_API_URL', os.environ.get('META_API_URL', 'https://graph.facebook.com/v17.0/960010463853608/messages'))
    meta_token = getattr(settings, 'META_ACCESS_TOKEN', os.environ.get('META_ACCESS_TOKEN', ''))

    template_obj = {
        "name": template_name,
        "language": {"code": language_code}
    }
    if components:
        template_obj["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_number,
        "type": "template",
        "template": template_obj
    }

    try:
        headers = {
            "Authorization": f"Bearer {meta_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(meta_url, headers=headers, json=payload, timeout=12)
        resp_data = response.json() if response.text else {}

        if response.status_code == 200:
            messages = resp_data.get('messages', [])
            wamid = messages[0].get('id') if messages else None
            return (True, wamid, None) if return_details else True

        err_code = resp_data.get('error', {}).get('code')
        err_subcode = resp_data.get('error', {}).get('error_subcode')
        # If language code was 'en' and failed with 132000 (translation not found), retry with 'en_US'
        if (err_code == 132000 or err_subcode == 132000) and language_code == 'en':
            template_obj['language']['code'] = 'en_US'
            response2 = requests.post(meta_url, headers=headers, json=payload, timeout=12)
            resp_data2 = response2.json() if response2.text else {}
            if response2.status_code == 200:
                messages2 = resp_data2.get('messages', [])
                wamid2 = messages2[0].get('id') if messages2 else None
                return (True, wamid2, None) if return_details else True
            err_msg = resp_data2.get('error', {}).get('message') or response2.text
            return (False, None, err_msg) if return_details else False

        err_msg = resp_data.get('error', {}).get('message') or response.text
        print(f"Meta API Template Error ({response.status_code}): {err_msg}")
        return (False, None, err_msg) if return_details else False
    except Exception as e:
        print(f"Meta API Template Exception: {e}")
        return (False, None, str(e)) if return_details else False

def send_seller_onboarding_template(to_number, document_url=None, document_filename=None, return_details=False):
    """
    Sends the pre-approved Meta template 'seller_onboarding_details_template'
    with the Seller Onboarding Guide PDF in the document header.
    """
    doc_url = document_url or DEFAULT_SELLER_GUIDE_PUBLIC_URL
    doc_fn = document_filename or DEFAULT_SELLER_GUIDE_PDF_FILENAME

    components = [
        {
            "type": "header",
            "parameters": [
                {
                    "type": "document",
                    "document": {
                        "link": doc_url,
                        "filename": doc_fn
                    }
                }
            ]
        }
    ]
    template_name = getattr(settings, 'WHATSAPP_SELLER_ONBOARDING_TEMPLATE', 'seller_onboarding_details_template')
    return send_template_message(
        to_number,
        template_name=template_name,
        language_code='en',
        components=components,
        return_details=return_details
    )

def get_whatsapp_window_status(customer=None, phone=None):
    """
    Checks whether the Meta WhatsApp 24-hour customer service window is open.
    The window opens when a customer sends an incoming message and stays open for 24h.
    Outside the window, Meta rejects free-form messages with error 131047 (Re-engagement message).
    """
    from core.models import WhatsAppChat, WhatsAppMessageStatus
    from django.utils import timezone
    from django.db.models import Q

    clean_phone = format_whatsapp_phone(phone) if phone else None
    if not clean_phone and customer:
        clean_phone = format_whatsapp_phone(customer.whatsapp_number or customer.phone)

    # 1. Find latest incoming message
    incoming_query = WhatsAppChat.objects.filter(direction='incoming')
    if customer:
        incoming_query = incoming_query.filter(customer=customer)
    elif clean_phone:
        short_phone = clean_phone[2:] if clean_phone.startswith('91') and len(clean_phone) == 12 else clean_phone
        incoming_query = incoming_query.filter(
            Q(customer__phone__in=[clean_phone, short_phone]) |
            Q(customer__whatsapp_number__in=[clean_phone, short_phone])
        )

    last_incoming = incoming_query.order_by('-timestamp').first()

    # 2. Check latest 131047 failure
    last_131047 = None
    if clean_phone:
        last_131047 = WhatsAppMessageStatus.objects.filter(
            recipient_id=clean_phone,
            status='failed',
            error_code='131047'
        ).order_by('-timestamp').first()

    now = timezone.now()
    if last_incoming and last_incoming.timestamp:
        # If a 131047 occurred after the last incoming message, window is closed
        if last_131047 and last_131047.timestamp and last_131047.timestamp > last_incoming.timestamp:
            return {
                'is_open': False,
                'remaining_seconds': 0,
                'formatted_remaining': 'Expired (Template Mode)',
                'last_incoming_time': last_incoming.timestamp,
                'status_mode': 'template',
            }

        elapsed = (now - last_incoming.timestamp).total_seconds()
        if elapsed < 86400:
            remaining = int(86400 - elapsed)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            formatted = f"{hours}h {minutes}m left" if hours > 0 else f"{minutes}m left"
            return {
                'is_open': True,
                'remaining_seconds': remaining,
                'formatted_remaining': formatted,
                'last_incoming_time': last_incoming.timestamp,
                'status_mode': 'freeform',
            }

    return {
        'is_open': False,
        'remaining_seconds': 0,
        'formatted_remaining': 'Expired (Template Mode)',
        'last_incoming_time': last_incoming.timestamp if last_incoming else None,
        'status_mode': 'template',
    }

def format_india_time(dt, format_str='%I:%M %p | %d %b'):
    """
    Safely converts any datetime to India Standard Time (Asia/Kolkata, UTC+05:30)
    and returns a formatted string.
    """
    if not dt:
        return ''
    from zoneinfo import ZoneInfo
    from django.utils import timezone
    ist = ZoneInfo("Asia/Kolkata")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.astimezone(ist).strftime(format_str)

def verify_gst_number_live(gst_number):
    """
    Verifies GST via SprintVerify API and maps response to CRM fields.
    Returns: (is_valid: bool, data: dict)
    """
    if not gst_number:
        return False, {}

    try:
        # 1. Prepare Request
        token = generate_live_token()
        refid = str(random.randint(100000, 999999))
        
        headers = {
            "Token": token,
            "User-Agent": GST_PARTNER_ID,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "refid": refid,
            "id_number": gst_number
        }

        # 2. Call API
        response = requests.post(
            GST_LIVE_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        data = response.json()
        
        # --- DEBUG PRINT ---
        # Keep this for a while to ensure you see the response in terminal
        print(f"GST API Response: {data}")

        # 3. Check Success (UPDATED LOGIC)
        # Your log shows: {'status': True, 'data': {...}}
        if data.get('status') is True and 'data' in data:
            result = data['data']
            
            address_obj = result.get('address', {})
            
            if isinstance(address_obj, dict):
                addr1 = address_obj.get('addr1', '')
                addr2 = address_obj.get('addr2', '')
                locality = address_obj.get('locality', '')
                city = address_obj.get('city', '')
                state = address_obj.get('state', '')
                pincode = address_obj.get('pin', '')
                
                parts = [p for p in [addr1, addr2, locality] if p]
                full_address = ", ".join(parts)
            else:
                full_address = str(address_obj)
                city = ''
                state = ''
                pincode = full_address.split()[-1] if full_address and full_address[-1].isdigit() else ''

            crm_data = {
                'legal_name': result.get('legal_name', ''),
                'trade_name': result.get('business_name', ''),
                'address': full_address,
                'city': city or result.get('city', ''),
                'state': state or result.get('state', ''),
                'pincode': pincode
            }
            return True, crm_data

        print(f"GST Verification Failed Logic. Data: {data}")
        return False, {}

    except Exception as e:
        print(f"GST Verification Error: {e}")
        return False, {}

import mimetypes
from django.core.files.base import ContentFile

def download_whatsapp_media(media_id):
    """Downloads media from WhatsApp API and returns a Django ContentFile and mime_type."""
    try:
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        }
        # 1. Get media URL
        url_response = requests.get(f"https://graph.facebook.com/v17.0/{media_id}", headers=headers)
        url_response.raise_for_status()
        url_data = url_response.json()
        
        media_url = url_data.get('url')
        mime_type = url_data.get('mime_type')
        
        if not media_url:
            return None, None
            
        # 2. Download actual binary data
        media_response = requests.get(media_url, headers=headers)
        media_response.raise_for_status()
        
        # Determine extension
        ext = mimetypes.guess_extension(mime_type) or '.bin'
        filename = f"{media_id}{ext}"
        
        content_file = ContentFile(media_response.content, name=filename)
        return content_file, mime_type
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None, None
