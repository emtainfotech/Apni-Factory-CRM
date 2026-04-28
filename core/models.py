import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


from django.db import models
from authentication.models import User

# --- 1. CUSTOMER MODEL ---
class Customer(models.Model):
    LEAD_SOURCE_CHOICES = (
        ('website', 'Website'),
        ('whatsapp', 'WhatsApp'),
        ('call', 'Call'),
        ('manual', 'Manual Entry'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
    )

    STATUS_CHOICES = (
        ('lead', 'Lead'),
        ('prospect', 'Prospect'),
        ('customer', 'Customer'),
        ('inactive', 'Inactive'),
        ('lost', 'Lost'),
    )

    # Basic Details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, unique=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)

    # Business Details (Added for GST Sync)
    company_name = models.CharField(max_length=200, blank=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    is_gst_verified = models.BooleanField(default=False, help_text="True if verified via WhatsApp or Manually by Employee")
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, default="India")

    # CRM Fields
    lead_source = models.CharField(max_length=20, choices=LEAD_SOURCE_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='lead')
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_customers"
    )
    notes = models.TextField(blank=True)

    # Metadata
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_customers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} - {self.phone}"

# --- 2. WHATSAPP BOT STATE ---
class WhatsAppLead(models.Model):
    # Link to the Core Customer Record
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='whatsapp_state', null=True, blank=True)
    
    USER_TYPE_CHOICES = (
        ('seller', 'Seller'),
        ('buyer', 'Buyer'),
        ('enquiry', 'General Enquiry'),
        ('unknown', 'Unknown'),
    )
    
    GST_STATUS_CHOICES = (
        ('none', 'Not Checked'),
        ('pending', 'Pending Input'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
        ('no_gst', 'User has no GST'),
    )

    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    
    # State Management
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='unknown')
    gst_status = models.CharField(max_length=20, choices=GST_STATUS_CHOICES, default='none')
    
    # The "Cursor"
    conversation_stage = models.CharField(max_length=50, default='W-001')
    
    needs_human = models.BooleanField(default=False)
    last_message_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bot State: {self.phone_number}"

# --- 3. CHAT HISTORY ---
class WhatsAppChat(models.Model):
    DIRECTION_CHOICES = (
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='whatsapp_chats')
    message = models.TextField()
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.direction}: {self.message[:20]}"

# --- 4. PREFERENCES ---
class CustomerPreference(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE)
    preferred_language = models.CharField(max_length=50, default='English')
    preferred_contact_method = models.CharField(max_length=50, default='call')
    marketing_email_opt_in = models.BooleanField(default=True)
    marketing_sms_opt_in = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# ... (Keep Order, CallLog, etc. models here if you use them in the profile view)

class Order(models.Model):
    ORDER_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=50, blank=True)
    payment_status = models.CharField(max_length=20, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} ({self.quantity})"


class CallLog(models.Model):
    CALL_STATUS_CHOICES = (
        ('connected', 'Connected'),
        ('not_connected', 'Not Connected'),
        ('busy', 'Busy'),
        ('no_answer', 'No Answer'),
        ('follow_up', 'Follow Up Required'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='call_logs')
    employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    call_status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES)
    remark = models.TextField()
    follow_up_date = models.DateTimeField(blank=True, null=True)

    call_duration = models.PositiveIntegerField(help_text="Duration in seconds", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Call - {self.customer.phone}"



# class WhatsAppChat(models.Model):
#     MESSAGE_TYPE_CHOICES = (
#         ('sent', 'Sent'),
#         ('received', 'Received'),
#     )

#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='whatsapp_chats')
#     employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

#     message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
#     message = models.TextField()
#     media_url = models.URLField(blank=True, null=True)

#     whatsapp_message_id = models.CharField(max_length=255, blank=True, null=True)
#     timestamp = models.DateTimeField()

#     synced_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"WhatsApp - {self.customer.phone}"


class CustomerActivityLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='activities')
    employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    action = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.action


# # --- Preferences Model ---
# class CustomerPreference(models.Model):
#     customer = models.OneToOneField(Customer, on_delete=models.CASCADE)
#     preferred_language = models.CharField(max_length=50, default='English')
#     preferred_contact_method = models.CharField(max_length=50, default='call')
#     marketing_email_opt_in = models.BooleanField(default=True)
#     marketing_sms_opt_in = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)