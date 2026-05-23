import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpResponse

# Import Models & Forms
from authentication.models import User, Notification
from authentication.tokens import account_activation_token
from .forms import UserInviteForm
from .models import Customer

# Import Hostinger Data Models
from hostinger_data.models import (
    Users as HostingerUser, Companies, Brands, Products, Orders,
    Wallet, Credits, Faqs, Pages, Tickets, ShadeCards,
    Advertisements, BankDetails, Admin as HostingerAdmin,
    Orderdetail, OrderTracks, OrderStatus, Categories, Sliders
)

# Import Invoice Utils & Models
from .models import Invoice, InvoiceItem, Order, OrderItem, Transaction
from .invoice_utils import calculate_gst_values, get_next_invoice_number

# ==========================================
#              HELPER FUNCTIONS
# ==========================================

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
    # Statistics from local DB
    total_customers = Customer.objects.count()
    total_invoices = Invoice.objects.count()
    
    # Statistics from External Hostinger DB
    total_hostinger_users = HostingerUser.objects.count()
    total_orders = Orders.objects.count()
    recent_orders = Orders.objects.all().order_by('-created_at')[:10]
    
    context = {
        'total_customers': total_customers,
        'total_invoices': total_invoices,
        'total_hostinger_users': total_hostinger_users,
        'total_orders': total_orders,
        'recent_orders': recent_orders,
        'recent_users': User.objects.order_by('-date_joined')[:5]
    }
    return render(request, 'core/dashboard_admin.html', context)

@login_required
@user_passes_test(is_manager)
def manager_dashboard(request):
    return render(request, 'core/dashboard_manager.html')

@login_required
@user_passes_test(is_employee)
def employee_dashboard(request):
    return render(request, 'core/dashboard_employee.html')

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
    query = request.GET.get('q')
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) | 
            Q(email__icontains=query) |
            Q(role__icontains=query)
        )

    # 2. Pagination
    paginator = Paginator(users_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 3. HTMX Navigation Fix
    is_htmx = request.headers.get('HX-Request') == 'true'
    target_id = request.headers.get('HX-Target')

    # Only return partial if specifically updating the table body
    if is_htmx and target_id == 'user-table-body':
        return render(request, 'core/partials/user_table_rows.html', {'page_obj': page_obj})

    # Otherwise return full page
    form = UserInviteForm()
    return render(request, 'core/user_list.html', {'page_obj': page_obj, 'form': form})


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
def user_detail(request, user_id):
    user_profile = get_object_or_404(User, pk=user_id)
    return render(request, 'core/user_detail.html', {'user_profile': user_profile})


@login_required
def customer_detail(request, customer_id):
    """
    360-degree view of a customer including orders, invoices, 
    whatsapp chats, and transactions.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Fetch related data with prefetching for performance
    orders = customer.orders.all().prefetch_related('status_history').order_by('-created_at')
    invoices = customer.invoices.all().order_by('-created_at')
    whatsapp_chats = customer.whatsapp_chats.all().order_by('-timestamp')
    transactions = customer.transactions.all().order_by('-transaction_date')
    activities = customer.activities.all().order_by('-created_at')
    
    context = {
        'customer': customer,
        'orders': orders,
        'invoices': invoices,
        'whatsapp_chats': whatsapp_chats,
        'transactions': transactions,
        'activities': activities,
        'total_spent': sum(o.total_amount for o in orders if o.status != 'cancelled'),
    }
    
    return render(request, 'core/customer_detail.html', context)

@login_required
def order_list(request):
    """Global list of all orders from Hostinger Database."""
    orders_qs = Orders.objects.all().order_by('-created_at')
    
    # Search logic
    query = request.GET.get('q')
    if query:
        orders_qs = orders_qs.filter(
            Q(orderno__icontains=query) | 
            Q(address__icontains=query)
        )
        
    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'core/order_list.html', {'page_obj': page_obj, 'query': query})

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
    
    # Get customer info from Hostinger
    h_user = get_object_or_404(HostingerUser, pk=order.user_id)
    h_company = Companies.objects.filter(user_id=order.user_id).first()
    
    # Parse address JSON
    address_data = {}
    if order.address:
        try:
            # Clean up potential string issues (like single quotes instead of double quotes)
            # though json.loads expects strict JSON.
            address_data = json.loads(order.address)
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON, we'll handle it as raw text in the template
            address_data = None
    
    # Parse tax details JSON
    tax_details = []
    if order.taxdetail:
        try:
            tax_details = json.loads(order.taxdetail)
        except (json.JSONDecodeError, TypeError):
            tax_details = None

    # Financials are directly on the 'order' object (Orders model)
    # Orderdetail model doesn't have financial fields
    items_count = order_details.count()
    
    context = {
        'order': order,
        'order_details': order_details,
        'order_tracks': order_tracks,
        'order_statuses': order_statuses,
        'h_user': h_user,
        'h_company': h_company,
        'address_data': address_data,
        'tax_details': tax_details,
        'items_count': items_count,
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

    # ... (Pagination logic remains same) ...
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    employees = User.objects.filter(is_active=True).exclude(is_superuser=True)

    context = {
        'customers': page_obj, 
        'modal_form': modal_form, # This now contains errors if POST failed
        'employees': employees,
        'query': query,
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
def hostinger_user_list(request):
    """
    Lists users from the external Hostinger database.
    """
    users_qs = HostingerUser.objects.all().order_by('-created_at')
    
    # Search logic
    query = request.GET.get('q')
    if query:
        users_qs = users_qs.filter(
            Q(name__icontains=query) | 
            Q(email__icontains=query)
        )

    # Include Admin details if requested (Addressing the "admin missing" part)
    # Since 'Admin' is a separate table, we might want to show it as well
    hostinger_admins = HostingerAdmin.objects.all()

    paginator = Paginator(users_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'hostinger_admins': hostinger_admins,
        'query': query,
    }

    return render(request, 'core/hostinger_user_list.html', context)


@login_required
@user_passes_test(is_admin)
def hostinger_user_detail(request, user_id):
    """
    Detailed view of a Hostinger user and all related data.
    """
    h_user = get_object_or_404(HostingerUser, pk=user_id)
    
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
    
    return render(request, 'core/hostinger_user_detail.html', context)


def hostinger_login(request):
    """
    Backend login view for Hostinger users.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password') # Note: In production, use proper password verification
        
        try:
            h_user = HostingerUser.objects.using('hostinger_db').get(email=email)
            # Simulating login by setting session variable
            request.session['hostinger_user_id'] = h_user.id
            request.session['hostinger_user_email'] = h_user.email
            messages.success(request, f"Successfully logged in as {h_user.name}")
            return redirect('hostinger_user_detail', user_id=h_user.id)
        except HostingerUser.DoesNotExist:
            messages.error(request, "Invalid email or password.")
            
    return render(request, 'core/hostinger_login.html')


@login_required
@user_passes_test(is_admin)
def banner_list(request):
    """View to show all active banners."""
    banners = Advertisements.objects.filter(status=1).order_by('sequence')
    
    # Prefix for images/files
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for banner in banners:
        banner.image_url = f"{IMAGE_PREFIX}{banner.file}" if banner.file else None
        
    context = {
        'banners': banners,
    }
    return render(request, 'core/banner_list.html', context)


@login_required
@user_passes_test(is_admin)
def slider_list(request):
    """View to show all active sliders."""
    sliders = Sliders.objects.filter(status=1).order_by('-created_at')
    
    # Prefix for images
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for slider in sliders:
        slider.image_url = f"{IMAGE_PREFIX}{slider.image}" if slider.image else None
        
    context = {
        'sliders': sliders,
    }
    return render(request, 'core/slider_list.html', context)


# ==========================================
#         INVOICE MANAGEMENT
# ==========================================

@login_required
def invoice_list(request):
    """Lists all invoices."""
    invoices = Invoice.objects.all().order_by('-created_at')
    
    # Search logic
    query = request.GET.get('q')
    if query:
        invoices = invoices.filter(
            Q(invoice_no__icontains=query) | 
            Q(client_name__icontains=query)
        )
        
    paginator = Paginator(invoices, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'core/invoice_list.html', {'page_obj': page_obj, 'query': query})

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