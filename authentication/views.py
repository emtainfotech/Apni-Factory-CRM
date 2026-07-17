from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from core.models import ApprovedIPAddress, LoginApprovalRequest
from django.http import JsonResponse
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

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')

    def form_valid(self, form):
        user = form.get_user()
        
        # Admin or Superuser bypasses IP checks
        if user.is_superuser or getattr(user, 'role', '') == 'admin':
            login(self.request, user)
            return redirect(self.get_success_url())
            
        if getattr(user, 'role', '') == 'employee':
            ip_address = self.get_client_ip()
            
            # Check if IP is approved
            is_approved = ApprovedIPAddress.objects.filter(user=user, ip_address=ip_address).exists()
            
            if not is_approved:
                # Need approval
                lat = self.request.POST.get('latitude')
                lng = self.request.POST.get('longitude')
                
                # Check for existing pending request for this IP
                req, created = LoginApprovalRequest.objects.get_or_create(
                    user=user, 
                    ip_address=ip_address,
                    status='pending',
                    defaults={
                        'latitude': lat if lat else None,
                        'longitude': lng if lng else None
                    }
                )
                
                # If not created, explicitly update location if provided
                if not created and lat and lng:
                    req.latitude = lat
                    req.longitude = lng
                    req.save()
                
                self.request.session['pending_login_user_id'] = user.id
                self.request.session['pending_login_request_id'] = req.id
                
                return redirect('waiting_room')
                
        # For non-employees or approved employees
        login(self.request, user)
        return redirect(self.get_success_url())

    def get_success_url(self):
        user = self.request.user
        
        # Check Superuser OR Admin Role
        if user.is_superuser or getattr(user, 'role', '') == 'admin':
            return reverse_lazy('dashboard_admin')
            
        elif getattr(user, 'role', '') == 'manager':
            return reverse_lazy('dashboard_manager')
            
        elif getattr(user, 'role', '') == 'field_agent':
            return reverse_lazy('dashboard_agent')
            
        elif getattr(user, 'role', '') == 'employee':
            return reverse_lazy('employee_portal:dashboard')
            
        else:
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

def waiting_room(request):
    req_id = request.session.get('pending_login_request_id')
    if not req_id:
        return redirect('login')
    
    login_request = get_object_or_404(LoginApprovalRequest, id=req_id)
    return render(request, 'authentication/waiting_room.html', {'login_request': login_request})

def check_login_status(request):
    req_id = request.session.get('pending_login_request_id')
    user_id = request.session.get('pending_login_user_id')
    
    if not req_id or not user_id:
        return JsonResponse({'status': 'error', 'message': 'No pending request found.'})
        
    login_request = get_object_or_404(LoginApprovalRequest, id=req_id)
    
    if login_request.status == 'approved':
        user = get_object_or_404(User, id=user_id)
        login(request, user)
        # Clear session vars
        del request.session['pending_login_request_id']
        del request.session['pending_login_user_id']
        return JsonResponse({'status': 'approved', 'redirect_url': reverse_lazy('employee_portal:dashboard')})
        
    elif login_request.status == 'rejected':
        del request.session['pending_login_request_id']
        del request.session['pending_login_user_id']
        return JsonResponse({'status': 'rejected', 'redirect_url': reverse_lazy('login')})
        
    return JsonResponse({'status': 'pending'})