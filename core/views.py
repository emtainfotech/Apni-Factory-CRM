import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone

# Import Models & Forms
from authentication.models import User, Notification
from authentication.tokens import account_activation_token
from .forms import UserInviteForm, BannerForm, SliderForm
from .models import Customer, WhatsAppLead

# Import Hostinger Data Models
from hostinger_data.models import (
    Users as HostingerUser, Companies, Brands, Products, Orders,
    Wallet, Credits, Faqs, Pages, Tickets, ShadeCards,
    Advertisements, BankDetails, Admin as HostingerAdmin,
    Orderdetail, OrderTracks, OrderStatus, Categories, Sliders,
    MainCategories, SubCategories, Brands as AppBrands, Tickets as AppTickets,
    Companies as AppCompanies, Wallet as AppWallet, Faqs as AppFaqs
)

# Import Invoice Utils & Models
from .models import Invoice, InvoiceItem, Order, OrderItem, Transaction, Attendance, Break, CallLog, CustomerActivityLog, LeaveRequest, EmployeeProfile
from .invoice_utils import calculate_gst_values, get_next_invoice_number

from datetime import datetime, timedelta

# ==========================================
#              HELPER FUNCTIONS
# ==========================================

def attendance_required(view_func):
    """
    Decorator for views that checks if the user has punched in for today.
    Admins are exempted.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser or request.user.role == 'admin':
            return view_func(request, *args, **kwargs)
        
        today = timezone.now().date()
        attendance = Attendance.objects.filter(user=request.user, date=today, is_punched_in=True).first()
        
        if not attendance:
            messages.warning(request, "Please Punch-In to access your dashboard.")
            return redirect('employee_dashboard')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def is_admin(user):
    return user.is_superuser or user.role == 'admin'

def is_manager(user):
    return user.role == 'manager'

def is_field_agent(user):
    return user.role == 'field_agent'

def is_employee(user):
    return user.role == 'employee'


def health_check(request):
    return HttpResponse("OK", status=200)

# ==========================================
#              DASHBOARDS
# ==========================================

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    from hostinger_data.models import Customers as HostingerCustomer
    
    # Local CRM Counts
    total_customers = Customer.objects.count()
    total_invoices = Invoice.objects.count()
    total_employees = User.objects.exclude(Q(role='admin') | Q(is_superuser=True)).count()
    
    # Remote E-commerce Counts & Sales (synced dynamically from hostinger_db)
    total_hostinger_users = HostingerUser.objects.count()
    total_hostinger_customers = HostingerCustomer.objects.count()
    total_orders = Orders.objects.count()
    total_products = Products.objects.count()
    total_tickets = Tickets.objects.count()
    total_companies = Companies.objects.count()
    total_brands = Brands.objects.count()
    
    # Calculate Total E-commerce Business Sales Volume
    total_sales = Orders.objects.aggregate(total=Sum('grandtotal'))['total'] or 0
    recent_orders = Orders.objects.all().order_by('-created_at')[:10]
    
    # WhatsApp Bot capture metrics
    whatsapp_needs_human = WhatsAppLead.objects.filter(needs_human=True).select_related('customer')
    total_whatsapp_leads = WhatsAppLead.objects.count()
    
    # HRMS Overview
    pending_leaves_count = LeaveRequest.objects.filter(status='pending').count()
    
    # Team Performance & Attendance reports
    employees = User.objects.exclude(Q(role='admin') | Q(is_superuser=True)).order_by('username')
    today = timezone.now().date()
    
    for emp in employees:
        # Today's Punch status
        emp.today_attendance = Attendance.objects.filter(user=emp, date=today).first()
        
        # Performance KPIs
        emp.assigned_customers_count = Customer.objects.filter(assigned_to=emp).count()
        emp.today_calls_count = CallLog.objects.filter(employee=emp, created_at__date=today).count()
        
        # Calculate Employee Generated Revenue in INR
        assigned_custs = Customer.objects.filter(assigned_to=emp)
        phones = [c.phone for c in assigned_custs if c.phone]
        whatsapp_numbers = [c.whatsapp_number for c in assigned_custs if c.whatsapp_number]
        gst_numbers = [c.gst_number for c in assigned_custs if c.gst_number]
        
        remote_cust_ids = []
        if phones or whatsapp_numbers or gst_numbers:
            q_filter = Q()
            if phones:
                q_filter |= Q(mobile__in=phones)
            if whatsapp_numbers:
                q_filter |= Q(whatsappno__in=whatsapp_numbers)
            if gst_numbers:
                q_filter |= Q(gstorpan__in=gst_numbers)
                
            remote_cust_ids = list(
                HostingerCustomer.objects.using('hostinger_db')
                .filter(q_filter)
                .values_list('id', flat=True)
            )
            
        if remote_cust_ids:
            emp.revenue_generated = Orders.objects.using('hostinger_db').filter(customer_id__in=remote_cust_ids).aggregate(total=Sum('grandtotal'))['total'] or 0
        else:
            emp.revenue_generated = 0
            
    context = {
        'total_customers': total_customers,
        'total_invoices': total_invoices,
        'total_employees': total_employees,
        'total_hostinger_users': total_hostinger_users,
        'total_hostinger_customers': total_hostinger_customers,
        'total_orders': total_orders,
        'total_products': total_products,
        'total_tickets': total_tickets,
        'total_companies': total_companies,
        'total_brands': total_brands,
        'total_sales': total_sales,
        'recent_orders': recent_orders,
        'recent_users': User.objects.order_by('-date_joined')[:5],
        'whatsapp_needs_human': whatsapp_needs_human,
        'total_whatsapp_leads': total_whatsapp_leads,
        'pending_leaves_count': pending_leaves_count,
        'employees': employees,
    }
    return render(request, 'core/dashboard_admin.html', context)

@login_required
@user_passes_test(is_manager)
def manager_dashboard(request):
    return render(request, 'core/dashboard_manager.html')

# Legacy employee views removed in favor of namespaced employee_portal app.


@login_required
@attendance_required
def log_call(request, customer_id):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=customer_id)
        call_status = request.POST.get('call_status')
        remark = request.POST.get('remark')
        follow_up = request.POST.get('follow_up_date')
        
        log = CallLog.objects.create(
            customer=customer,
            employee=request.user,
            call_status=call_status,
            remark=remark,
            follow_up_date=follow_up if follow_up else None
        )
        
        # Log activity
        CustomerActivityLog.objects.create(
            customer=customer,
            employee=request.user,
            action="Call Logged",
            description=f"Status: {log.get_call_status_display()}. Remark: {remark}"
        )
        
        messages.success(request, "Call logged successfully.")
    return redirect('customer_detail', customer_id=customer_id)


@login_required
@attendance_required
def convert_lead(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if customer.status == 'lead':
        customer.status = 'customer'
        customer.save()
        
        CustomerActivityLog.objects.create(
            customer=customer,
            employee=request.user,
            action="Lead Converted",
            description="Status changed from Lead to Customer."
        )
        messages.success(request, f"{customer.first_name} has been converted to a Customer.")
    return redirect('customer_detail', customer_id=customer_id)


@login_required
@user_passes_test(is_field_agent)
def agent_dashboard(request):
    return render(request, 'core/dashboard_agent.html')


# ==========================================
#           USER MANAGEMENT
# ==========================================

@login_required
@user_passes_test(is_admin)
def create_crm_user(request):
    if request.method == 'POST':
        form = UserInviteForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            
            # 1. Set Password (Hashed immediately)
            password = form.cleaned_data['password']
            user.set_password(password)
            
            # 2. Set as Pending & Inactive
            user.is_active = False
            user.invitation_status = User.INVITATION_PENDING
            user.save()

            # 3. Send INVITATION Email
            current_site = get_current_site(request)
            mail_subject = 'Invitation: Join ApniFactory CRM'
            message = render_to_string('authentication/email_invitation.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            
            email = EmailMessage(mail_subject, message, to=[user.email])
            email.content_subtype = "html"
            email.send()

            messages.success(request, f'Invitation sent to {user.email}. User is currently Inactive.')
            return redirect('user_list')
        else:
            messages.error(request, "Error creating user. Check inputs.")
    
    return redirect('user_list')


@login_required
@user_passes_test(is_admin)
def user_list(request):
    users_qs = User.objects.all().order_by('-date_joined')
    
    # 1. Search Logic
    query = request.GET.get('q', '')
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) | 
            Q(email__icontains=query) |
            Q(role__icontains=query)
        )

    # 2. Filters
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')

    if role_filter:
        users_qs = users_qs.filter(role=role_filter)
    if status_filter:
        is_active = status_filter == 'active'
        users_qs = users_qs.filter(is_active=is_active)

    # 3. Pagination
    paginator = Paginator(users_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'selected_role': role_filter,
        'selected_status': status_filter,
        'roles': User.ROLE_CHOICES,
    }

    # 4. HTMX Navigation Fix
    is_htmx = request.headers.get('HX-Request') == 'true'
    target_id = request.headers.get('HX-Target')

    # Only return partial if specifically updating the table wrapper
    if is_htmx and target_id in ['user-table-wrapper', 'user-table-body']:
        return render(request, 'core/partials/user_table.html', context)

    # Otherwise return full page
    form = UserInviteForm()
    context['form'] = form
    return render(request, 'core/user_list.html', context)


@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.is_superuser:
        messages.error(request, "Cannot delete a Superuser.")
    else:
        user.delete()
        messages.success(request, "User deleted successfully.")
    return redirect('user_list')


@login_required
def user_profile(request):
    """Profile details page where employees can view and edit their details, documents, and family members."""
    profile, created = EmployeeProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Personal Details
        profile.dob = request.POST.get('dob') or None
        profile.gender = request.POST.get('gender')
        profile.marital_status = request.POST.get('marital_status')
        profile.blood_group = request.POST.get('blood_group')
        profile.current_address = request.POST.get('current_address')
        profile.permanent_address = request.POST.get('permanent_address')
        profile.emergency_contact_name = request.POST.get('emergency_contact_name')
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone')
        
        # Education Details
        profile.qualification = request.POST.get('qualification')
        profile.institution = request.POST.get('institution')
        profile.passing_year = request.POST.get('passing_year')
        
        # Experience Details
        profile.previous_company = request.POST.get('previous_company')
        profile.previous_designation = request.POST.get('previous_designation')
        profile.experience_duration = request.POST.get('experience_duration')
        
        # Documents text fields
        profile.aadhar_number = request.POST.get('aadhar_number')
        profile.pan_number = request.POST.get('pan_number')
        
        # File Uploads
        if 'photo' in request.FILES:
            profile.photo = request.FILES['photo']
        if 'aadhar_file' in request.FILES:
            profile.aadhar_file = request.FILES['aadhar_file']
        if 'pan_file' in request.FILES:
            profile.pan_file = request.FILES['pan_file']
        if 'resume' in request.FILES:
            profile.resume = request.FILES['resume']
        if 'previous_month_salary_slip' in request.FILES:
            profile.previous_month_salary_slip = request.FILES['previous_month_salary_slip']
            
        # Family members JSON parsing
        family_members_raw = request.POST.get('family_members_json_raw', '[]')
        try:
            profile.family_members_json = json.loads(family_members_raw)
        except Exception:
            pass
            
        profile.save()
        messages.success(request, "Your profile details have been updated successfully.")
        return redirect('user_profile')
        
    # Get attendance & leave records for dashboard components
    attendances = Attendance.objects.filter(user=request.user).order_by('-date')[:15]
    leaves = LeaveRequest.objects.filter(employee=request.user).order_by('-created_at')[:15]
    
    # Calculate statistics
    total_leaves = LeaveRequest.objects.filter(employee=request.user, status='approved').count()
    pending_leaves = LeaveRequest.objects.filter(employee=request.user, status='pending').count()
    
    context = {
        'profile': profile,
        'attendances': attendances,
        'leaves': leaves,
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
    }
    return render(request, 'core/employee_profile.html', context)


@login_required
def user_detail(request, user_id):
    """Admin view to show full employee details, files, attendance, and modify salary/details."""
    user_profile = get_object_or_404(User, pk=user_id)
    profile, created = EmployeeProfile.objects.get_or_create(user=user_profile)
    
    # Admin can update user's salary or other details
    if request.method == 'POST' and (request.user.role == 'admin' or request.user.is_superuser):
        action = request.POST.get('action')
        if action == 'update_salary':
            profile.salary = request.POST.get('salary', 0.00)
            profile.save()
            messages.success(request, f"Salary updated for {user_profile.username}.")
            return redirect('user_detail', user_id=user_id)
            
    attendances = Attendance.objects.filter(user=user_profile).order_by('-date')
    leaves = LeaveRequest.objects.filter(employee=user_profile).order_by('-created_at')
    
    context = {
        'user_profile': user_profile,
        'profile': profile,
        'attendances': attendances,
        'leaves': leaves,
    }
    return render(request, 'core/user_detail.html', context)



@login_required
@attendance_required
def customer_detail(request, customer_id):
    """
    360-degree view of a customer including orders, invoices, 
    whatsapp chats, and transactions.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    from .forms import CustomerEditForm
    
    if request.method == 'POST' and request.POST.get('action') == 'edit_customer':
        edit_form = CustomerEditForm(request.POST, instance=customer)
        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, "Buyer profile updated successfully.")
            return redirect('customer_detail', customer_id=customer.id)
        else:
            messages.error(request, "Failed to update buyer profile. Please check the errors.")
    else:
        edit_form = CustomerEditForm(instance=customer)
    
    # Fetch related data with prefetching for performance
    orders = customer.orders.all().prefetch_related('status_history').order_by('-created_at')
    invoices = customer.invoices.all().order_by('-created_at')
    whatsapp_chats = customer.whatsapp_chats.all().order_by('-timestamp')
    transactions = customer.transactions.all().order_by('-transaction_date')
    activities = customer.activities.all().order_by('-created_at')
    call_logs = customer.call_logs.all().order_by('-created_at')
    
    context = {
        'customer': customer,
        'orders': orders,
        'invoices': invoices,
        'whatsapp_chats': whatsapp_chats,
        'transactions': transactions,
        'activities': activities,
        'call_logs': call_logs,
        'total_spent': sum(o.total_amount for o in orders if o.status != 'cancelled'),
        'edit_form': edit_form,
    }
    
    return render(request, 'core/customer_detail.html', context)

@login_required
def order_list(request):
    """Global list of all orders from Hostinger Database with filters and pagination."""
    from django.db.models import Subquery, OuterRef
    
    # Subquery to get the latest status for each order to filter and display efficiently
    latest_status_subquery = OrderStatus.objects.filter(
        order_id=OuterRef('id')
    ).order_by('-created_at', '-id').values('status')[:1]

    orders_qs = Orders.objects.all().annotate(
        latest_status=Subquery(latest_status_subquery)
    ).order_by('-created_at')
    
    # 1. Search logic
    query = request.GET.get('q', '')
    if query:
        orders_qs = orders_qs.filter(
            Q(orderno__icontains=query) | 
            Q(address__icontains=query)
        )

    # 2. Address search logic
    address_query = request.GET.get('address_q', '')
    if address_query:
        orders_qs = orders_qs.filter(address__icontains=address_query)
        
    # 3. Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders_qs = orders_qs.filter(latest_status__icontains=status_filter)
        
    # 4. Pagination
    paginator = Paginator(orders_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Inject latest status for each order in the page
    for order in page_obj:
        order.current_status = order.latest_status if order.latest_status else "Pending"
        
    context = {
        'page_obj': page_obj,
        'query': query,
        'address_query': address_query,
        'selected_status': status_filter,
    }
    
    # 5. HTMX Integration
    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'order-table-wrapper':
        return render(request, 'core/partials/order_table.html', context)
    
    return render(request, 'core/order_list.html', context)

@login_required
def product_list(request):
    """View to list all products from Hostinger with filters."""
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    brand_id = request.GET.get('brand', '')
    
    products_qs = Products.objects.all().order_by('-created_at')
    
    if query:
        products_qs = products_qs.filter(
            Q(name__icontains=query) | 
            Q(title__icontains=query) | 
            Q(hsncode__icontains=query)
        )
        
    if category_id:
        products_qs = products_qs.filter(category_id=category_id)
        
    if brand_id:
        # Filter by brand name instead of ID to handle duplicates correctly
        products_qs = products_qs.filter(brand_id__in=Brands.objects.filter(name=brand_id).values_list('id', flat=True))
        
    # Pagination
    paginator = Paginator(products_qs, 20)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)
    
    # Fetch metadata for filters
    categories = Categories.objects.all().order_by('name')
    
    # Fetch distinct brand names to avoid duplicates in dropdown
    brands_names = Brands.objects.values_list('name', flat=True).distinct().order_by('name')
    
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    # Enhance product objects with extra data
    for p in products:
        p.image_url = f"{IMAGE_PREFIX}{p.image}" if p.image else None
        p.category_name = Categories.objects.filter(id=p.category_id).values_list('name', flat=True).first()
        p.brand_name = Brands.objects.filter(id=p.brand_id).values_list('name', flat=True).first()
        # Fetch vendor name
        vendor = HostingerUser.objects.filter(id=p.user_id).values_list('name', flat=True).first()
        p.vendor_name = vendor if vendor else "Unknown"

    context = {
        'products': products,
        'categories': categories,
        'brands': brands_names,
        'query': query,
        'selected_category': category_id,
        'selected_brand': brand_id,
    }
    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'product-table-wrapper':
        return render(request, 'core/partials/product_table.html', context)
        
    return render(request, 'core/product_list.html', context)


@login_required
def order_detail(request, order_id):
    """Detailed view of a specific order from Hostinger."""
    order = get_object_or_404(Orders, pk=order_id)
    
    # Get related data from Hostinger
    order_details = Orderdetail.objects.filter(order_id=order_id)
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"

    # Parse attributes and fetch product details for each order item
    for item in order_details:
        # Parse attributes
        if item.attribute:
            try:
                item.parsed_attributes = json.loads(item.attribute)
            except (json.JSONDecodeError, TypeError):
                item.parsed_attributes = None
        else:
            item.parsed_attributes = None
            
        # Fetch detailed product info
        try:
            product = Products.objects.filter(id=item.product_id).first()
            if product:
                item.product_obj = product
                item.product_image = f"{IMAGE_PREFIX}{product.image}" if product.image else None
                item.brand_obj = Brands.objects.filter(id=product.brand_id).first()
                item.category_obj = Categories.objects.filter(id=product.category_id).first()
                
                # Fetch Vendor/Brand Owner info
                vendor_user = HostingerUser.objects.filter(id=product.user_id).first()
                vendor_company = Companies.objects.filter(user_id=product.user_id).first()
                item.vendor_info = {
                    'name': vendor_user.name if vendor_user else "Unknown Vendor",
                    'company': vendor_company.name if vendor_company else None,
                    'mobile': vendor_company.mobile if vendor_company else None,
                }
        except Exception:
            item.product_obj = None
            item.product_image = None
            item.brand_obj = None
            item.category_obj = None

    order_tracks = OrderTracks.objects.filter(order_id=order_id).order_by('-created_at')
    order_statuses = OrderStatus.objects.filter(order_id=order_id).order_by('-created_at')
    
    # Get customer info from Application DB
    h_user = get_object_or_404(HostingerUser, pk=order.user_id)
    h_company = AppCompanies.objects.filter(user_id=order.user_id).first()
    
    # Get latest status for banner
    latest_status = order_statuses.first() if order_statuses.exists() else None
    latest_track = order_tracks.first() if order_tracks.exists() else None
    
    # Calculate totals if not present
    total_qty = 0
    for item in order_details:
        if item.parsed_attributes:
            for attr in item.parsed_attributes:
                total_qty += int(attr.get('qty', 0))
    
    # Parse address JSON
    address_data = {}
    if order.address:
        try:
            address_data = json.loads(order.address)
        except (json.JSONDecodeError, TypeError):
            address_data = None
    
    # Parse tax details JSON
    tax_details = []
    if order.taxdetail:
        try:
            tax_details = json.loads(order.taxdetail)
        except (json.JSONDecodeError, TypeError):
            tax_details = None

    # Financials
    items_count = order_details.count()
    
    context = {
        'order': order,
        'order_details': order_details,
        'order_tracks': order_tracks,
        'order_statuses': order_statuses,
        'latest_status': latest_status,
        'latest_track': latest_track,
        'h_user': h_user,
        'h_company': h_company,
        'address_data': address_data,
        'tax_details': tax_details,
        'items_count': items_count,
        'total_qty': total_qty,
        'total_net': order.netamount,
        'total_tax': order.taxamount,
        'grand_total': order.grandtotal,
    }
    
    return render(request, 'core/order_detail.html', context)


# ==========================================
#         NOTIFICATION SYSTEM
# ==========================================

@login_required
def get_notifications(request):
    """
    Fetches ONLY UNREAD notifications with N+1 Optimization.
    """
    user = request.user
    
    # Base query with optimization
    if user.is_superuser or user.role == 'admin':
        qs = Notification.objects.select_related('recipient').filter(is_read=False).order_by('-created_at')
    else:
        qs = Notification.objects.select_related('recipient').filter(recipient=user, is_read=False).order_by('-created_at')

    # Pagination (10 per request)
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {'notifications': page_obj}

    return render(request, 'core/partials/notification_list.html', context)


@login_required
def mark_notifications_read(request):
    """Marks all visible notifications as read and triggers a list refresh."""
    user = request.user
    if request.method == "POST":
        if user.is_superuser or user.role == 'admin':
            Notification.objects.filter(is_read=False).update(is_read=True)
        else:
            Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
            
        # 1. Return empty string to hide the Red Dot
        response = HttpResponse('<span class="d-none"></span>')
        
        # 2. HTMX TRIGGER: Tell the frontend to refresh the notification list!
        response['HX-Trigger'] = 'refreshNotifications' 
        return response
        
    return HttpResponse(status=400)


@login_required
def notification_history(request):
    """
    Full page view for all notifications with Pagination.
    """
    user = request.user
    
    # Fetch Data (Optimized)
    if user.is_superuser or user.role == 'admin':
        qs = Notification.objects.select_related('recipient').all().order_by('-created_at')
    else:
        qs = Notification.objects.select_related('recipient').filter(recipient=user).order_by('-created_at')
        
    # Pagination
    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/notification_history.html', {'notifications': page_obj})


# ==========================================
#         CUSTOMER MANAGEMENT
# ==========================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from .models import Customer
from .forms import CustomerModalForm
from authentication.models import User

@login_required
@attendance_required
def customer_list(request):
    # Initialize the form (default to empty)
    modal_form = CustomerModalForm()

    # --- HANDLE MODAL FORM SUBMISSION (ADD CUSTOMER) ---
    if request.method == 'POST' and 'add_customer' in request.POST:
        # Bind data to the form
        modal_form = CustomerModalForm(request.POST)
        
        if modal_form.is_valid():
            customer = modal_form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, f"Customer {customer.first_name} added successfully!")
            # Clear the form after success
            modal_form = CustomerModalForm()
            return redirect('customer_list')
        else:
            # DO NOT REDIRECT HERE. 
            # We let it fall through so the template renders WITH the errors.
            messages.error(request, "Please correct the errors below.")
            # Debugging: Print errors to terminal so you can see them immediately
            print(modal_form.errors) 
    
    # --- HANDLE BULK ASSIGNMENT ---
    if request.method == 'POST' and 'bulk_assign' in request.POST:
        customer_ids = request.POST.getlist('selected_customers')
        assignee_id = request.POST.get('assign_to_user')
        
        if customer_ids and assignee_id:
            try:
                user_to_assign = User.objects.get(id=assignee_id)
                Customer.objects.filter(id__in=customer_ids).update(assigned_to=user_to_assign)
                messages.success(request, f"Assigned customers to {user_to_assign.username}.")
            except User.DoesNotExist:
                messages.error(request, "User not found.")
        return redirect('customer_list')

    # --- STANDARD LIST LOGIC (Search/Pagination) ---
    qs = Customer.objects.select_related('assigned_to').all().order_by('-created_at')
    
    # ... (Search logic remains same) ...
    query = request.GET.get('q', '')
    if query:
        qs = qs.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )

    # 2. Filters
    status_filter = request.GET.get('status', '')
    source_filter = request.GET.get('lead_source', '')
    assignee_filter = request.GET.get('assigned_to', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if source_filter:
        qs = qs.filter(lead_source=source_filter)
    if assignee_filter:
        qs = qs.filter(assigned_to_id=assignee_filter)

    # ... (Pagination logic remains same) ...
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    employees = User.objects.filter(is_active=True).exclude(is_superuser=True)

    existing_sources = list(Customer.objects.exclude(lead_source__isnull=True).exclude(lead_source='').values_list('lead_source', flat=True).distinct().order_by('lead_source'))
    source_choices = [(src, src.replace('_', ' ').title()) for src in existing_sources if src]

    context = {
        'customers': page_obj, 
        'modal_form': modal_form, # This now contains errors if POST failed
        'employees': employees,
        'query': query,
        'status_choices': Customer.STATUS_CHOICES,
        'source_choices': source_choices,
        'selected_status': status_filter,
        'selected_source': source_filter,
        'selected_assignee': assignee_filter,
    }

    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'customer-table-content':
        return render(request, 'core/partials/customer_table_rows.html', context)

    return render(request, 'core/customer_list.html', context)

import csv
import openpyxl
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from authentication.models import User  # Import your User model
from .models import Customer, CustomerPreference

# --- 1. DOWNLOAD SAMPLE CSV (Updated with all fields) ---
@login_required
def download_sample_file(request):
    """Generates a sample CSV file for bulk upload."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customer_upload_sample.csv"'

    writer = csv.writer(response)
    # 1. Define Headers
    headers = [
        'First Name', 'Last Name', 'Phone Number', 'Email', 
        'Company Name', 'City', 'State', 'Pincode', 'Address',
        'Lead Source', 'Status', 'Assigned To (Username)', 'Notes'
    ]
    writer.writerow(headers)
    
    # 2. Add Dummy Data
    writer.writerow([
        'Rahul', 'Sharma', '9876543210', 'rahul@example.com', 
        'Sharma Traders', 'Indore', 'MP', '452001', '123 Main St',
        'Website', 'Lead', 'admin', 'Interested in premium plan'
    ])
    writer.writerow([
        'Asian Paints', 'Store', '9123456789', '', 
        'Asian Paints', 'Delhi', 'Delhi', '110001', 'Connaught Place',
        'Manual Entry', 'Customer', '', 'Follow up next week'
    ])
    
    return response

# --- 2. BULK UPLOAD VIEW ---
@login_required
def bulk_upload_customers(request):
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'No file selected')
            return redirect('bulk_upload_customers')
            
        file = request.FILES['file']
        
        # Determine file type
        if file.name.endswith('.csv'):
            try:
                decoded_file = file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                process_import(reader, request)
            except Exception as e:
                messages.error(request, f"Error processing CSV: {str(e)}")
                
        elif file.name.endswith('.xlsx'):
            try:
                wb = openpyxl.load_workbook(file)
                sheet = wb.active
                rows = list(sheet.iter_rows(values_only=True))
                headers = rows[0]
                data = [dict(zip(headers, row)) for row in rows[1:]]
                process_import(data, request)
            except Exception as e:
                messages.error(request, f"Error processing Excel: {str(e)}")
        else:
            messages.error(request, 'Invalid file format. Please upload CSV or XLSX.')
            
        return redirect('customer_list')

    return render(request, 'core/bulk_upload.html')

# --- 3. IMPORT LOGIC (Updated Mapping) ---
def process_import(data, request):
    success_count = 0
    errors = []
    
    # Helper to map text to model choices (e.g., "Website" -> "website")
    def get_choice_key(value, choices):
        if not value: return None
        value = str(value).lower().strip()
        for key, label in choices:
            if label.lower() == value or key == value:
                return key
        return None # Default fallback

    for index, row in enumerate(data):
        # 1. Normalize Keys (Lowercase, strip spaces)
        row = {str(k).strip().lower(): v for k, v in row.items() if k}
        
        # 2. Extract Mandatory Fields
        first_name = row.get('first name') or row.get('name')
        phone = row.get('phone number') or row.get('phone') or row.get('mobile')
        
        if not first_name or not phone:
            errors.append(f"Row {index + 2}: Missing Name or Phone")
            continue
            
        # Clean Phone
        phone = str(phone).replace('tel:', '').replace('+', '').replace(' ', '').replace('-', '')[-10:]
        
        # Check Duplicates
        if Customer.objects.filter(phone=phone).exists():
            errors.append(f"Row {index + 2}: Phone {phone} already exists")
            continue

        # Handle Email Unique
        raw_email = row.get('email', '')
        email = str(raw_email).strip() if raw_email else None
        if email and Customer.objects.filter(email=email).exists():
            errors.append(f"Row {index + 2}: Email {email} is already taken")
            continue

        # --- NEW FIELD MAPPING ---
        
        # A. Lead Source & Status
        source_raw = row.get('lead source') or row.get('source')
        status_raw = row.get('status')
        
        lead_source = get_choice_key(source_raw, Customer.LEAD_SOURCE_CHOICES) or 'manual'
        status = get_choice_key(status_raw, Customer.STATUS_CHOICES) or 'lead'

        # B. Assigned User (Lookup by Username)
        assigned_username = row.get('assigned to (username)') or row.get('assigned to')
        assigned_user = None
        if assigned_username:
            try:
                assigned_user = User.objects.get(username__iexact=str(assigned_username).strip())
            except User.DoesNotExist:
                # Optional: Log warning but still create customer
                # errors.append(f"Row {index + 2}: User '{assigned_username}' not found. Customer set to Unassigned.")
                pass 

        try:
            customer = Customer.objects.create(
                # Basic
                first_name=first_name,
                last_name=row.get('last name', ''),
                phone=phone,
                email=email,
                
                # Business/Location
                # Note: 'company_name' removed from your model snippet, add back if exists
                # company_name=row.get('company name', ''), 
                address=row.get('address', ''),
                city=row.get('city', ''),
                state=row.get('state', ''),
                pincode=row.get('pincode', ''),
                country=row.get('country', 'India'),
                
                # CRM Fields
                lead_source=lead_source,
                status=status,
                assigned_to=assigned_user,
                notes=row.get('notes', ''),
                
                # Metadata
                created_by=request.user
            )
            
            # Create Preferences (Optional if model exists)
            # CustomerPreference.objects.create(customer=customer)
            
            success_count += 1
            
        except Exception as e:
            errors.append(f"Row {index + 2}: {str(e)}")

    # Feedback
    if success_count > 0:
        messages.success(request, f"Successfully imported {success_count} customers.")
    
    if errors:
        # Show top 5 errors
        error_msg = "Import Errors:<br>" + "<br>".join(errors[:5])
        if len(errors) > 5:
            error_msg += f"<br>...and {len(errors)-5} more."
        messages.warning(request, error_msg)
        

# ==========================================
#         HOSTINGER DATA MANAGEMENT
# ==========================================

@login_required
@user_passes_test(is_admin)
def app_user_list(request):
    """
    Lists users from the App database.
    """
    users_qs = HostingerUser.objects.all().order_by('-created_at')
    
    # Search logic
    query = request.GET.get('q', '')
    if query:
        users_qs = users_qs.filter(
            Q(name__icontains=query) | 
            Q(email__icontains=query)
        )

    # Role filter logic
    role_filter = request.GET.get('role', '')
    if role_filter == 'admin':
        users_qs = users_qs.filter(Q(name__icontains='admin') | Q(email__icontains='admin'))
    elif role_filter == 'seller':
        users_qs = users_qs.exclude(Q(name__icontains='admin') | Q(email__icontains='admin'))

    # Include Admin details if requested
    hostinger_admins = HostingerAdmin.objects.all()

    paginator = Paginator(users_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Compute computed_role and GST verification status for the current page
    from .models import VerifiedGST
    for h_user in page_obj:
        if 'admin' in h_user.name.lower() or 'admin' in h_user.email.lower():
            h_user.computed_role = 'Admin'
            h_user.gst_verified = False
        else:
            h_user.computed_role = 'Seller'
            company_gsts = list(Companies.objects.filter(user_id=h_user.id).exclude(gst='').exclude(gst__isnull=True).values_list('gst', flat=True))
            if company_gsts:
                normalized_gsts = [g.strip().upper() for g in company_gsts if g]
                h_user.gst_verified = VerifiedGST.objects.filter(gst_number__in=normalized_gsts).exists()
            else:
                h_user.gst_verified = False

    context = {
        'page_obj': page_obj,
        'hostinger_admins': hostinger_admins,
        'query': query,
        'selected_role': role_filter,
    }

    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'app-user-table-wrapper':
        return render(request, 'core/partials/app_user_table.html', context)

    return render(request, 'core/app_user_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_customer_list(request):
    """
    Lists customers (App Buyers) from the App database.
    """
    from hostinger_data.models import Customers as HostingerCustomer
    from .models import VerifiedGST
    
    customers_qs = HostingerCustomer.objects.all().order_by('-created_at')
    
    # Search logic
    query = request.GET.get('q', '').strip()
    if query:
        customers_qs = customers_qs.filter(
            Q(name__icontains=query) | 
            Q(email__icontains=query) |
            Q(mobile__icontains=query)
        )

    paginator = Paginator(customers_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Compute GST verification status for the current page
    for cust in page_obj:
        if cust.gstorpan:
            cust.gst_verified = VerifiedGST.objects.filter(gst_number=cust.gstorpan.strip().upper()).exists()
        else:
            cust.gst_verified = False

    context = {
        'page_obj': page_obj,
        'query': query,
    }

    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'app-customer-table-wrapper':
        return render(request, 'core/partials/app_customer_table.html', context)

    return render(request, 'core/app_customer_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_user_detail(request, user_id):
    """
    Detailed view of an App user and all related data.
    """
    h_user = get_object_or_404(HostingerUser, pk=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'edit_basic':
            h_user.name = request.POST.get('name')
            h_user.email = request.POST.get('email')
            h_user.save()
            messages.success(request, "Seller basic info updated successfully.")
            return redirect('app_user_detail', user_id=user_id)
            
        elif action == 'edit_company':
            company_id = request.POST.get('company_id')
            company = get_object_or_404(Companies, id=company_id, user_id=user_id)
            company.name = request.POST.get('name')
            company.status = int(request.POST.get('status', 0))
            company.email = request.POST.get('email')
            company.mobile = request.POST.get('mobile')
            company.maincategory_id = int(request.POST.get('maincategory_id', 0))
            company.gst = request.POST.get('gst', '')
            company.crn = request.POST.get('crn', '')
            company.minordervalue = int(request.POST.get('minordervalue', 0))
            company.city = request.POST.get('city', '')
            company.state = request.POST.get('state', '')
            company.pincode = int(request.POST.get('pincode') or 0)
            company.comission = int(request.POST.get('comission') or 0)
            company.restricted_city = request.POST.get('restricted_city', '')
            company.save()
            messages.success(request, "Company details updated successfully.")
            return redirect('app_user_detail', user_id=user_id)
            
        elif action == 'edit_bank':
            bank_id = request.POST.get('bank_id')
            bank = get_object_or_404(BankDetails, id=bank_id, user_id=user_id)
            bank.accountholder = request.POST.get('accountholder')
            bank.accountno = request.POST.get('accountno')
            bank.bankname = request.POST.get('bankname')
            bank.branch = request.POST.get('branch')
            bank.ifsc = request.POST.get('ifsc')
            bank.isprimary = request.POST.get('isprimary', '0')
            bank.status = request.POST.get('status', 'active')
            bank.save()
            messages.success(request, "Bank details updated successfully.")
            return redirect('app_user_detail', user_id=user_id)
            
    # Get related data from all identified tables
    context = {
        'h_user': h_user,
        'companies': Companies.objects.filter(user_id=user_id),
        'brands': Brands.objects.filter(user_id=user_id),
        'products': Products.objects.filter(user_id=user_id),
        'orders': Orders.objects.filter(user_id=user_id),
        'wallet': Wallet.objects.filter(user_id=user_id),
        'credits': Credits.objects.filter(user_id=user_id),
        'faqs': Faqs.objects.filter(user_id=user_id),
        'pages': Pages.objects.filter(user_id=user_id),
        'tickets': Tickets.objects.filter(user_id=user_id),
        'shade_cards': ShadeCards.objects.filter(user_id=user_id),
        'advertisements': Advertisements.objects.filter(user_id=user_id),
        'bank_details': BankDetails.objects.filter(user_id=user_id),
    }
    
    return render(request, 'core/app_user_detail.html', context)


@login_required
@user_passes_test(is_admin)
def banner_list(request):
    """View to show all banners with pagination and categories."""
    banners_qs = Advertisements.objects.all().order_by('sequence')
    
    # Pagination
    paginator = Paginator(banners_qs, 10)
    page_number = request.GET.get('page')
    banners = paginator.get_page(page_number)
    
    # Prefix for images/files
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for banner in banners:
        banner.image_url = f"{IMAGE_PREFIX}{banner.file}" if banner.file else None
        # Map category name
        try:
            cat_id = int(banner.content)
            banner.category_name = Categories.objects.filter(id=cat_id).values_list('name', flat=True).first()
        except (ValueError, TypeError):
            banner.category_name = None
        
    context = {
        'banners': banners,
    }
    return render(request, 'core/banner_list.html', context)


@login_required
@user_passes_test(is_admin)
def slider_list(request):
    """View to show all sliders with pagination."""
    sliders_qs = Sliders.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(sliders_qs, 10)
    page_number = request.GET.get('page')
    sliders = paginator.get_page(page_number)
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for slider in sliders:
        slider.image_url = f"{IMAGE_PREFIX}{slider.image}" if slider.image else None
        # Map category name
        if slider.company_id:
            slider.category_name = Categories.objects.filter(id=slider.company_id).values_list('name', flat=True).first()
        else:
            slider.category_name = None
        
    context = {
        'sliders': sliders,
    }
    return render(request, 'core/slider_list.html', context)


@login_required
@user_passes_test(is_admin)
def add_banner(request):
    """View to add a new banner."""
    if request.method == 'POST':
        form = BannerForm(request.POST)
        if form.is_valid():
            banner = form.save(commit=False)
            banner.user_id = 1  # Default admin/vendor ID
            banner.save()
            messages.success(request, "Banner created successfully.")
            return redirect('banner_list')
    else:
        form = BannerForm()
    return render(request, 'core/banner_form.html', {'form': form, 'title': 'Add New Banner'})


@login_required
@user_passes_test(is_admin)
def edit_banner(request, banner_id):
    """View to edit an existing banner."""
    banner = get_object_or_404(Advertisements, pk=banner_id)
    if request.method == 'POST':
        form = BannerForm(request.POST, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, "Banner updated successfully.")
            return redirect('banner_list')
    else:
        form = BannerForm(instance=banner)
    return render(request, 'core/banner_form.html', {'form': form, 'title': 'Edit Banner', 'banner': banner})


@login_required
@user_passes_test(is_admin)
def add_slider(request):
    """View to add a new slider."""
    if request.method == 'POST':
        form = SliderForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Slider created successfully.")
            return redirect('slider_list')
    else:
        form = SliderForm()
    return render(request, 'core/slider_form.html', {'form': form, 'title': 'Add New Slider'})


@login_required
@user_passes_test(is_admin)
def edit_slider(request, slider_id):
    """View to edit an existing slider."""
    slider = get_object_or_404(Sliders, pk=slider_id)
    if request.method == 'POST':
        form = SliderForm(request.POST, instance=slider)
        if form.is_valid():
            form.save()
            messages.success(request, "Slider updated successfully.")
            return redirect('slider_list')
    else:
        form = SliderForm(instance=slider)
    return render(request, 'core/slider_form.html', {'form': form, 'title': 'Edit Slider', 'slider': slider})



@login_required
@user_passes_test(is_admin)
def app_category_list(request):
    """View to show all application main categories."""
    main_categories = MainCategories.objects.all().order_by('sequence')
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for item in main_categories:
        item.image_url = f"{IMAGE_PREFIX}{item.image}" if item.image else None

    context = {
        'main_categories': main_categories,
    }
    return render(request, 'core/app_category_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_category_detail(request, main_category_id):
    """View to show categories related to a specific main category."""
    main_category = get_object_or_404(MainCategories, pk=main_category_id)
    categories = Categories.objects.filter(maincategory_id=main_category_id).order_by('sequence')
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for item in categories:
        item.image_url = f"{IMAGE_PREFIX}{item.image}" if item.image else None
        item.main_category_name = main_category.name

    context = {
        'main_category': main_category,
        'categories': categories,
    }
    return render(request, 'core/app_category_detail.html', context)


@login_required
@user_passes_test(is_admin)
def app_subcategory_list(request, category_id):
    """View to show sub categories related to a specific category."""
    category = get_object_or_404(Categories, pk=category_id)
    main_category = get_object_or_404(MainCategories, pk=category.maincategory_id)
    sub_categories = SubCategories.objects.filter(category_id=category_id).order_by('name')
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for item in sub_categories:
        item.image_url = f"{IMAGE_PREFIX}{item.image}" if item.image else None
        item.category_name = category.name

    context = {
        'main_category': main_category,
        'category': category,
        'sub_categories': sub_categories,
    }
    return render(request, 'core/app_subcategory_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_brand_list(request):
    """View to show all application brands."""
    brands = AppBrands.objects.all().order_by('name')
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for brand in brands:
        brand.image_url = f"{IMAGE_PREFIX}{brand.image}" if brand.image else None
        brand.company_name = AppCompanies.objects.filter(id=brand.company_id).values_list('name', flat=True).first()
        
    context = {
        'brands': brands,
    }
    return render(request, 'core/app_brand_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_company_list(request):
    """View to show all application companies/vendors."""
    companies = AppCompanies.objects.all().order_by('-created_at')
    
    context = {
        'companies': companies,
    }
    return render(request, 'core/app_company_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_ticket_list(request):
    """View to show all support tickets."""
    tickets = AppTickets.objects.all().order_by('-created_at')
    
    context = {
        'tickets': tickets,
    }
    return render(request, 'core/app_ticket_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_wallet_transactions(request):
    """View to show all wallet transactions."""
    transactions = AppWallet.objects.all().order_by('-created_at')
    
    context = {
        'transactions': transactions,
    }
    return render(request, 'core/app_wallet_list.html', context)


@login_required
@user_passes_test(is_admin)
def app_faq_list(request):
    """View to show all FAQs."""
    faqs = AppFaqs.objects.all().order_by('-created_at')
    
    context = {
        'faqs': faqs,
    }
    return render(request, 'core/app_faq_list.html', context)


# ==========================================
#         INVOICE MANAGEMENT
# ==========================================

@login_required
def invoice_list(request):
    """Lists all invoices with filters and search."""
    invoices = Invoice.objects.all().order_by('-created_at')
    
    # 1. Search logic
    query = request.GET.get('q', '')
    if query:
        invoices = invoices.filter(
            Q(invoice_no__icontains=query) | 
            Q(client_name__icontains=query)
        )

    # 2. Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'finalized':
        invoices = invoices.filter(is_finalized=True)
    elif status_filter == 'draft':
        invoices = invoices.filter(is_finalized=False)
        
    # 3. Pagination
    paginator = Paginator(invoices, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'selected_status': status_filter,
    }
    
    # 4. HTMX Integration
    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'invoice-table-wrapper':
        return render(request, 'core/partials/invoice_table.html', context)
    
    return render(request, 'core/invoice_list.html', context)

@login_required
def create_invoice(request):
    """View to create a new invoice."""
    if request.method == 'POST':
        hostinger_user_id = request.POST.get('hostinger_user_id')
        total_amount = request.POST.get('total_amount')
        gst_type = request.POST.get('gst_type') # 'inclusive' or 'exclusive'
        
        h_user = get_object_or_404(HostingerUser, id=hostinger_user_id)
        
        # Get details from Hostinger Companies table if possible
        h_company = Companies.objects.filter(user_id=hostinger_user_id).first()
        
        # Determine state code
        client_gstin = request.POST.get('client_gstin') or (h_company.gst if h_company else None)
        client_state_code = "23" # Default MP
        if client_gstin and len(client_gstin) >= 2:
            client_state_code = client_gstin[:2]
        
        # Calculate GST
        is_inclusive = (gst_type == 'inclusive')
        vals = calculate_gst_values(total_amount, is_inclusive, client_state_code)
        
        # Create Invoice
        invoice = Invoice.objects.create(
            invoice_no=get_next_invoice_number(),
            hostinger_user_id=hostinger_user_id,
            created_by=request.user,
            client_name=request.POST.get('client_name') or h_user.name,
            client_gstin=client_gstin,
            client_state_code=client_state_code,
            place_of_supply=request.POST.get('place_of_supply') or (h_company.state if h_company else 'Madhya Pradesh'),
            taxable_value=vals['taxable_value'],
            gst_total=vals['gst_total'],
            cgst=vals['cgst'],
            sgst=vals['sgst'],
            igst=vals['igst'],
            total_amount=vals['total_amount'],
            payment_mode=request.POST.get('payment_mode', 'Cheque'),
        )
        
        # Create Items
        # 1. Product Listing
        if vals['listing_taxable'] > 0:
            item_vals = calculate_gst_values(vals['listing_taxable'], False, client_state_code)
            InvoiceItem.objects.create(
                invoice=invoice,
                description="Product Listing & Data Entry Charges",
                sac_code="998361",
                taxable_value=vals['listing_taxable'],
                gst_rate=18.00,
                cgst=item_vals['cgst'],
                sgst=item_vals['sgst'],
                igst=item_vals['igst'],
                total_amount=item_vals['total_amount']
            )
            
        # 2. Marketing Services
        if vals['marketing_taxable'] > 0:
            item_vals = calculate_gst_values(vals['marketing_taxable'], False, client_state_code)
            InvoiceItem.objects.create(
                invoice=invoice,
                description="Marketing & Promotional Services (Includes WhatsApp Campaign, Digital Promotion, Creative Support & Campaign Management)",
                sac_code="998361",
                taxable_value=vals['marketing_taxable'],
                gst_rate=18.00,
                cgst=item_vals['cgst'],
                sgst=item_vals['sgst'],
                igst=item_vals['igst'],
                total_amount=item_vals['total_amount']
            )
            
        messages.success(request, f"Invoice {invoice.invoice_no} created successfully.")
        return redirect('invoice_detail', invoice_id=invoice.id)
        
    hostinger_users = HostingerUser.objects.all().order_by('name')
    return render(request, 'core/invoice_form.html', {'hostinger_users': hostinger_users})

@login_required
def invoice_detail(request, invoice_id):
    """View to see invoice details."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    return render(request, 'core/invoice_detail.html', {'invoice': invoice})

@login_required
def finalize_invoice(request, invoice_id):
    """Locks the invoice from further edits."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.method == 'POST':
        invoice.is_finalized = True
        invoice.save()
        messages.success(request, "Invoice finalized and locked.")
    return redirect('invoice_detail', invoice_id=invoice.id)

@login_required
def download_invoice_pdf(request, invoice_id):
    """Generates and downloads PDF of the invoice."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    # For now, we will render a clean print-friendly HTML page
    # In a real environment, you'd use weasyprint or reportlab here
    return render(request, 'core/invoice_pdf.html', {'invoice': invoice})


from django.core.mail import EmailMessage
from django.conf import settings
import os

@login_required
def send_invoice_email(request, invoice_id):
    """Sends the invoice PDF to the user's email."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    h_user = get_object_or_404(HostingerUser, id=invoice.hostinger_user_id)
    
    if not h_user.email:
        messages.error(request, "User does not have an email address.")
        return redirect('invoice_detail', invoice_id=invoice.id)

    # Render the invoice HTML for the email body or as an attachment
    # For now, we send a link and basic details
    subject = f"Tax Invoice {invoice.invoice_no} from ApniFactory"
    body = f"Dear {h_user.name},\n\nPlease find attached your tax invoice {invoice.invoice_no} for marketing services.\n\nTotal Amount: ₹{invoice.total_amount}\n\nThank you for choosing ApniFactory!"
    
    email = EmailMessage(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [h_user.email],
    )
    
    # Optional: Attach PDF if you have a library like WeasyPrint
    # For now, we'll notify success
    try:
        email.send()
        messages.success(request, f"Invoice sent to {h_user.email} successfully.")
    except Exception as e:
        messages.error(request, f"Failed to send email: {str(e)}")
        
    return redirect('invoice_detail', invoice_id=invoice.id)

@login_required
def send_invoice_whatsapp(request, invoice_id):
    """Sends invoice details to the user via WhatsApp."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    h_user = get_object_or_404(HostingerUser, id=invoice.hostinger_user_id)
    
    # Get phone from Companies or other related table if not in Users
    h_company = Companies.objects.filter(user_id=h_user.id).first()
    phone = h_company.mobile if h_company else None
    
    if not phone:
        messages.error(request, "User/Company does not have a mobile number.")
        return redirect('invoice_detail', invoice_id=invoice.id)

    # Format message
    message = (
        f"*TAX INVOICE: {invoice.invoice_no}*\n\n"
        f"Dear {h_user.name},\n"
        f"Your invoice for marketing services is ready.\n\n"
        f"*Total Amount:* ₹{invoice.total_amount}\n"
        f"*Status:* {invoice.payment_status.upper()}\n\n"
        f"Thank you for choosing ApniFactory!"
    )
    
    from .utils import send_text_message
    try:
        send_text_message(phone, message)
        messages.success(request, f"Invoice details sent to {phone} via WhatsApp.")
    except Exception as e:
        messages.error(request, f"Failed to send WhatsApp: {str(e)}")
        
    return redirect('invoice_detail', invoice_id=invoice.id)


# ==========================================
#         API & UTILS
# ==========================================

import requests
import urllib3
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
# from .forms import CustomerForm
# from .models import Customer, CustomerPreference

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- LOCAL DATA (Safety Net) ---
LOCAL_PINCODE_MAP = {
    "452010": {"city": "Indore", "state": "Madhya Pradesh"},
    "452001": {"city": "Indore", "state": "Madhya Pradesh"},
    "110001": {"city": "New Delhi", "state": "Delhi"},
    "302001": {"city": "Jaipur", "state": "Rajasthan"},
    "400001": {"city": "Mumbai", "state": "Maharashtra"},
    "560001": {"city": "Bangalore", "state": "Karnataka"},
}

INDIAN_STATES_CITIES = {
    "Andhra Pradesh": ["Anantapur", "Chittoor", "East Godavari", "Guntur", "Krishna", "Kurnool", "Nellore", "Prakasam", "Srikakulam", "Visakhapatnam", "Vizianagaram", "West Godavari"], 
            "Arunachal Pradesh": ["Anjaw", "Changlang", "Dibang Valley", "East Siang", "East Siang", "East Siang", "East Siang", "East Siang", "East Siang", "East Siang", "East Siang"],
            "Assam": ["Barpeta", "Bongaigaon", "Cachar", "Charaideo", "Chirang", "Darrang", "Dhemaji", "Dhubri", "Dibrugarh", "Dima Hasao", "Goalpara", "Golaghat", "Hailakandi", "Hazaribag", "Jorhat", "Kamrup Metropolitan", "Kamrup", "Karbi Anglong", "Karimganj", "Kokrajhar", "Lakhimpur", "Majuli", "Moranha", "Nagaon", "Nalbari", "North Cachar Hills", "Sivasagar", "Sonitpur", "South Cachar Hills", "Tinsukia", "Udalguri", "West Karbi Anglong"],
            "Bihar": ["Araria", "Aurangabad", "Bhojpur", "Buxar", "Darbhanga", "East Champaran", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur", "Katihar", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur", "Nalanda", "Nawada", "Patna", "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran", "Sheikhpura", "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali", "West Champaran"],
            "Chhattisgarh": ["Balod", "Baloda Bazar", "Balrampur", "Bastar", "Bemetara", "Bijapur", "Bilaspur", "Dakshin Bastar Dantewada", "Dhamtari", "Durg", "Gariyaband", "Gaurela Pendra Marwahi", "Janjgir-Champa", "Jashpur", "Kabirdham", "Kanker", "Kondagaon", "Korba", "Koriya", "Mahasamund", "Mungeli", "Narayanpur"],
            "Goa": ["North Goa", "South Goa"],
            "Gujarat": ["Ahmedabad", "Amreli", "Anand", "Aravalli", "Banaskantha", "Bharuch", "Bhavnagar", "Botad", "Chhota Udaipur", "Dahod", "Dang", "Devbhoomi Dwarka", "Gandhinagar", "Gir Somnath", "Jamnagar", "Junagadh", "Kheda", "Kutch", "Mahisagar", "Mehsana", "Morbi", "Narmada", "Navsari", "Panchmahal", "Patan", "Porbandar", "Rajkot", "Sabarkantha", "Surat", "Surendranagar", "Tapi", "Vadodara", "Valsad"],
            "Haryana": ["Ambala", "Bhiwani", "Charkhi Dadri", "Faridabad", "Fatehabad", "Gurugram", "Hisar", "Jhajjar", "Jind", "Kaithal", "Karnal", "Kurukshetra", "Mahendragarh", "Nuh", "Palwal", "Panchkula", "Panipat", "Rewari", "Rohtak", "Sirsa", "Sonipat", "Yamunanagar"],
            "Himachal Pradesh": ["Bilaspur", "Chamba", "Hamirpur", "Kangra", "Kinnaur", "Kullu", "Lahaul and Spiti", "Mandi", "Shimla", "Sirmaur", "Solan", "Una"],
            "Jharkhand": ["Bokaro", "Chatra", "Deoghar", "Dhanbad", "Dumka", "East Singhbhum", "Garhwa", "Giridih", "Godda", "Gumla", "Hazaribagh", "Jamtara", "Khunti", "Koderma", "Latehar", "Lohardaga", "Pakur", "Palamu", "Ramgarh", "Ranchi", "Sahebganj", "Seraikela Kharsawan", "Simdega", "West Singhbhum"],
            "Karnataka": ["Bagalkot", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban", "Bidar", "Chamarajanagar", "Chikballapur", "Chikkamagaluru", "Chitradurga", "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri", "Kalaburagi", "Kodagu", "Kolar", "Koppal", "Mandya", "Mysuru", "Raichur", "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada", "Vijayapura", "Yadgir"],
            "Kerala": ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"],
            "Madhya Pradesh": ["Alirajpur", "Anuppur", "Ashoknagar", "Balaghat", "Barwani", "Betul", "Bhind", "Bhopal", "Burhanpur", "Chhatarpur", "Chhindwara", "Damoh", "Datia", "Dewas", "Dhar", "Dindori", "Guna", "Gwalior", "Harda", "Hoshangabad", "Indore", "Jabalpur", "Jhabua", "Katni", "Khandwa", "Khargone", "Mandla", "Mandsaur", "Morena", "Narsinghpur", "Neemuch", "Panna", "Raisen", "Rajgarh", "Ratlam", "Rewa", "Sagar", "Satna", "Sehore", "Seoni", "Shahdol", "Shajapur", "Sheopur", "Shivpuri", "Sidhi", "Singrauli", "Tikamgarh", "Ujjain", "Umaria", "Vidisha"],
            "Maharashtra": ["Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana", "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna", "Kolhapur", "Latur", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar", "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad", "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha", "Washim", "Yavatmal"],
            "Manipur": ["Bishnupur", "Chandel", "Churachandpur", "Imphal East", "Imphal West", "Jiribam", "Kakching", "Kamjong", "Kangpokpi", "Noney", "Pherzawl", "Senapati", "Tamenglong", "Tengnoupal", "Thoubal", "Ukhrul"],
            "Meghalaya": ["East Garo Hills", "East Jaintia Hills", "East Khasi Hills", "North Garo Hills", "Ri Bhoi", "South Garo Hills", "South West Garo Hills", "South West Khasi Hills", "West Garo Hills", "West Jaintia Hills", "West Khasi Hills"],
            "Mizoram": ["Aizawl", "Champhai", "Hnahthial", "Khawzawl", "Kolasib", "Lawngtlai", "Lunglei", "Mamit", "Saiha", "Saitual", "Serchhip"],
            "Nagaland": ["Dimapur", "Kiphire", "Kohima", "Longleng", "Mokokchung", "Mon", "Peren", "Phek", "Tuensang", "Wokha", "Zunheboto"],
            "Odisha": ["Angul", "Balangir", "Balasore", "Bargarh", "Bhadrak", "Bhubaneswar", "Boudh", "Cuttack", "Deogarh", "Dhenkanal", "Gajapati", "Ganjam", "Jagatsinghpur", "Jajpur", "Jharsuguda", "Kalahandi", "Kandhamal", "Kendrapara", "Kendujhar", "Khordha", "Koraput", "Malkangiri", "Mayurbhanj", "Nabarangpur", "Nayagarh", "Nuapada", "Puri", "Rayagada", "Sambalpur", "Subarnapur", "Sundargarh"],
            "Punjab": ["Amritsar", "Barnala", "Bathinda", "Faridkot", "Fatehgarh Sahib", "Fazilka", "Ferozepur", "Gurdaspur", "Hoshiarpur", "Jalandhar", "Kapurthala", "Ludhiana", "Mansa", "Moga", "Muktsar", "Nawanshahr", "Pathankot", "Patiala", "Rupnagar", "Sangrur", "SAS Nagar", "Tarn Taran"],
            "Rajasthan": ["Ajmer", "Alwar", "Banswara", "Baran", "Barmer", "Bharatpur", "Bhilwara", "Bikaner", "Bundi", "Chittorgarh", "Churu", "Dausa", "Dholpur", "Dungarpur", "Hanumangarh", "Jaipur", "Jaisalmer", "Jalore", "Jhalawar", "Jhunjhunu", "Jodhpur", "Karauli", "Kota", "Nagaur", "Pali", "Pratapgarh", "Rajsamand", "Sawai Madhopur", "Sikar", "Sirohi", "Sri Ganganagar", "Tonk", "Udaipur"],
            "Sikkim": ["East Sikkim", "North Sikkim", "South Sikkim", "West Sikkim"],
            "Tamil Nadu": ["Ariyalur", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri", "Dindigul", "Erode", "Kanchipuram", "Kanyakumari", "Karur", "Krishnagiri", "Madurai", "Nagapattinam", "Namakkal", "Nilgiris", "Perambalur", "Pudukkottai", "Ramanathapuram", "Salem", "Sivaganga", "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore", "Viluppuram", "Virudhunagar"],
            "Telangana": ["Adilabad", "Bhadradri Kothagudem", "Hyderabad", "Jagtial", "Jangaon", "Jayashankar Bhupalpally", "Jogulamba Gadwal", "Kamareddy", "Karimnagar", "Khammam", "Komaram Bheem Asifabad", "Mahabubabad", "Mahabubnagar", "Mancherial", "Medak", "Medchal-Malkajgiri", "Mulugu", "Nagarkurnool", "Nalgonda", "Narayanpet", "Nirmal", "Nizamabad", "Peddapalli", "Rajanna Sircilla", "Rangareddy", "Sangareddy", "Siddipet", "Suryapet", "Vikarabad", "Wanaparthy", "Warangal Rural", "Warangal Urban", "Yadadri Bhuvanagiri"],
            "Tripura": ["Dhalai", "Gomati", "Khowai", "North Tripura", "Sepahijala", "South Tripura", "Unakoti", "West Tripura"],
            "Uttar Pradesh": ["Agra", "Aligarh", "Ambedkar Nagar", "Amethi", "Amroha", "Auraiya", "Azamgarh", "Baghpat", "Bahraich", "Ballia", "Balrampur", "Banda", "Barabanki", "Bareilly", "Basti", "Bhadohi", "Bijnor", "Budaun", "Bulandshahr", "Chandauli", "Chitrakoot", "Deoria", "Etah", "Etawah", "Ayodhya", "Farrukhabad", "Fatehpur", "Firozabad", "Gautam Buddha Nagar", "Ghaziabad", "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur", "Hapur", "Hardoi", "Hathras", "Jalaun", "Jaunpur", "Jhansi", "Kannauj", "Kanpur Dehat", "Kanpur Nagar", "Kasganj", "Kaushambi", "Kushinagar", "Lakhimpur Kheri", "Lalitpur", "Lucknow", "Maharajganj", "Mahoba", "Mainpuri", "Mathura", "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar", "Pilibhit", "Pratapgarh", "Prayagraj", "Rae Bareli", "Rampur", "Saharanpur", "Sambhal", "Sant Kabir Nagar", "Shahjahanpur", "Shamli", "Shravasti", "Siddharthnagar", "Sitapur", "Sonbhadra", "Sultanpur", "Unnao", "Varanasi"],
            "Uttarakhand": ["Almora", "Bageshwar", "Chamoli", "Champawat", "Dehradun", "Haridwar", "Nainital", "Pauri Garhwal", "Pithoragarh", "Rudraprayag", "Tehri Garhwal", "Udham Singh Nagar", "Uttarkashi"],
            "West Bengal": ["Alipurduar", "Bankura", "Birbhum", "Cooch Behar", "Dakshin Dinajpur", "Darjeeling", "Hooghly", "Howrah", "Jalpaiguri", "Jhargram", "Kalimpong", "Kolkata", "Malda", "Murshidabad", "Nadia", "North 24 Parganas", "Paschim Bardhaman", "Paschim Medinipur", "Purba Bardhaman", "Purba Medinipur", "Purulia", "South 24 Parganas", "Uttar Dinajpur"],
            "Andaman and Nicobar Islands": ["Nicobar", "North and Middle Andaman", "South Andaman"],
            "Chandigarh": ["Chandigarh"],
            "Dadra and Nagar Haveli and Daman and Diu": ["Dadra and Nagar Haveli", "Daman", "Diu"],
            "Delhi": ["Central Delhi", "East Delhi", "New Delhi", "North Delhi", "North East Delhi", "North West Delhi", "Shahdara", "South Delhi", "South East Delhi", "South West Delhi", "West Delhi"],
            "Jammu and Kashmir": ["Anantnag", "Bandipora", "Baramulla", "Budgam", "Doda", "Ganderbal", "Jammu", "Kathua", "Kishtwar", "Kulgam", "Kupwara", "Poonch", "Pulwama", "Rajouri", "Ramban", "Reasi", "Samba", "Shopian", "Srinagar", "Udhampur"],
            "Ladakh": ["Kargil", "Leh"],
            "Lakshadweep": ["Lakshadweep"],
            "Puducherry": ["Karaikal", "Mahe", "Puducherry", "Yanam"]
}

def get_external_data(url):
    """Helper to fetch data with proper headers to avoid blocking."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=4, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"External API Error ({url}): {e}")
        return None

# --- API ENDPOINTS ---

@login_required
def api_get_cities(request):
    state = request.GET.get('state')
    cities = INDIAN_STATES_CITIES.get(state, [])
    data = [{'value': city, 'label': city} for city in cities]
    return JsonResponse({'cities': data})

@login_required
def api_get_pincode_details(request):
    pincode = request.GET.get('pincode')
    
    if not pincode or len(pincode) < 6:
        return JsonResponse({'error': 'Invalid format'}, status=400)

    # 1. Local Fallback
    if pincode in LOCAL_PINCODE_MAP:
        data = LOCAL_PINCODE_MAP[pincode]
        return JsonResponse(data)

    # 2. External API
    data = get_external_data(f"https://api.postalpincode.in/pincode/{pincode}")
    
    if data and isinstance(data, list) and data[0]['Status'] == 'Success':
        details = data[0]['PostOffice'][0]
        return JsonResponse({
            'city': details.get('District'),
            'state': details.get('State'),
            'country': 'India'
        })
    
    return JsonResponse({'error': 'Not found'}, status=404)

@login_required
def api_get_pincodes_for_city(request):
    city = request.GET.get('city')
    if not city:
        return JsonResponse({'pincodes': []})

    unique_pincodes = set()

    # 1. Local Search
    for pin, data in LOCAL_PINCODE_MAP.items():
        if data['city'].lower() == city.lower():
            unique_pincodes.add(str(pin).strip())

    # 2. External API Search
    if len(unique_pincodes) == 0:
        data = get_external_data(f"https://api.postalpincode.in/postoffice/{city}")
        
        if data and isinstance(data, list) and data[0]['Status'] == 'Success':
            for office in data[0]['PostOffice']:
                val = str(office.get('Pincode', '')).strip()
                if val:
                    unique_pincodes.add(val)

    results = [{'value': p, 'label': p} for p in sorted(unique_pincodes)]
    return JsonResponse({'pincodes': results})

import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Customer, WhatsAppLead, WhatsAppChat, CustomerPreference
# UPDATED IMPORT
from .utils import send_text_message, verify_gst_number_live 
from .bot_messages import BOT_RESPONSES

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == settings.META_VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse('Forbidden', status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            if 'messages' in value:
                msg_data = value['messages'][0]
                phone_number = msg_data['from']
                
                profile_name = "WhatsApp User"
                contacts = value.get('contacts', [])
                if contacts:
                    profile_name = contacts[0].get('profile', {}).get('name', "WhatsApp User")

                text_body = ""
                if msg_data['type'] == 'text':
                    text_body = msg_data['text']['body']
                elif msg_data['type'] == 'button':
                    text_body = msg_data['button']['payload']
                
                process_conversation(phone_number, profile_name, text_body)

            return HttpResponse('EVENT_RECEIVED', status=200)
        except Exception as e:
            print(f"Webhook Error: {e}")
            return HttpResponse('ERROR', status=500)

def process_conversation(phone, profile_name, message):
    # 1. SYNC CUSTOMER
    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={'first_name': profile_name, 'lead_source': 'whatsapp', 'whatsapp_number': phone}
    )
    if created: CustomerPreference.objects.create(customer=customer)

    # 2. LOG CHAT
    WhatsAppChat.objects.create(customer=customer, message=message, direction='incoming')

    # 3. SYNC BOT STATE
    lead, _ = WhatsAppLead.objects.get_or_create(phone_number=phone)
    if not lead.customer:
        lead.customer = customer
        lead.save()

    if lead.needs_human: return 

    # --- VERIFIED USER LOGIC ---
    if customer.is_gst_verified:
        if message.lower() in ['hi', 'hello', 'start', 'reset']:
            msg = BOT_RESPONSES['verified_welcome'].format(name=customer.first_name)
            send_reply_text(lead, msg)
        else:
            send_reply_text(lead, BOT_RESPONSES['support_contact'])
        return

    # --- UNVERIFIED / ONBOARDING LOGIC ---
    if message.lower() in ['hi', 'hello', 'start', 'reset']:
        lead.conversation_stage = 'W-001'
        lead.save()
        send_reply_text(lead, BOT_RESPONSES['onboard_menu'])
        return

    stage = lead.conversation_stage
    clean_msg = message.strip().upper()

    # --- STAGE HANDLERS ---
    if stage == 'W-001':
        if clean_msg == '1': 
            lead.user_type = 'seller'
            lead.conversation_stage = 'S-001'
            send_reply_text(lead, BOT_RESPONSES['seller_segment'])
        elif clean_msg == '2': 
            lead.user_type = 'buyer'
            lead.conversation_stage = 'B-001'
            send_reply_text(lead, BOT_RESPONSES['buyer_segment'])
        elif clean_msg == '3': 
            lead.user_type = 'enquiry'
            lead.conversation_stage = 'E-001'
            send_reply_text(lead, BOT_RESPONSES['general_inquiry'])
        else:
            send_reply_text(lead, BOT_RESPONSES['invalid_input'])
        lead.save()

    elif stage == 'S-001':
        if clean_msg in ['1', '2', '3']:
            lead.conversation_stage = 'S-002'
            send_reply_text(lead, BOT_RESPONSES['gst_confirm'])
            lead.save()
        else:
            send_reply_text(lead, BOT_RESPONSES['invalid_input'])

    elif stage == 'S-002':
        if clean_msg in ['YES', 'Y']:
            lead.gst_status = 'pending'
            lead.conversation_stage = 'S-003'
            send_reply_text(lead, BOT_RESPONSES['gst_input'])
        elif clean_msg in ['NO', 'N']:
            lead.gst_status = 'no_gst'
            lead.conversation_stage = 'S-004'
            send_reply_text(lead, BOT_RESPONSES['no_gst_notice'])
        else:
            send_reply_text(lead, "Please reply YES or NO.")
        lead.save()

    # --- LIVE GST VERIFICATION ---
    elif stage == 'S-003':
        # Using the NEW Live Function
        is_valid, gst_data = verify_gst_number_live(clean_msg)
        
        if is_valid:
            from .models import VerifiedGST
            VerifiedGST.objects.get_or_create(gst_number=clean_msg.strip().upper())
            lead.gst_status = 'verified'
            lead.conversation_stage = 'S-005'
            
            # Sync Live Data to Database
            customer.gst_number = clean_msg
            # Prefer Trade Name (Business Name) for Company Name
            customer.company_name = gst_data.get('trade_name') or gst_data.get('legal_name', '')
            customer.address = gst_data.get('address', '')
            customer.city = gst_data.get('city', '')
            customer.state = gst_data.get('state', '')
            customer.pincode = gst_data.get('pincode', '')
            
            # Mark Verified
            customer.is_gst_verified = True
            customer.status = 'customer'
            customer.save()
            
            # Send Success with Company Name
            msg = BOT_RESPONSES['gst_verified'].format(company_name=customer.company_name)
            send_reply_text(lead, msg)
        else:
            lead.gst_status = 'failed'
            send_reply_text(lead, BOT_RESPONSES['gst_failed'])
        lead.save()

    elif stage == 'B-001':
        if clean_msg in ['1', '2']:
            lead.conversation_stage = 'B-002'
            send_reply_text(lead, BOT_RESPONSES['buyer_success'])
            lead.save()

def send_reply_text(lead, text):
    send_text_message(lead.phone_number, text)
    WhatsAppChat.objects.create(customer=lead.customer, message=text, direction='outgoing')


@login_required
@user_passes_test(is_admin)
def manage_leaves(request):
    """Enables admins to view and approve/reject employee leave requests."""
    pending_leaves = LeaveRequest.objects.filter(status='pending').order_by('-created_at')
    completed_leaves = LeaveRequest.objects.exclude(status='pending').order_by('-created_at')
    
    context = {
        'pending_leaves': pending_leaves,
        'completed_leaves': completed_leaves,
    }
    return render(request, 'core/manage_leaves.html', context)


@login_required
@user_passes_test(is_admin)
def approve_leave(request, leave_id):
    """Approves a leave request and notifies the employee."""
    if request.method != 'POST':
        return HttpResponse("Method Not Allowed", status=405)
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    if leave.status == 'pending':
        leave.status = 'approved'
        leave.approved_by = request.user
        leave.save()
        
        # Notify the employee
        Notification.objects.create(
            recipient=leave.employee,
            message=f"Your leave request for {leave.get_leave_type_display()} from {leave.start_date} to {leave.end_date} has been Approved.",
            is_read=False
        )
        
        messages.success(request, f"Approved leave request for {leave.employee.username}.")
    else:
        messages.info(request, "Leave request is already processed.")
        
    return redirect('manage_leaves')


@login_required
@user_passes_test(is_admin)
def reject_leave(request, leave_id):
    """Rejects a leave request and notifies the employee."""
    if request.method != 'POST':
        return HttpResponse("Method Not Allowed", status=405)
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    if leave.status == 'pending':
        leave.status = 'rejected'
        leave.approved_by = request.user
        leave.save()
        
        # Notify the employee
        Notification.objects.create(
            recipient=leave.employee,
            message=f"Your leave request for {leave.get_leave_type_display()} from {leave.start_date} to {leave.end_date} has been Rejected.",
            is_read=False
        )
        
        messages.warning(request, f"Rejected leave request for {leave.employee.username}.")
    else:
        messages.info(request, "Leave request is already processed.")
        
    return redirect('manage_leaves')


def is_admin_or_manager(user):
    return user.is_superuser or user.role in ['admin', 'manager']


@login_required
@user_passes_test(is_admin_or_manager)
def lead_kanban(request):
    """Enables admins to view and manage leads in a Kanban column layout."""
    from .forms import CustomerModalForm
    
    if request.method == 'POST':
        form = CustomerModalForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, f"Lead {customer.first_name} manually added successfully.")
            return redirect('lead_kanban')
        else:
            messages.error(request, "Failed to create lead. Please check the form errors.")
    else:
        form = CustomerModalForm()
        
    customers = Customer.objects.all().select_related('assigned_to')
    
    # Filter customers by column
    leads = customers.filter(status='lead')
    prospects = customers.filter(status='prospect')
    active_customers = customers.filter(status='customer')
    inactive = customers.filter(status='inactive')
    lost = customers.filter(status='lost')
    
    employees = User.objects.filter(is_active=True).exclude(is_superuser=True)
    
    context = {
        'leads': leads,
        'prospects': prospects,
        'active_customers': active_customers,
        'inactive': inactive,
        'lost': lost,
        'employees': employees,
        'form': form,
    }
    return render(request, 'core/lead_kanban.html', context)


@login_required
def update_customer_status(request, customer_id):
    """Enables quick status updates via HTMX request."""
    customer = get_object_or_404(Customer, id=customer_id)
    old_status = customer.get_status_display()
    new_status_val = request.POST.get('status') or request.GET.get('status')
    
    if new_status_val in dict(Customer.STATUS_CHOICES):
        customer.status = new_status_val
        customer.save()
        
        CustomerActivityLog.objects.create(
            customer=customer,
            employee=request.user,
            action="Status Updated (Kanban)",
            description=f"Status transitioned from {old_status} to {customer.get_status_display()}."
        )
        
        if request.headers.get('HX-Request') == 'true':
            if request.GET.get('board') == 'true':
                if request.GET.get('employee') == 'true':
                    return redirect('employee_portal:lead_kanban')
                return redirect('lead_kanban')
            # Returns a small HTML badge response for HTMX updates
            badge_color = 'success' if new_status_val == 'customer' else 'info' if new_status_val == 'lead' else 'warning' if new_status_val == 'prospect' else 'danger'
            return HttpResponse(f'<span class="badge badge-phoenix badge-phoenix-{badge_color} text-capitalize fs-11">{customer.get_status_display()}</span>')
            
        messages.success(request, f"Successfully updated status for {customer.first_name}.")
    else:
        messages.error(request, "Invalid status choice.")
        
    return redirect('customer_detail', customer_id=customer.id)


@login_required
def global_search(request):
    """Universal instant autocomplete search for Customers, Users, Orders, Products."""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return HttpResponse('')
        
    # Search Customers
    customers = Customer.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query)
    ).select_related('assigned_to')[:5]
    
    # Search Orders (Admins and Managers only)
    orders = []
    if request.user.is_superuser or request.user.role in ['admin', 'manager']:
        orders = Orders.objects.filter(
            Q(orderno__icontains=query) |
            Q(address__icontains=query)
        )[:5]
        
    # Search Users (Admins and Managers only)
    users = []
    if request.user.is_superuser or request.user.role in ['admin', 'manager']:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )[:5]
        
    # Search Products
    products = Products.objects.filter(
        Q(name__icontains=query) |
        Q(title__icontains=query)
    )[:5]
    
    context = {
        'customers': customers,
        'orders': orders,
        'users': users,
        'products': products,
        'query': query,
    }
    return render(request, 'core/partials/global_search_results.html', context)


@login_required
def verify_gst_ajax(request):
    gst_number = request.GET.get('gst_number', '').strip().upper()
    customer_id = request.GET.get('customer_id')
    company_id = request.GET.get('company_id')
    
    if not gst_number:
        return JsonResponse({'success': False, 'message': 'No GST number provided.'})
        
    from .utils import verify_gst_number_live
    is_valid, gst_data = verify_gst_number_live(gst_number)
    
    if is_valid:
        from .models import VerifiedGST
        VerifiedGST.objects.get_or_create(gst_number=gst_number)
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
                customer.is_gst_verified = True
                if gst_data.get('legal_name'):
                    customer.company_name = gst_data['trade_name'] or gst_data['legal_name']
                if gst_data.get('address'):
                    customer.address = gst_data['address']
                if gst_data.get('city'):
                    customer.city = gst_data['city']
                if gst_data.get('state'):
                    customer.state = gst_data['state']
                if gst_data.get('pincode'):
                    customer.pincode = gst_data['pincode']
                customer.save()
                
                CustomerActivityLog.objects.create(
                    customer=customer,
                    employee=request.user,
                    action="GST Verified",
                    description=f"GST {gst_number} verified successfully. Company Name: {customer.company_name}."
                )
            except Customer.DoesNotExist:
                pass
                
        elif company_id:
            try:
                company = Companies.objects.get(id=company_id)
                if gst_data.get('legal_name'):
                    company.name = gst_data['trade_name'] or gst_data['legal_name']
                if gst_data.get('city'):
                    company.city = gst_data['city']
                if gst_data.get('state'):
                    company.state = gst_data['state']
                if gst_data.get('pincode'):
                    try:
                        company.pincode = int(gst_data['pincode'])
                    except (ValueError, TypeError):
                        pass
                company.save()
            except Companies.DoesNotExist:
                pass
        
        html_response = f"""
        <div class="alert alert-success mt-2 mb-0 p-2">
            <h6 class="alert-heading fw-bold mb-1 text-success fs-10"><i class="fas fa-check-circle me-1"></i>GST Verified (UAT Registry)</h6>
            <ul class="list-unstyled mb-0 fs-10 text-success">
                <li><strong>Legal Name:</strong> {gst_data.get('legal_name')}</li>
                <li><strong>Trade Name:</strong> {gst_data.get('trade_name')}</li>
                <li><strong>Address:</strong> {gst_data.get('address')}</li>
                <li><strong>City/State/Pin:</strong> {gst_data.get('city')}, {gst_data.get('state')} - {gst_data.get('pincode')}</li>
            </ul>
        </div>
        """
        return HttpResponse(html_response)
    else:
        html_response = f"""
        <div class="alert alert-danger mt-2 mb-0 p-2">
            <h6 class="alert-heading fw-bold mb-1 text-danger fs-10"><i class="fas fa-times-circle me-1"></i>GST Verification Failed</h6>
            <p class="mb-0 fs-10 text-danger">The GST number "{gst_number}" could not be verified.</p>
        </div>
        """
        return HttpResponse(html_response)