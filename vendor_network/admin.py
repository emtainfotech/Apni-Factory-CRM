from django.contrib import admin
from django.contrib import messages
from .models import VendorProfile
from .tasks import enrich_vendor_contacts

@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'category', 'mobile_number', 'email_address', 'enrichment_status')
    list_filter = ('enrichment_status', 'category')
    search_fields = ('store_name', 'phone_number', 'mobile_number', 'email_address')
    
    actions = ['trigger_enrichment']

    def trigger_enrichment(self, request, queryset):
        """
        Custom admin action to manually trigger the Celery enrichment task for selected vendors.
        """
        count = 0
        for vendor in queryset:
            # We can trigger it even if it was previously successful to force a re-scrape,
            # but usually we only want to do it if there's a website.
            if vendor.website_url:
                enrich_vendor_contacts.delay(vendor.id)
                count += 1
                
        self.message_user(
            request, 
            f"Successfully queued enrichment tasks for {count} vendors.",
            messages.SUCCESS
        )
    trigger_enrichment.short_description = "Run Website Scraper / Enrichment on selected vendors"
