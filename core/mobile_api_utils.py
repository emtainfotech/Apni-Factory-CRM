import json
import time
import random
import jwt
import requests
from django.conf import settings

GST_PARTNER_ID = getattr(settings, 'GST_PARTNER_ID', 'CORP00002370')
GST_SECRET_KEY = getattr(settings, 'GST_SECRET_KEY', '')
GST_LIVE_URL = getattr(settings, 'GST_LIVE_URL', 'https://api.verifya2z.com/api/v1/verification/gst_verify')

def generate_mobile_token():
    """Generates JWT Token for API verification"""
    payload = {
        "timestamp": int(time.time()),
        "partnerId": GST_PARTNER_ID,
        "reqid": str(random.randint(100000, 9999999))
    }
    return jwt.encode(payload, GST_SECRET_KEY, algorithm="HS256")

def verify_gst_for_mobile(gst_number):
    """
    Standalone GST Verification utility for mobile app.
    Returns: (is_valid: bool, data: dict, error_message: str)
    """
    if not gst_number:
        return False, {}, "GST number is required"

    try:
        token = generate_mobile_token()
        headers = {
            "Token": token,
            "User-Agent": GST_PARTNER_ID,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "refid": str(random.randint(100000, 999999)),
            "id_number": gst_number.upper().strip()
        }

        response = requests.post(
            GST_LIVE_URL,
            json=payload,
            headers=headers,
            timeout=15
        )
        
        data = response.json()
        
        if data.get('status') is True and 'data' in data:
            result = data['data']
            
            # Extract Address
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
                city = result.get('city', '')
                state = result.get('state', '')
                pincode = ''

            # Structured response for Mobile App
            formatted_data = {
                'gstin': result.get('gstin', gst_number),
                'legal_name': result.get('legal_name', ''),
                'business_name': result.get('business_name', ''),
                'status': result.get('gstin_status', 'Active'),
                'taxpayer_type': result.get('taxpayer_type', ''),
                'registration_date': result.get('date_of_registration', ''),
                'address': {
                    'full': full_address,
                    'city': city,
                    'state': state,
                    'pincode': pincode
                }
            }
            return True, formatted_data, None

        return False, {}, data.get('message', "Invalid GST or API Error")

    except Exception as e:
        return False, {}, str(e)
