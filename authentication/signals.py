from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.urls import reverse
from .models import User, Notification

# 1. Define a Custom Signal
# We use a custom signal because we only want to notify when the 
# specific action of "Accepting Invite" happens in the view.
invitation_accepted_signal = Signal()

# 2. Define the Receiver (The logic that runs when signal is sent)
@receiver(invitation_accepted_signal)
def handle_invitation_accepted(sender, user, **kwargs):
    """
    Generates a notification for all Admins/Superusers when a new user accepts an invite.
    """
    # Get all Superusers or Admins who should receive the alert
    # You can adjust the filter to match your specific 'Admin' role definition
    admins = User.objects.filter(is_superuser=True) | User.objects.filter(role='admin')
    
    # Generate the URL to the new user's profile
    # Ensure 'user_detail' is the correct name of your url pattern in core/urls.py
    try:
        target_url = reverse('user_detail', args=[user.id])
    except:
        target_url = '#' # Fallback if URL pattern not found

    # Create Notification for each Admin
    notifications_to_create = []
    for admin in admins:
        # Don't notify the user about themselves if they happen to be an admin
        if admin.id != user.id: 
            notifications_to_create.append(
                Notification(
                    recipient=admin,
                    message=f"{user.username} ({user.get_role_display()}) has accepted the invitation.",
                    url=target_url
                )
            )
    
    # Bulk create is more efficient
    Notification.objects.bulk_create(notifications_to_create)