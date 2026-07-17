import os
import requests
import logging
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from vendor_network.models import VendorProfile
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure .env is explicitly reloaded just in case the server hasn't restarted
load_dotenv(settings.BASE_DIR / '.env')

def fetch_and_save_google_places(query: str) -> dict:
    """
    Fetches places from Google Places API using Text Search.
    Saves them to the database efficiently.
    """
    api_key = os.environ.get('GOOGLE_PLACES_API_KEY')
    if not api_key or api_key == 'your_google_places_api_key_here':
        return {"status": "error", "message": "Google Places API key is not configured in .env", "synced_count": 0}

    # Using Places API (New) - Text Search
    search_url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.location,places.primaryType,places.nationalPhoneNumber,places.websiteUri,nextPageToken'
    }
    
    synced_count = 0
    results_found = 0
    
    payload = {
        'textQuery': query,
        'pageSize': 20
    }
    
    try:
        response = requests.post(search_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Places Search API Error: {e}")
        # Add response content if available to debug
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                # Return the whole JSON string for debugging
                import json
                error_msg = json.dumps(error_data)
            except ValueError:
                error_msg = str(e.response.text)
        
        # If it errors out, just return the error immediately
        return {"status": "error", "message": error_msg, "synced_count": synced_count}

    results = data.get('places', [])
    results_found += len(results)

    # We will use transaction.atomic() to avoid SQLite database lock
    with transaction.atomic():
        for place in results:
            place_id = place.get('id')
            if not place_id:
                continue
                
            store_name = place.get('displayName', {}).get('text', 'Unknown Store')
            address = place.get('formattedAddress', '')
            
            location = place.get('location', {})
            lat = location.get('latitude')
            lng = location.get('longitude')
            
            category = place.get('primaryType', 'store')
            phone_number = place.get('nationalPhoneNumber')
            website = place.get('websiteUri')
            
            # Check for duplicacy on the basis of mobile number (skip if phone exists on another place)
            if phone_number:
                if VendorProfile.objects.filter(
                    Q(phone_number=phone_number) | Q(mobile_number=phone_number)
                ).exclude(place_id=place_id).exists():
                    logger.info(f"Skipping {store_name} - duplicate phone number {phone_number}")
                    continue
                
            # Create or update in DB
            VendorProfile.objects.update_or_create(
                place_id=place_id,
                defaults={
                    'store_name': store_name,
                    'category': category,
                    'latitude': lat,
                    'longitude': lng,
                    'street_address': address,
                    'phone_number': phone_number,
                    'mobile_number': phone_number,  # Map it here for now
                    'website_url': website,
                }
            )
            synced_count += 1
                
    return {"status": "success", "synced_count": synced_count, "results_found": results_found}
