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

def send_text_message(to_number, text):
    """Sends a standard WhatsApp text message via Meta API."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    try:
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        requests.post(META_API_URL, headers=headers, json=payload)
    except Exception as e:
        print(f"Meta API Error: {e}")

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
            "User-Agent": PARTNER_ID,
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