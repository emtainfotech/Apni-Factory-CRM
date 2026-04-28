from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib import messages
from django.http import HttpResponse

from .models import User, Notification
from .forms import UserCreationForm # You'll need to create a standard ModelForm for User
from .tokens import account_activation_token
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

class CustomLoginView(LoginView):
    template_name = 'authentication/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        
        # Check Superuser OR Admin Role
        if user.is_superuser or getattr(user, 'role', '') == 'admin':
            return reverse_lazy('dashboard_admin')
            
        elif getattr(user, 'role', '') == 'manager':
            return reverse_lazy('dashboard_manager')
            
        elif getattr(user, 'role', '') == 'field_agent':
            return reverse_lazy('dashboard_agent')
            
        else:
            # Default fallback for employees or undefined roles
            return reverse_lazy('dashboard_employee')
        
# IMPORT THE SIGNAL
from .signals import invitation_accepted_signal 

def activate_account(request, uidb64, token, action):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        
        if action == 'accept':
            user.is_active = True
            user.invitation_status = User.INVITATION_ACCEPTED
            user.save()
            
            # --- SEND SIGNAL HERE ---
            # This triggers the notification creation for Admins
            invitation_accepted_signal.send(sender=User, user=user)
            # ------------------------

            # Send Credentials Email (Existing Logic)
            current_site = get_current_site(request)
            mail_subject = 'Account Active: Login Credentials'
            message = render_to_string('authentication/email_credentials.html', {
                'user': user,
                'domain': current_site.domain,
            })
            email = EmailMessage(mail_subject, message, to=[user.email])
            email.content_subtype = "html"
            email.send()

            return HttpResponse("Thank you! Your account is now active.")
        
        elif action == 'reject':
            user.invitation_status = User.INVITATION_REJECTED
            user.save()
            return HttpResponse("Invitation Rejected.")
            
    else:
        return HttpResponse('Activation link is invalid or has expired.')