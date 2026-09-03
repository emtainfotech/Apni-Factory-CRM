import os
import requests
import logging
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from vendor_network.models import VendorProfile
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv(settings.BASE_DIR / '.env')

def fetch_and_save_google_places(query: str, user=None, party_type: str = 'SELLER') -> dict:
    """
    Fetches places from Google Places API using Text Search.
    Saves them to the database associated with user and party_type ('SELLER' vs 'BUYER').
    """
    api_key = os.environ.get('GOOGLE_PLACES_API_KEY') or getattr(settings, 'GOOGLE_PLACES_API_KEY', '')
    if not api_key or api_key == 'your_google_places_api_key_here':
        # Fallback to OpenStreetMap text search if Google key is not set
        try:
            from .osm_fetcher import search_and_sync_osm
            return search_and_sync_osm(query=query, user=user, party_type=party_type)
        except Exception as e:
            return {"status": "error", "message": f"Google Places API key is not configured and OSM fallback failed: {e}", "synced_count": 0}

    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.location,places.primaryType,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.addressComponents'
    }

    synced_count = 0
    results_found = 0
    payload = {
        'textQuery': query,
        'pageSize': 20
    }

    try:
        response = requests.post(search_url, headers=headers, json=payload, timeout=12)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Places Search API Error: {e}")
        # Try OSM fallback
        try:
            from .osm_fetcher import search_and_sync_osm
            return search_and_sync_osm(query=query, user=user, party_type=party_type)
        except Exception:
            return {"status": "error", "message": str(e), "synced_count": synced_count}

    results = data.get('places', [])
    results_found += len(results)

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

            category = place.get('primaryType', 'Store / Business').replace('_', ' ').title()
            phone_number = place.get('nationalPhoneNumber')
            website = place.get('websiteUri')
            rating = place.get('rating')
            user_ratings_total = place.get('userRatingCount', 0)

            # Extract City, State, Pincode from addressComponents
            city = ''
            state = ''
            pincode = ''
            for comp in place.get('addressComponents', []):
                types = comp.get('types', [])
                if 'locality' in types or 'administrative_area_level_2' in types:
                    if not city:
                        city = comp.get('longText', '')
                elif 'administrative_area_level_1' in types:
                    state = comp.get('longText', '')
                elif 'postal_code' in types:
                    pincode = comp.get('longText', '')

            # Check for duplicacy on the basis of mobile/phone number
            if phone_number:
                existing = VendorProfile.objects.filter(
                    Q(phone_number=phone_number) | Q(mobile_number=phone_number)
                ).exclude(place_id=place_id).first()
                if existing:
                    # If existing belongs to this user or unassigned, update assignment
                    if user and not existing.created_by:
                        existing.created_by = user
                        existing.assigned_to = user
                        existing.party_type = party_type
                        existing.save()
                    continue

            # Update or create
            vendor_obj, created = VendorProfile.objects.update_or_create(
                place_id=place_id,
                defaults={
                    'store_name': store_name,
                    'category': category,
                    'party_type': party_type,
                    'latitude': lat,
                    'longitude': lng,
                    'street_address': address,
                    'city': city,
                    'state': state,
                    'pincode': pincode,
                    'phone_number': phone_number,
                    'mobile_number': phone_number,
                    'website_url': website,
                    'rating': rating,
                    'user_ratings_total': user_ratings_total,
                    'created_by': user if user else None,
                    'assigned_to': user if user else None,
                }
            )
            synced_count += 1

    return {"status": "success", "synced_count": synced_count, "results_found": results_found}
