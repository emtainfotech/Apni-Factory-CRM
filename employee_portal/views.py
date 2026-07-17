import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.urls import reverse

# Core and Auth Models
from authentication.models import User, Notification
from core.models import (
    Customer, Attendance, Break, CallLog, CustomerActivityLog,
    Invoice, InvoiceItem, Transaction, LeaveRequest
)
from core.forms import CustomerModalForm

# Hostinger Data Models
from hostinger_data.models import (
    Customers as HostingerCustomer, Orders as HostingerOrders,
    Orderdetail as HostingerOrderDetail, OrderTracks as HostingerOrderTrack,
    OrderStatus as HostingerOrderStatus, Categories as HostingerCategory,
    Brands as HostingerBrand, Products as HostingerProduct
)

# Core Views/Utils for Invoice Actions
from core.views import (
    finalize_invoice as core_finalize_invoice,
    download_invoice_pdf as core_download_invoice_pdf,
    send_invoice_email as core_send_invoice_email,
    send_invoice_whatsapp as core_send_invoice_whatsapp
)
from core.invoice_utils import calculate_gst_values, get_next_invoice_number

# ==========================================
#              DECORATORS
# ==========================================

def employee_required(view_func):
    """Restricts access to employees, managers, and superusers/admins only."""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or request.user.role in ['employee', 'manager', 'admin']:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Employee Portal.")
        return redirect('login')
    return _wrapped_view


def attendance_required(view_func):
    """
    Checks if employee has punched in for today before allowing dashboard actions.
    Admins/Superusers are exempted.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser or request.user.role == 'admin':
            return view_func(request, *args, **kwargs)
        
        today = timezone.now().date()
        attendance = Attendance.objects.filter(user=request.user, date=today, is_punched_in=True).first()
        
        if not attendance:
            messages.warning(request, "Please Punch-In to access this feature.")
            return redirect('employee_portal:dashboard')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ==========================================
#              UTILITY LOGIC
# ==========================================

def get_employee_remote_orders(employee):
    """
    Retrieves remote Hostinger Orders placed by customers assigned to the logged-in employee.
    Matches using customer mobile numbers, whatsapp numbers, or GSTINs.
    """
    assigned_customers = Customer.objects.filter(assigned_to=employee)
    phones = [c.phone for c in assigned_customers if c.phone]
    whatsapp_numbers = [c.whatsapp_number for c in assigned_customers if c.whatsapp_number]
    gst_numbers = [c.gst_number for c in assigned_customers if c.gst_number]
    
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
        return HostingerOrders.objects.using('hostinger_db').filter(customer_id__in=remote_cust_ids).order_by('-created_at')
    
    return HostingerOrders.objects.none()


def get_single_customer_remote_orders(customer):
    """Fetches remote Hostinger orders for a single customer by matching identifiers."""
    phones = [customer.phone] if customer.phone else []
    if customer.whatsapp_number:
        phones.append(customer.whatsapp_number)
    
    gst_numbers = [customer.gst_number] if customer.gst_number else []
    
    remote_cust_ids = []
    if phones or gst_numbers:
        q_filter = Q()
        if phones:
            q_filter |= Q(mobile__in=phones) | Q(whatsappno__in=phones)
        if gst_numbers:
            q_filter |= Q(gstorpan__in=gst_numbers)
            
        remote_cust_ids = list(
            HostingerCustomer.objects.using('hostinger_db')
            .filter(q_filter)
            .values_list('id', flat=True)
        )
        
    if remote_cust_ids:
        return HostingerOrders.objects.using('hostinger_db').filter(customer_id__in=remote_cust_ids).order_by('-created_at')
    
    return HostingerOrders.objects.none()

# ==========================================
#              CORE VIEWS
# ==========================================

@login_required
@employee_required
def dashboard(request):
    """Streamlined employee dashboard with attendance timeline and live e-commerce metrics."""
    today = timezone.now().date()
    attendance = Attendance.objects.filter(user=request.user, date=today).first()
    
    work_seconds = 0
    break_seconds = 0
    current_break_start = None
    
    if attendance and attendance.is_punched_in:
        now = timezone.now()
        total_duration = (now - attendance.punch_in).total_seconds()
        
        for b in attendance.breaks.all():
            if b.duration:
                break_seconds += b.duration.total_seconds()
            elif b.break_end is None:
                # Active break
                current_break_start = b.break_start.isoformat()
                break_seconds += (now - b.break_start).total_seconds()
                
        work_seconds = total_duration - break_seconds
    
    # Calculate stats for the employee
    assigned_leads = Customer.objects.filter(assigned_to=request.user, status='lead').count()
    active_customers = Customer.objects.filter(assigned_to=request.user, status='customer').count()
    today_calls = CallLog.objects.filter(employee=request.user, created_at__date=today).count()
    
    # Live E-commerce mapping statistics
    remote_orders = get_employee_remote_orders(request.user)
    
    # Sum total order business
    total_business = 0
    if remote_orders.exists():
        total_business = remote_orders.aggregate(total=Sum('grandtotal'))['total'] or 0
    
    context = {
        'attendance': attendance,
        'work_seconds': int(work_seconds),
        'break_seconds': int(break_seconds),
        'current_break_start': current_break_start,
        'assigned_leads': assigned_leads,
        'active_customers': active_customers,
        'today_calls': today_calls,
        'total_business': total_business,
        'recent_calls': CallLog.objects.filter(employee=request.user).order_by('-created_at')[:5],
        'recent_orders': remote_orders[:5] if remote_orders.exists() else [],
    }
    return render(request, 'employee_portal/dashboard.html', context)


@login_required
@employee_required
def attendance_history(request):
    """View historical attendance records for the logged-in employee."""
    attendance_qs = Attendance.objects.filter(user=request.user).order_by('-date', '-punch_in')
    paginator = Paginator(attendance_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'employee_portal/attendance_history.html', {'page_obj': page_obj})


@login_required
@employee_required
def punch_in(request):
    """Handles Punch In trigger with IP and User-Agent audit logging."""
    today = timezone.now().date()
    attendance, created = Attendance.objects.get_or_create(user=request.user, date=today)
    
    if not attendance.is_punched_in:
        now = timezone.now()
        attendance.punch_in = now
        attendance.is_punched_in = True
        
        # Extract IP Address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        attendance.ip_address = ip
        attendance.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Determine Late Status (Asia/Kolkata threshold: 09:30 AM IST)
        from zoneinfo import ZoneInfo
        kolkata_tz = ZoneInfo('Asia/Kolkata')
        local_time = timezone.now().astimezone(kolkata_tz)
        late_threshold = local_time.replace(hour=9, minute=30, second=0, microsecond=0)
        is_late = local_time > late_threshold
        attendance.is_late = is_late
        
        attendance.save()
        
        # Notify employee and admins
        if is_late:
            Notification.objects.create(
                recipient=request.user,
                message=f"Late punch-in recorded today at {local_time.strftime('%H:%M')} IST.",
                is_read=False
            )
            # Notify admins
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
            for admin in admins:
                Notification.objects.create(
                    recipient=admin,
                    message=f"Late Punch Alert: {request.user.username} punched in today at {local_time.strftime('%H:%M')} IST from IP {ip}.",
                    is_read=False
                )
                
        messages.success(request, "Punched-in successfully.")
    else:
        messages.info(request, "You are already punched-in.")
        
    return redirect(request.META.get('HTTP_REFERER', 'employee_portal:dashboard'))


@login_required
@employee_required
def punch_out(request):
    """Handles Punch Out trigger."""
    today = timezone.now().date()
    attendance = Attendance.objects.filter(user=request.user, date=today, is_punched_in=True).first()
    
    if attendance:
        now = timezone.now()
        attendance.punch_out = now
        attendance.is_punched_in = False
        
        # Calculate working hours (excluding breaks)
        if attendance.punch_in:
            work_duration = now - attendance.punch_in
            total_break = timedelta()
            for b in attendance.breaks.all():
                if b.duration:
                    total_break += b.duration
            
            attendance.total_working_hours = work_duration - total_break
            attendance.total_break_duration = total_break
            
        attendance.save()
        messages.success(request, "Punched-out successfully.")
    else:
        messages.error(request, "No active punch-in found for today.")
        
    return redirect(request.META.get('HTTP_REFERER', 'employee_portal:dashboard'))


@login_required
@employee_required
def toggle_break(request):
    """Starts or ends an attendance break."""
    today = timezone.now().date()
    attendance = Attendance.objects.filter(user=request.user, date=today, is_punched_in=True).first()
    
    if not attendance:
        messages.error(request, "Must be punched-in to take a break.")
        return redirect('employee_portal:dashboard')
        
    if not attendance.on_break:
        b_type = request.POST.get('break_type', 'short_break')
        Break.objects.create(attendance=attendance, break_type=b_type)
        attendance.on_break = True
        attendance.save()
        messages.info(request, f"Break ({b_type}) started.")
    else:
        latest_break = attendance.breaks.filter(break_end__isnull=True).last()
        if latest_break:
            now = timezone.now()
            latest_break.break_end = now
            latest_break.duration = now - latest_break.break_start
            latest_break.save()
            
        attendance.on_break = False
        attendance.save()
        messages.success(request, "Break ended. Back to work.")
        
    return redirect(request.META.get('HTTP_REFERER', 'employee_portal:dashboard'))


@login_required
@employee_required
def update_location(request):
    """AJAX endpoint for Live Tracker to ping current location."""
    if request.method == 'POST':
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        if lat and lng:
            today = timezone.now().date()
            attendance = Attendance.objects.filter(user=request.user, date=today, is_punched_in=True).first()
            if attendance:
                attendance.current_latitude = lat
                attendance.current_longitude = lng
                attendance.last_location_update = timezone.now()
                attendance.save()
                return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Invalid data or not punched in'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


# ==========================================
#           CUSTOMER MANAGEMENT
# ==========================================

@login_required
@employee_required
@attendance_required
def customer_list(request):
    """Lists only customers assigned to the logged-in employee."""
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    source_filter = request.GET.get('lead_source', '')
    
    qs = Customer.objects.filter(assigned_to=request.user).order_by('-created_at')
    
    if query:
        qs = qs.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(company_name__icontains=query)
        )
        
    if status_filter:
        qs = qs.filter(status=status_filter)
    if source_filter:
        qs = qs.filter(lead_source=source_filter)
        
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    existing_sources = list(Customer.objects.exclude(lead_source__isnull=True).exclude(lead_source='').values_list('lead_source', flat=True).distinct().order_by('lead_source'))
    source_choices = [(src, src.replace('_', ' ').title()) for src in existing_sources if src]

    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'source_filter': source_filter,
        'status_choices': Customer.STATUS_CHOICES,
        'source_choices': source_choices,
    }
    return render(request, 'employee_portal/customer_list.html', context)


@login_required
@employee_required
@attendance_required
def customer_detail(request, customer_id):
    """Comprehensive 360 view of a customer assigned to the employee."""
    customer = get_object_or_404(Customer, id=customer_id, assigned_to=request.user)
    from core.forms import CustomerEditForm
    
    if request.method == 'POST' and request.POST.get('action') == 'edit_customer':
        edit_form = CustomerEditForm(request.POST, instance=customer)
        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, "Buyer profile updated successfully.")
            return redirect('employee_portal:customer_detail', customer_id=customer.id)
        else:
            messages.error(request, "Failed to update buyer profile. Please check the errors.")
    else:
        edit_form = CustomerEditForm(instance=customer)
        
    # Fetch local records
    invoices = customer.invoices.all().order_by('-created_at')
    transactions = customer.transactions.all().order_by('-transaction_date')
    call_logs = customer.call_logs.all().order_by('-created_at')
    activities = customer.activities.all().order_by('-created_at')
    
    # Match remote Hostinger orders
    remote_orders = get_single_customer_remote_orders(customer)
    total_spent = sum(o.grandtotal for o in remote_orders) if remote_orders.exists() else 0
    
    context = {
        'customer': customer,
        'invoices': invoices,
        'transactions': transactions,
        'call_logs': call_logs,
        'activities': activities,
        'orders': remote_orders,
        'total_spent': total_spent,
        'edit_form': edit_form,
    }
    return render(request, 'employee_portal/customer_detail.html', context)


@login_required
@employee_required
@attendance_required
def log_call(request, customer_id):
    """Enables employees to log calls for their assigned customers."""
    customer = get_object_or_404(Customer, id=customer_id, assigned_to=request.user)
    
    if request.method == 'POST':
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
        
    return redirect('employee_portal:customer_detail', customer_id=customer_id)


@login_required
@employee_required
@attendance_required
def convert_lead(request, customer_id):
    """Converts a Lead status to Customer status."""
    customer = get_object_or_404(Customer, id=customer_id, assigned_to=request.user)
    
    if customer.status == 'lead':
        customer.status = 'customer'
        customer.save()
        
        CustomerActivityLog.objects.create(
            customer=customer,
            employee=request.user,
            action="Lead Converted",
            description="Status changed from Lead to Customer."
        )
        messages.success(request, f"{customer.first_name} converted to Customer.")
    else:
        messages.info(request, "Customer is already converted.")
        
    return redirect('employee_portal:customer_detail', customer_id=customer_id)

# ==========================================
#             ORDERS MANAGEMENT
# ==========================================

@login_required
@employee_required
@attendance_required
def order_list(request):
    """Lists remote orders from hostinger_db placed by assigned customers."""
    query = request.GET.get('q', '')
    
    remote_orders_qs = get_employee_remote_orders(request.user)
    
    if query and remote_orders_qs.exists():
        remote_orders_qs = remote_orders_qs.filter(
            Q(orderno__icontains=query) | Q(address__icontains=query)
        )
        
    paginator = Paginator(remote_orders_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Inject latest status dynamically
    for order in page_obj:
        latest_status = HostingerOrderStatus.objects.using('hostinger_db').filter(order_id=order.id).order_by('-created_at').first()
        order.current_status = latest_status.status if latest_status else "Pending"
        
        # Link back to local customer for templates
        # Match remote customer address or details to find local CRM customer
        order.crm_customer = None
        remote_cust = HostingerCustomer.objects.using('hostinger_db').filter(id=order.customer_id).first()
        if remote_cust:
            crm_cust = Customer.objects.filter(
                Q(phone=remote_cust.mobile) | Q(whatsapp_number=remote_cust.whatsappno)
            ).first()
            if crm_cust:
                order.crm_customer = crm_cust
                
    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'employee_portal/order_list.html', context)


@login_required
@employee_required
@attendance_required
def order_detail(request, order_id):
    """Displays detailed order information and item specs."""
    # Read-only order query
    order = get_object_or_404(HostingerOrders.objects.using('hostinger_db'), pk=order_id)
    
    # Safety Check: Verify order belongs to an assigned customer
    remote_cust = get_object_or_404(HostingerCustomer.objects.using('hostinger_db'), pk=order.customer_id)
    crm_cust = Customer.objects.filter(
        Q(phone=remote_cust.mobile) | Q(whatsapp_number=remote_cust.whatsappno)
    ).first()
    
    if not crm_cust or crm_cust.assigned_to != request.user:
        if not request.user.is_superuser and request.user.role != 'admin':
            messages.error(request, "Permission Denied: Order belongs to unassigned customer.")
            return redirect('employee_portal:order_list')
            
    # Gather remote details
    order_details = HostingerOrderDetail.objects.using('hostinger_db').filter(order_id=order_id)
    IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"
    
    for item in order_details:
        if item.attribute:
            try:
                item.parsed_attributes = json.loads(item.attribute)
            except Exception:
                item.parsed_attributes = None
        else:
            item.parsed_attributes = None
            
        # Enhance details with products
        product = HostingerProduct.objects.using('hostinger_db').filter(id=item.product_id).first()
        if product:
            item.product_obj = product
            item.product_image = f"{IMAGE_PREFIX}{product.image}" if product.image else None
            
    order_tracks = HostingerOrderTrack.objects.using('hostinger_db').filter(order_id=order_id).order_by('-created_at')
    order_statuses = HostingerOrderStatus.objects.using('hostinger_db').filter(order_id=order_id).order_by('-created_at')
    
    # Dynamic logistics timeline
    latest_status = order_statuses.first() if order_statuses.exists() else None
    latest_track = order_tracks.first() if order_tracks.exists() else None
    
    # Parse addresses & taxes
    address_data = None
    if order.address:
        try:
            address_data = json.loads(order.address)
        except Exception:
            address_data = None
            
    tax_details = None
    if order.taxdetail:
        try:
            tax_details = json.loads(order.taxdetail)
        except Exception:
            tax_details = None
            
    context = {
        'order': order,
        'order_details': order_details,
        'order_tracks': order_tracks,
        'order_statuses': order_statuses,
        'latest_status': latest_status,
        'latest_track': latest_track,
        'crm_customer': crm_cust,
        'address_data': address_data,
        'tax_details': tax_details,
    }
    return render(request, 'employee_portal/order_detail.html', context)

# ==========================================
#            INVOICES MANAGEMENT
# ==========================================

@login_required
@employee_required
@attendance_required
def invoice_list(request):
    """Lists local invoices generated by this employee."""
    # Fetch invoices belonging to assigned customers
    assigned_customers = Customer.objects.filter(assigned_to=request.user)
    invoices_qs = Invoice.objects.filter(
        Q(created_by=request.user) | Q(customer__in=assigned_customers)
    ).distinct().order_by('-created_at')
    
    paginator = Paginator(invoices_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'employee_portal/invoice_list.html', {'page_obj': page_obj})


@login_required
@employee_required
@attendance_required
def create_invoice(request):
    """Enables employees to generate invoices for their assigned customers."""
    assigned_customers = Customer.objects.filter(assigned_to=request.user)
    
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        supply_type = request.POST.get('supply_type', 'B2B')
        place_of_supply = request.POST.get('place_of_supply')
        reverse_charge = request.POST.get('reverse_charge') == 'on'
        payment_mode = request.POST.get('payment_mode')
        
        # Descriptions and Values
        descriptions = request.POST.getlist('description[]')
        sac_codes = request.POST.getlist('sac_code[]')
        taxable_values = request.POST.getlist('taxable_value[]')
        gst_rates = request.POST.getlist('gst_rate[]')
        
        customer = get_object_or_404(Customer, id=customer_id, assigned_to=request.user)
        
        # Financial Totals Accumulator
        total_taxable_value = 0
        total_gst = 0
        total_cgst = 0
        total_sgst = 0
        total_igst = 0
        total_amount = 0
        
        items_to_save = []
        
        for i in range(len(descriptions)):
            desc = descriptions[i]
            sac = sac_codes[i]
            val = float(taxable_values[i] or 0)
            rate = float(gst_rates[i] or 18.0)
            
            if not desc or val <= 0:
                continue
                
            # GST Computation (Intra-state state code = Delhi/etc vs Inter-state)
            cgst, sgst, igst, total_item_amount = calculate_gst_values(
                val, rate, place_of_supply, customer.state
            )
            
            total_taxable_value += val
            total_gst += (cgst + sgst + igst)
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            total_amount += total_item_amount
            
            items_to_save.append({
                'description': desc,
                'sac_code': sac,
                'taxable_value': val,
                'gst_rate': rate,
                'cgst': cgst,
                'sgst': sgst,
                'igst': igst,
                'total_amount': total_item_amount
            })
            
        if not items_to_save:
            messages.error(request, "Invoices must contain at least one item.")
            return redirect('employee_portal:create_invoice')
            
        invoice = Invoice.objects.create(
            invoice_no=get_next_invoice_number(),
            customer=customer,
            created_by=request.user,
            client_name=customer.company_name or f"{customer.first_name} {customer.last_name}",
            client_gstin=customer.gst_number,
            client_state_code=place_of_supply[:2] if place_of_supply else '07', # Delhi fallback
            place_of_supply=place_of_supply or 'Delhi',
            supply_type=supply_type,
            reverse_charge=reverse_charge,
            taxable_value=total_taxable_value,
            gst_total=total_gst,
            cgst=total_cgst,
            sgst=total_sgst,
            igst=total_igst,
            total_amount=total_amount,
            payment_mode=payment_mode,
            payment_status='pending',
            is_finalized=False
        )
        
        # Save invoice items
        for item in items_to_save:
            InvoiceItem.objects.create(
                invoice=invoice,
                description=item['description'],
                sac_code=item['sac_code'],
                taxable_value=item['taxable_value'],
                gst_rate=item['gst_rate'],
                cgst=item['cgst'],
                sgst=item['sgst'],
                igst=item['igst'],
                total_amount=item['total_amount']
            )
            
        messages.success(request, f"Invoice {invoice.invoice_no} drafted successfully.")
        return redirect('employee_portal:invoice_detail', invoice_id=invoice.id)
        
    context = {
        'customers': assigned_customers,
        'states': [
            'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
            'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
            'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
            'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
            'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
            'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Puducherry'
        ]
    }
    return render(request, 'employee_portal/invoice_form.html', context)


@login_required
@employee_required
@attendance_required
def invoice_detail(request, invoice_id):
    """Detailed view of an invoice."""
    assigned_customers = Customer.objects.filter(assigned_to=request.user)
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Safety Check: Verify invoice belongs to employee
    if invoice.created_by != request.user and invoice.customer not in assigned_customers:
        if not request.user.is_superuser and request.user.role != 'admin':
            messages.error(request, "Permission Denied: Invoice details restricted.")
            return redirect('employee_portal:invoice_list')
            
    return render(request, 'employee_portal/invoice_detail.html', {'invoice': invoice})

# ==========================================
#           INVOICE CORE REDIRECTS
# ==========================================

@login_required
@employee_required
def finalize_invoice(request, invoice_id):
    """Drafts invoice ledger credit/debit records via core view helper."""
    response = core_finalize_invoice(request, invoice_id)
    return redirect('employee_portal:invoice_detail', invoice_id=invoice_id)


@login_required
@employee_required
def download_invoice_pdf(request, invoice_id):
    """Downloads invoice PDF card."""
    return core_download_invoice_pdf(request, invoice_id)


@login_required
@employee_required
def send_invoice_email(request, invoice_id):
    """Sends invoices to the client's email."""
    core_send_invoice_email(request, invoice_id)
    return redirect('employee_portal:invoice_detail', invoice_id=invoice_id)


@login_required
@employee_required
def send_invoice_whatsapp(request, invoice_id):
    """Sends invoices to the client's whatsapp."""
    core_send_invoice_whatsapp(request, invoice_id)
    return redirect('employee_portal:invoice_detail', invoice_id=invoice_id)


@login_required
@employee_required
def apply_leave(request):
    """Enables employees to apply for sick, casual, or earned leave requests."""
    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        
        try:
            leave = LeaveRequest.objects.create(
                employee=request.user,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                status='pending'
            )
            
            # Notify admins of a new leave request
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
            for admin in admins:
                Notification.objects.create(
                    recipient=admin,
                    message=f"New Leave Request: {request.user.username} applied for {leave.get_leave_type_display()} from {start_date} to {end_date}.",
                    is_read=False
                )
                
            messages.success(request, "Leave request submitted successfully.")
        except Exception as e:
            messages.error(request, f"Failed to submit leave request: {e}")
            
        return redirect('employee_portal:apply_leave')
        
    leaves = LeaveRequest.objects.filter(employee=request.user).order_by('-created_at')
    return render(request, 'employee_portal/apply_leave.html', {'leaves': leaves})


@login_required
@employee_required
def lead_kanban(request):
    """Enables employees to view and manage their assigned leads in a Kanban column layout."""
    if request.method == 'POST':
        form = CustomerModalForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.assigned_to = request.user  # Auto-assign to self
            customer.save()
            messages.success(request, f"Lead {customer.first_name} manually added to your pipeline successfully.")
            return redirect('employee_portal:lead_kanban')
        else:
            messages.error(request, "Failed to create lead. Please check the form errors.")
    else:
        form = CustomerModalForm()
        
    # Gather only customers assigned to this employee
    customers = Customer.objects.filter(assigned_to=request.user).select_related('assigned_to')
    
    # Filter customers by column
    leads = customers.filter(status='lead')
    prospects = customers.filter(status='prospect')
    active_customers = customers.filter(status='customer')
    inactive = customers.filter(status='inactive')
    lost = customers.filter(status='lost')
    
    context = {
        'leads': leads,
        'prospects': prospects,
        'active_customers': active_customers,
        'inactive': inactive,
        'lost': lost,
        'form': form,
        'is_employee': True,
    }
    
    return render(request, 'employee_portal/lead_kanban.html', context)
