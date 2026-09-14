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

def send_document_message(to_number, document_url, filename, caption=None, return_details=False):
    """
    Sends a WhatsApp document (e.g. PDF) via Meta Cloud API.
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

    doc_obj = {
        "link": document_url,
        "filename": filename,
    }
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
