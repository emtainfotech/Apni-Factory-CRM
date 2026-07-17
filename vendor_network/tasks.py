import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from celery import shared_task
from django.utils import timezone
from .models import VendorProfile

logger = logging.getLogger(__name__)

# Regular expressions for data extraction
# Basic email regex
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Mobile regex for India: Optional +91, 0, or spacing, followed by 10 digits starting with 6-9
MOBILE_REGEX = re.compile(r'(?:(?:\+|0{0,2})91[\s-]?)?[6-9]\d{2}[\s-]?\d{3}[\s-]?\d{4}')

@shared_task(bind=True, max_retries=3)
def enrich_vendor_contacts(self, vendor_id: int):
    """
    Celery task to scrape a vendor's website for missing contact information (email, mobile).
    Implements exponential backoff via Celery max_retries.
    """
    try:
        vendor = VendorProfile.objects.get(id=vendor_id)
    except VendorProfile.DoesNotExist:
        logger.error(f"VendorProfile {vendor_id} does not exist.")
        return

    if not vendor.website_url:
        vendor.enrichment_status = 'NO_WEBSITE'
        vendor.save()
        return

    # Check if we actually need enrichment
    if vendor.email_address and vendor.mobile_number:
        vendor.enrichment_status = 'SCRAPED_SUCCESS'
        vendor.save()
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    pages_to_check = [vendor.website_url]
    # Add common contact pages to check if homepage fails to yield full info
    base_url = vendor.website_url.rstrip('/')
    pages_to_check.extend([f"{base_url}/contact", f"{base_url}/about", f"{base_url}/contact-us"])

    found_email = vendor.email_address
    found_mobile = vendor.mobile_number

    for page_url in pages_to_check:
        try:
            response = requests.get(page_url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text(separator=' ')
            
            # 1. Search for mailto: links
            if not found_email:
                for a_tag in soup.find_all('a', href=True):
                    if a_tag['href'].startswith('mailto:'):
                        found_email = a_tag['href'].replace('mailto:', '').split('?')[0].strip()
                        break
                        
            # 2. Regex fallback for email in text
            if not found_email:
                emails = EMAIL_REGEX.findall(text_content)
                if emails:
                    found_email = emails[0]
                    
            # 3. Regex for mobile
            if not found_mobile:
                mobiles = MOBILE_REGEX.findall(text_content)
                if mobiles:
                    # Clean up spacing
                    clean_mobile = re.sub(r'[\s-]', '', mobiles[0])
                    found_mobile = clean_mobile

            # Stop hitting subpages if we got both
            if found_email and found_mobile:
                break
                
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Failed to reach {page_url}: {exc}")
            # If it's the very first URL (homepage) and it completely fails with connection error, retry later
            if page_url == vendor.website_url:
                try:
                    # Retry with exponential backoff (countdown = 2^retries * 10 seconds)
                    self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
                except self.MaxRetriesExceededError:
                    logger.error(f"Max retries exceeded for {vendor.website_url}")
                    vendor.enrichment_status = 'SCRAPED_FAILED'
                    vendor.save()
                    return

    # Update the vendor profile
    updated = False
    if found_email and not vendor.email_address:
        vendor.email_address = found_email
        updated = True
        
    if found_mobile and not vendor.mobile_number:
        vendor.mobile_number = found_mobile
        updated = True

    vendor.enrichment_status = 'SCRAPED_SUCCESS'
    vendor.save()
    
    logger.info(f"Enrichment completed for {vendor.store_name}. Updated: {updated}")
    return {"updated": updated, "email": found_email, "mobile": found_mobile}
