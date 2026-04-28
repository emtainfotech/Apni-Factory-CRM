from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # Roles
    ADMIN = 'admin'
    MANAGER = 'manager'
    EMPLOYEE = 'employee'
    FIELD_AGENT = 'field_agent'

    ROLE_CHOICES = (
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (EMPLOYEE, 'Employee'),
        (FIELD_AGENT, 'Field Sales Agent'),
    )

    # Invitation Status
    INVITATION_PENDING = 'pending'
    INVITATION_ACCEPTED = 'accepted'
    INVITATION_REJECTED = 'rejected'
    
    INVITATION_STATUS_CHOICES = (
        (INVITATION_PENDING, 'Pending'),
        (INVITATION_ACCEPTED, 'Accepted'),
        (INVITATION_REJECTED, 'Rejected'),
    )

    # --- MAKE SURE THESE FIELDS EXIST ---
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=EMPLOYEE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)  # <--- THIS WAS MISSING
    invitation_status = models.CharField(max_length=20, choices=INVITATION_STATUS_CHOICES, default=INVITATION_ACCEPTED)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True) 
    is_read = models.BooleanField(default=False)
    
    # This will now use Indian Time based on settings.py
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message}"