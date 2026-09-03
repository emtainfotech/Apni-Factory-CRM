import requests
import time
import logging
from typing import Dict, Any
from django.db import transaction
from vendor_network.models import VendorProfile

logger = logging.getLogger(__name__)

def fetch_and_sync_osm_vendors(city_name: str = "Indore", user=None, party_type: str = 'SELLER') -> Dict[str, Any]:
    """
    Fetches shop nodes from Overpass API for a given city and syncs them to the VendorProfile model.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json][timeout:25];
    area[name="{city_name}"]->.searchArea;
    (
      node["shop"](area.searchArea);
    );
    out body;
    >;
    out skel qt;
    """
    
    headers = {
        'User-Agent': 'ApniFactoryCRM/2.0 (Contact: admin@apnifactory.co.in)'
    }
    
    try:
        response = requests.get(overpass_url, params={'data': query}, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch from Overpass API: {e}")
        # Fallback to search_and_sync_osm
        return search_and_sync_osm(query=city_name, user=user, party_type=party_type)

    elements = data.get('elements', [])
    synced_count = 0
    
    with transaction.atomic():
        for element in elements:
            if element.get('type') != 'node':
                continue
                
            tags = element.get('tags', {})
            store_name = tags.get('name')
            if not store_name:
                continue
                
            place_id = f"node_{element.get('id')}"
            category = tags.get('shop', 'General Store').replace('_', ' ').title()
            latitude = element.get('lat')
            longitude = element.get('lon')
            
            phone_number = tags.get('contact:phone') or tags.get('phone')
            mobile_number = tags.get('contact:mobile') or tags.get('mobile')
            website = tags.get('contact:website') or tags.get('website')
            email = tags.get('contact:email') or tags.get('email')
            
            street_address = tags.get('addr:street', '')
            city = tags.get('addr:city', city_name)
            state = tags.get('addr:state', '')
            pincode = tags.get('addr:postcode', '')
            full_address = f"{street_address}, {city}".strip(', ')
            
            VendorProfile.objects.update_or_create(
                place_id=place_id,
                defaults={
                    'store_name': store_name,
                    'category': category,
                    'party_type': party_type,
                    'latitude': latitude,
                    'longitude': longitude,
                    'street_address': full_address,
                    'city': city,
                    'state': state,
                    'pincode': pincode,
                    'phone_number': phone_number,
                    'mobile_number': mobile_number,
                    'website_url': website,
                    'email_address': email,
                    'created_by': user,
                    'assigned_to': user,
                }
            )
            synced_count += 1
        
    return {"status": "success", "synced_count": synced_count}


def search_and_sync_osm(query: str, user=None, party_type: str = 'SELLER') -> Dict[str, Any]:
    """
    Fallback search using OpenStreetMap / Nominatim API to find places based on text search.
    """
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    headers = {
        'User-Agent': 'ApniFactoryCRM/2.0 (Contact: admin@apnifactory.co.in)'
    }
    params = {
        'q': query,
        'format': 'json',
        'addressdetails': 1,
        'limit': 25,
        'countrycodes': 'in'
    }

    try:
        response = requests.get(nominatim_url, params=params, headers=headers, timeout=12)
        response.raise_for_status()
        places = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch from Nominatim: {e}")
        return {"status": "error", "message": str(e), "synced_count": 0}

    synced_count = 0
    with transaction.atomic():
        for place in places:
            place_id = str(place.get('place_id', ''))
            if not place_id:
                continue

            display_name = place.get('display_name', '')
            name = place.get('name') or display_name.split(',')[0]
            lat = place.get('lat')
            lon = place.get('lon')
            category = place.get('type', place.get('class', 'Commercial')).replace('_', ' ').title()

            address = place.get('address', {})
            city = address.get('city') or address.get('town') or address.get('state_district') or address.get('county', '')
            state = address.get('state', '')
            pincode = address.get('postcode', '')

            VendorProfile.objects.update_or_create(
                place_id=f"osm_{place_id}",
                defaults={
                    'store_name': name,
                    'category': category,
                    'party_type': party_type,
                    'latitude': lat,
                    'longitude': lon,
                    'street_address': display_name,
                    'city': city,
                    'state': state,
                    'pincode': pincode,
                    'created_by': user,
                    'assigned_to': user,
                }
            )
            synced_count += 1

    return {"status": "success", "synced_count": synced_count, "results_found": len(places)}
