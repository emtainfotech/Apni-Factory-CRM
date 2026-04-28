from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    # The names inside these quotes MUST match the variables in models.py
    list_display = ('username', 'email', 'role', 'region', 'is_staff') 
    
    fieldsets = UserAdmin.fieldsets + (
        ('CRM Roles', {'fields': ('role', 'region', 'phone_number', 'invitation_status')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('CRM Roles', {'fields': ('role', 'region', 'phone_number', 'invitation_status')}),
    )

admin.site.register(User, CustomUserAdmin)