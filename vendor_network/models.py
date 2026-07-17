from django.db import models

class VendorProfile(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Enrichment'),
        ('SCRAPED_SUCCESS', 'Enrichment Successful'),
        ('SCRAPED_FAILED', 'Enrichment Failed'),
        ('NO_WEBSITE', 'No Website Available'),
    ]

    osm_id = models.CharField(max_length=255, unique=True, db_index=True)
    store_name = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    street_address = models.TextField(blank=True, null=True)
    
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    mobile_number = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    
    website_url = models.URLField(max_length=500, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    
    enrichment_status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.store_name} ({self.category})"
