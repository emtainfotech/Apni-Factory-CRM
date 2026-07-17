import requests
import time
import logging
from typing import Dict, Any
from django.db import transaction
from vendor_network.models import VendorProfile

logger = logging.getLogger(__name__)

def fetch_and_sync_osm_vendors(city_name: str = "Indore") -> Dict[str, Any]:
    """
    Fetches shop nodes from Overpass API for a given city and syncs them to the VendorProfile model.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Overpass QL query to find all nodes tagged as "shop" in the given city
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
        'User-Agent': 'ApniFactoryCRM/1.0 (Contact: admin@apnifactory.com)'
    }
    
    try:
        response = requests.get(overpass_url, params={'data': query}, headers=headers)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch from Overpass API: {e}")
        return {"status": "error", "message": str(e), "synced_count": 0}

    elements = data.get('elements', [])
    synced_count = 0
    
    with transaction.atomic():
        for element in elements:
            if element.get('type') != 'node':
                continue
                
            tags = element.get('tags', {})
            
            # Skip if no name
            store_name = tags.get('name')
            if not store_name:
                continue
                
            osm_id = f"node/{element.get('id')}"
            category = tags.get('shop')
            latitude = element.get('lat')
            longitude = element.get('lon')
            
            # Extract Contacts
            phone_number = tags.get('contact:phone') or tags.get('phone')
            mobile_number = tags.get('contact:mobile') or tags.get('mobile')
            website = tags.get('contact:website') or tags.get('website')
            email = tags.get('contact:email') or tags.get('email')
            
            # Extract Address (Street)
            street_address = tags.get('addr:street', '')
            city = tags.get('addr:city', '')
            full_address = f"{street_address}, {city}".strip(', ')
            
            VendorProfile.objects.update_or_create(
                osm_id=osm_id,
                defaults={
                    'store_name': store_name,
                    'category': category,
                    'latitude': latitude,
                    'longitude': longitude,
                    'street_address': full_address,
                    'phone_number': phone_number,
                    'mobile_number': mobile_number,
                    'website_url': website,
                    'email_address': email,
                }
            )
            synced_count += 1
        
    logger.info(f"Successfully synced {synced_count} vendors from {city_name}.")
    
    # Sleep to respect Overpass API rate limits if called in a loop
    time.sleep(2)
    
    return {"status": "success", "synced_count": synced_count}
