from django.db import models
from django.conf import settings

class VendorProfile(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Enrichment'),
        ('SCRAPED_SUCCESS', 'Enrichment Successful'),
        ('SCRAPED_FAILED', 'Enrichment Failed'),
        ('NO_WEBSITE', 'No Website Available'),
        ('VERIFIED', 'Verified / Active'),
        ('CONTACTED', 'Contacted / Pitch Made'),
        ('CONVERTED', 'Converted to Customer'),
    ]

    PARTY_TYPE_CHOICES = [
        ('SELLER', 'Customer / Seller / Vendor'),
        ('BUYER', 'Buyer / Contractor'),
    ]

    place_id = models.CharField(max_length=255, unique=True, db_index=True)
    store_name = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    party_type = models.CharField(max_length=20, choices=PARTY_TYPE_CHOICES, default='SELLER', db_index=True)
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    street_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    mobile_number = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    
    website_url = models.URLField(max_length=500, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    user_ratings_total = models.IntegerField(default=0)
    
    enrichment_status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING'
    )

    notes = models.TextField(blank=True, null=True)

    # Scoping & Assignment
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='searched_vendors'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_vendors'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['created_by', 'party_type']),
            models.Index(fields=['assigned_to', 'party_type']),
            models.Index(fields=['category', 'city']),
        ]

    def __str__(self):
        return f"{self.store_name} ({self.get_party_type_display()} - {self.category})"
