from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer, CustomerFolder

@receiver(post_save, sender=Customer)
def create_default_whatsapp_folder(sender, instance, created, **kwargs):
    if created:
        CustomerFolder.objects.get_or_create(
            customer=instance,
            name='whatsapp',
            parent=None,
            defaults={'is_system_folder': True}
        )
