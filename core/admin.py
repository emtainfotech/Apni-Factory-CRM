from django.contrib import admin

from core.models import Customer, WhatsAppMessageStatus

# Register your models here.

admin.site.register(Customer)
admin.site.register(WhatsAppMessageStatus)