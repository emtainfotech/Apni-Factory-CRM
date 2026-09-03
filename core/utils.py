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

def send_text_message(to_number, text):
    """Sends a standard WhatsApp text message via Meta Cloud API."""
    clean_number = format_whatsapp_phone(to_number)
    if not clean_number:
        return False

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
        if response.status_code == 200:
            return True
        else:
            print(f"Meta API Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"Meta API Dispatch Exception: {e}")
        return False

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
