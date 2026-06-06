import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


from django.db import models
from authentication.models import User

from django.utils import timezone

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

class VerifiedGST(models.Model):
    gst_number = models.CharField(max_length=20, unique=True)
    verified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.gst_number


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
    
    # Mapping to Hostinger Data
    hostinger_order_id = models.IntegerField(null=True, blank=True, db_index=True)
    order_number = models.CharField(max_length=50, unique=True) # Maps to Hostinger orderno
    
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')

    # Financials (Synced from Hostinger)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    payment_mode = models.CharField(max_length=50, blank=True)
    payment_status = models.CharField(max_length=20, default='pending')

    # Logistics / Tracking (From Hostinger OrderTracks)
    transporter_name = models.CharField(max_length=255, blank=True, null=True)
    lr_number = models.CharField(max_length=100, blank=True, null=True)
    tracking_msg = models.TextField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)

    # CRM Fields
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders')
    crm_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    # Sync from Hostinger Orderdetail
    hostinger_product_id = models.IntegerField(null=True, blank=True)
    product_name = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    attribute = models.TextField(blank=True, null=True)
    
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} ({self.quantity})"


class OrderStatusHistory(models.Model):
    """Tracks status changes for CRM visibility (from Hostinger OrderStatus)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


# --- 5. APP DATA CRM SYNC ---
class CompanyAssignment(models.Model):
    """Allows assigning Application Companies to CRM Team Members"""
    company_id = models.IntegerField(unique=True, help_text="ID from App Database (hostinger_data.Companies)")
    company_name = models.CharField(max_length=255)
    
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_companies')
    crm_notes = models.TextField(blank=True)
    
    last_sync = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name


class TicketInternalNote(models.Model):
    """Allows CRM team to add internal notes to Support Tickets"""
    ticket_id = models.IntegerField(help_text="ID from App Database (hostinger_data.Tickets)")
    note = models.TextField()
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note on Ticket #{self.ticket_id} by {self.created_by}"


# --- 6. ATTENDANCE SYSTEM ---
class Attendance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(auto_now_add=True)
    punch_in = models.DateTimeField(null=True, blank=True)
    punch_out = models.DateTimeField(null=True, blank=True)
    
    # Track working status
    is_punched_in = models.BooleanField(default=False)
    on_break = models.BooleanField(default=False)
    
    # Audit trail & Accuracy
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    is_late = models.BooleanField(default=False)
    
    # Totals
    total_working_hours = models.DurationField(null=True, blank=True)
    total_break_duration = models.DurationField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Attendances"
        ordering = ['-date', '-punch_in']

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class Break(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='breaks')
    break_start = models.DateTimeField(auto_now_add=True)
    break_end = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"Break for {self.attendance.user.username} on {self.attendance.date}"


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

# --- 5. INVOICE SYSTEM ---
class Invoice(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )

    SUPPLY_TYPE_CHOICES = (
        ('B2B', 'B2B'),
        ('B2C', 'B2C'),
    )

    invoice_no = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(auto_now_add=True)
    
    # Relationships
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    hostinger_user_id = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_invoices')

    # Client details at time of invoice (for history)
    client_name = models.CharField(max_length=255)
    client_gstin = models.CharField(max_length=15, blank=True, null=True)
    client_state_code = models.CharField(max_length=2)
    place_of_supply = models.CharField(max_length=100)
    
    supply_type = models.CharField(max_length=10, choices=SUPPLY_TYPE_CHOICES, default='B2B')
    reverse_charge = models.BooleanField(default=False)
    
    # Financials
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2)
    gst_total = models.DecimalField(max_digits=12, decimal_places=2)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    payment_mode = models.CharField(max_length=50, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    is_finalized = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.invoice_no

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.TextField()
    sac_code = models.CharField(max_length=10, default="998361")
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.description[:30]}"

# --- 6. CRM TRANSACTIONS ---
class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('credit', 'Credit (Income)'),
        ('debit', 'Debit (Expense)'),
    )
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='transactions')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    payment_method = models.CharField(max_length=50, help_text="UPI, Cheque, Bank Transfer, etc.")
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    
    remark = models.TextField(blank=True)
    transaction_date = models.DateTimeField(default=timezone.now)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.transaction_type.upper()} - {self.amount} ({self.customer.first_name})"


# # --- Preferences Model ---
# class CustomerPreference(models.Model):
#     customer = models.OneToOneField(Customer, on_delete=models.CASCADE)
#     preferred_language = models.CharField(max_length=50, default='English')
#     preferred_contact_method = models.CharField(max_length=50, default='call')
#     marketing_email_opt_in = models.BooleanField(default=True)
#     marketing_sms_opt_in = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = (
        ('casual', 'Casual Leave'),
        ('sick', 'Sick Leave'),
        ('earned', 'Earned Leave'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='casual')
    
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.username} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"


class EmployeeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    
    # Photo & Personal Details
    photo = models.ImageField(upload_to='photos/', blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    marital_status = models.CharField(max_length=20, blank=True, null=True)
    blood_group = models.CharField(max_length=10, blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    current_address = models.TextField(blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Education Details
    qualification = models.CharField(max_length=100, blank=True, null=True)
    institution = models.CharField(max_length=100, blank=True, null=True)
    passing_year = models.CharField(max_length=10, blank=True, null=True)
    
    # Experience Details
    previous_company = models.CharField(max_length=100, blank=True, null=True)
    previous_designation = models.CharField(max_length=100, blank=True, null=True)
    experience_duration = models.CharField(max_length=50, blank=True, null=True)
    
    # Documents
    aadhar_number = models.CharField(max_length=20, blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    aadhar_file = models.FileField(upload_to='documents/', blank=True, null=True)
    pan_file = models.FileField(upload_to='documents/', blank=True, null=True)
    resume = models.FileField(upload_to='documents/', blank=True, null=True)
    other_document = models.FileField(upload_to='documents/', blank=True, null=True)
    
    # Family Members (Stored as list of dicts e.g. [{'name': 'John', 'relation': 'Father', 'age': 55}])
    family_members_json = models.JSONField(default=list, blank=True)
    
    # Salary & Payslip
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    previous_month_salary_slip = models.FileField(upload_to='salary_slips/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"