from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Notification

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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'recipient__email', 'message')
    ordering = ('-created_at',)