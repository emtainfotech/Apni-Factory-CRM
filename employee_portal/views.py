import json
from functools import wraps
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Max, Count, Avg, Min
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.urls import reverse

# Core and Auth Models
from authentication.models import User, Notification
from core.models import (
    Customer, Attendance, Break, CallLog, CustomerActivityLog,
    Invoice, InvoiceItem, Transaction, LeaveRequest, MissedPunchOutRecord
)
from core.forms import CustomerModalForm, EmployeeCustomerCreateForm

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
    """Restricts access to employees, managers, and superusers/admins only.
    Also blocks employees whose is_employee_active flag has been disabled by admin.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Admins / superusers are always allowed
        if request.user.is_superuser or request.user.role == 'admin':
            return view_func(request, *args, **kwargs)
        # Check valid role
        if request.user.role not in ['employee', 'manager']:
            messages.error(request, "Access restricted to Employee Portal.")
            return redirect('login')
        # Check admin-controlled active status
        if not getattr(request.user, 'is_employee_active', True):
            messages.error(
                request,
                "Your account has been deactivated. Please contact your administrator."
            )
            from django.contrib.auth import logout
            logout(request)
            return redirect('login')
        return view_func(request, *args, **kwargs)
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
    today = timezone.localdate()
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
    unassigned_leads_count = Customer.objects.filter(assigned_to__isnull=True).count()

    # 1. Today's Scheduled Follow-ups
    todays_followups = CallLog.objects.filter(
        Q(employee=request.user) | Q(customer__assigned_to=request.user),
        follow_up_date__date=today
    ).select_related('customer').order_by('follow_up_date')
    todays_followups_count = todays_followups.count()

    overdue_followups_count = CallLog.objects.filter(
        Q(employee=request.user) | Q(customer__assigned_to=request.user),
        follow_up_date__date__lt=today,
        follow_up_date__isnull=False
    ).count()

    # 2. Customers Connected by Employee (on basis of profile creation and profile changes/updates)
    created_cust_ids_today = set(Customer.objects.filter(
        created_by=request.user,
        created_at__date=today
    ).values_list('id', flat=True))

    updated_cust_ids_today = set(CustomerActivityLog.objects.filter(
        employee=request.user,
        created_at__date=today
    ).values_list('customer_id', flat=True))

    connected_today_cust_ids = created_cust_ids_today.union(updated_cust_ids_today)
    connected_today_count = len(connected_today_cust_ids)
    connected_today_created = len(created_cust_ids_today)
    connected_today_updated = len(updated_cust_ids_today)

    # Month figures
    created_cust_ids_month = set(Customer.objects.filter(
        created_by=request.user,
        created_at__year=today.year,
        created_at__month=today.month
    ).values_list('id', flat=True))

    updated_cust_ids_month = set(CustomerActivityLog.objects.filter(
        employee=request.user,
        created_at__year=today.year,
        created_at__month=today.month
    ).values_list('customer_id', flat=True))

    connected_month_count = len(created_cust_ids_month.union(updated_cust_ids_month))
    connected_month_created = len(created_cust_ids_month)
    connected_month_updated = len(updated_cust_ids_month)

    created_cust_ids_all = set(Customer.objects.filter(created_by=request.user).values_list('id', flat=True))
    updated_cust_ids_all = set(CustomerActivityLog.objects.filter(employee=request.user).values_list('customer_id', flat=True))
    connected_all_count = len(created_cust_ids_all.union(updated_cust_ids_all))

    # Recent customer connections / activity stream for this employee (last 6 items)
    recent_connection_logs = CustomerActivityLog.objects.filter(
        employee=request.user
    ).select_related('customer').order_by('-created_at')[:6]
    
    # Live E-commerce mapping statistics
    remote_orders = get_employee_remote_orders(request.user)
    
    # Sum total order business
    total_business = 0
    if remote_orders.exists():
        total_business = remote_orders.aggregate(total=Sum('grandtotal'))['total'] or 0
    
    existing_states = list(Customer.objects.exclude(state__isnull=True).exclude(state='').values_list('state', flat=True).distinct().order_by('state'))
    state_choices = [s for s in existing_states if s and s.strip()]
    create_customer_form = EmployeeCustomerCreateForm(initial={'country': 'India', 'lead_source': 'manual', 'status': 'lead', 'customer_type': 'buyer'})

    context = {
        'attendance': attendance,
        'work_seconds': int(work_seconds),
        'break_seconds': int(break_seconds),
        'current_break_start': current_break_start,
        'assigned_leads': assigned_leads,
        'active_customers': active_customers,
        'today_calls': today_calls,
        'unassigned_leads_count': unassigned_leads_count,
        'todays_followups': todays_followups,
        'todays_followups_count': todays_followups_count,
        'overdue_followups_count': overdue_followups_count,
        'connected_today_count': connected_today_count,
        'connected_today_created': connected_today_created,
        'connected_today_updated': connected_today_updated,
        'connected_month_count': connected_month_count,
        'connected_month_created': connected_month_created,
        'connected_month_updated': connected_month_updated,
        'connected_all_count': connected_all_count,
        'recent_connection_logs': recent_connection_logs,
        'total_business': total_business,
        'recent_calls': CallLog.objects.filter(employee=request.user).order_by('-created_at')[:5],
        'recent_orders': remote_orders[:5] if remote_orders.exists() else [],
        'create_customer_form': create_customer_form,
        'state_choices': state_choices,
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
    """Handles Punch In.
    Rules:
    - Blocked on Sundays (weekday() == 6)
    - If previous working day had no punch-out, redirect to missed-punchout form first
    - Records IP, user agent, and late status (threshold: 09:30 IST)
    """
    from zoneinfo import ZoneInfo
    kolkata_tz = ZoneInfo('Asia/Kolkata')
    now_local = timezone.now().astimezone(kolkata_tz)
    today = now_local.date()

    # --- Sunday Block ---
    if today.weekday() == 6:  # Sunday
        messages.error(request, "🚫 Today is Sunday — a weekly off. Punch-in is not allowed.")
        return redirect('employee_portal:dashboard')

    # --- Missed Punch-Out Check ---
    # Look for yesterday's (or most recent working day's) attendance with no punch-out
    yesterday = today - timedelta(days=1)
    # Skip Sunday when calculating previous working day
    if yesterday.weekday() == 6:
        yesterday = today - timedelta(days=2)

    missed_attendance = Attendance.objects.filter(
        user=request.user,
        date=yesterday,
        punch_in__isnull=False,
        punch_out__isnull=True,
    ).first()

    # Only block if we haven't already collected a missed-punchout record for that day
    already_reported = MissedPunchOutRecord.objects.filter(
        user=request.user, missed_date=yesterday
    ).exists()

    if missed_attendance and not already_reported:
        # Store context in session so the form knows which day to fix
        request.session['missed_punchout_date'] = str(yesterday)
        messages.warning(
            request,
            f"⚠️ You forgot to punch out on {yesterday.strftime('%d %b %Y')}. "
            "Please provide your exit time and reason before punching in today."
        )
        return redirect('employee_portal:missed_punchout_form')

    # --- Normal Punch In ---
    attendance, created = Attendance.objects.get_or_create(user=request.user, date=today)

    if not attendance.is_punched_in:
        now_utc = timezone.now()
        attendance.punch_in = now_utc
        attendance.is_punched_in = True
        attendance.status = 'present'

        # Extract IP Address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
        attendance.ip_address = ip
        attendance.user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Determine Late Status (threshold: 09:30 IST)
        late_threshold = now_local.replace(hour=9, minute=30, second=0, microsecond=0)
        is_late = now_local > late_threshold
        attendance.is_late = is_late
        attendance.save()

        if is_late:
            Notification.objects.create(
                recipient=request.user,
                message=f"⏰ Late punch-in recorded today at {now_local.strftime('%H:%M')} IST.",
            )
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
            for admin in admins:
                Notification.objects.create(
                    recipient=admin,
                    message=(
                        f"🔴 Late Punch Alert: {request.user.get_display_name()} punched in "
                        f"at {now_local.strftime('%H:%M')} IST from IP {ip}."
                    ),
                )

        messages.success(request, f"✅ Punched-in successfully at {now_local.strftime('%H:%M')} IST.")
    else:
        messages.info(request, "You are already punched-in.")

    return redirect(request.META.get('HTTP_REFERER', reverse('employee_portal:dashboard')))


@login_required
@employee_required
def missed_punchout_form(request):
    """Interstitial form: employee submits yesterday's exit time & reason before today's punch-in."""
    missed_date_str = request.session.get('missed_punchout_date')
    if not missed_date_str:
        return redirect('employee_portal:punch_in')

    from datetime import date as date_cls
    missed_date = date_cls.fromisoformat(missed_date_str)

    if request.method == 'POST':
        exit_time_str = request.POST.get('exit_time', '').strip()
        reason = request.POST.get('reason', '').strip()

        if not exit_time_str or not reason:
            messages.error(request, "Both exit time and reason are required.")
            return render(request, 'employee_portal/missed_punchout_form.html', {'missed_date': missed_date})

        try:
            from datetime import time as time_cls
            exit_time = time_cls.fromisoformat(exit_time_str)  # HH:MM
        except ValueError:
            messages.error(request, "Invalid time format. Use HH:MM.")
            return render(request, 'employee_portal/missed_punchout_form.html', {'missed_date': missed_date})

        # Save the missed punch-out record
        MissedPunchOutRecord.objects.create(
            user=request.user,
            missed_date=missed_date,
            reported_exit_time=exit_time,
            reason=reason,
        )

        # Retroactively update yesterday's Attendance record
        from zoneinfo import ZoneInfo
        kolkata_tz = ZoneInfo('Asia/Kolkata')
        missed_attendance = Attendance.objects.filter(
            user=request.user, date=missed_date, punch_out__isnull=True
        ).first()
        if missed_attendance and missed_attendance.punch_in:
            from datetime import datetime as dt_cls
            exit_dt_naive = dt_cls.combine(missed_date, exit_time)
            exit_dt = kolkata_tz.localize(exit_dt_naive)
            missed_attendance.punch_out = exit_dt
            missed_attendance.is_punched_in = False
            work_duration = exit_dt - missed_attendance.punch_in
            total_break = timedelta()
            for b in missed_attendance.breaks.all():
                if b.duration:
                    total_break += b.duration
            missed_attendance.total_working_hours = work_duration - total_break
            missed_attendance.total_break_duration = total_break
            missed_attendance.save()

        # Notify admins
        admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                message=(
                    f"📋 {request.user.get_display_name()} submitted a missed punch-out record for "
                    f"{missed_date.strftime('%d %b %Y')} — exit at {exit_time_str}."
                ),
            )

        # Clear session
        request.session.pop('missed_punchout_date', None)
        messages.success(
            request,
            f"✅ Missed punch-out for {missed_date.strftime('%d %b %Y')} recorded. You can now punch in."
        )
        return redirect('employee_portal:punch_in')

    return render(request, 'employee_portal/missed_punchout_form.html', {'missed_date': missed_date})


@login_required
@employee_required
def punch_out(request):
    """Handles Punch Out.
    Rules:
    - If hours worked < 8 AND no approved leave/half-day → require early punch-out approval from admin
    - If early_out_approval_status == 'pending' → block, show awaiting message
    - If early_out_approval_status == 'approved' OR hours >= 8 OR approved leave → allow punch-out
    """
    from zoneinfo import ZoneInfo
    kolkata_tz = ZoneInfo('Asia/Kolkata')
    today = timezone.now().astimezone(kolkata_tz).date()
    REQUIRED_HOURS = 8 * 3600  # 8 hours in seconds

    attendance = Attendance.objects.filter(user=request.user, date=today, is_punched_in=True).first()

    if not attendance:
        messages.error(request, "No active punch-in found for today.")
        return redirect(request.META.get('HTTP_REFERER', reverse('employee_portal:dashboard')))

    # Check for an approved leave/half-day for today
    approved_leave = LeaveRequest.objects.filter(
        employee=request.user,
        start_date__lte=today,
        end_date__gte=today,
        status='approved'
    ).first()
    required_seconds = REQUIRED_HOURS
    if approved_leave and approved_leave.is_half_day:
        required_seconds = 4 * 3600  # Half-day = 4h
    elif approved_leave:
        required_seconds = 0  # Full-day leave — no hour requirement

    worked_seconds = attendance.get_worked_seconds()
    hours_short = worked_seconds < required_seconds

    # Check early-out approval state
    if hours_short and required_seconds > 0:
        if attendance.early_out_approval_status == 'approved':
            # Admin has approved — allow punch-out
            pass
        elif attendance.early_out_approval_status == 'pending':
            messages.warning(
                request,
                "⏳ Your early punch-out request is awaiting admin approval. Please wait."
            )
            return redirect(request.META.get('HTTP_REFERER', reverse('employee_portal:dashboard')))
        else:
            # No request yet — redirect employee to submit one
            messages.warning(
                request,
                "⚠️ You have worked less than 8 hours. Please submit an early punch-out request for admin approval."
            )
            return redirect(request.META.get('HTTP_REFERER', reverse('employee_portal:dashboard')))

    # --- Finalise Punch Out ---
    now_utc = timezone.now()
    attendance.punch_out = now_utc
    attendance.is_punched_in = False

    if attendance.punch_in:
        work_duration = now_utc - attendance.punch_in
        total_break = timedelta()
        for b in attendance.breaks.all():
            if b.duration:
                total_break += b.duration
        attendance.total_working_hours = work_duration - total_break
        attendance.total_break_duration = total_break

    # Determine final status
    if approved_leave and approved_leave.is_half_day:
        attendance.status = 'half_day'
    else:
        attendance.status = 'present'

    attendance.save()
    messages.success(request, "✅ Punched-out successfully. Have a great evening!")
    return redirect(request.META.get('HTTP_REFERER', reverse('employee_portal:dashboard')))


@login_required
@employee_required
def request_early_punchout(request):
    """AJAX endpoint: employee submits reason for early punch-out.
    Admin is notified; punch-out is blocked until approval.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    from zoneinfo import ZoneInfo
    kolkata_tz = ZoneInfo('Asia/Kolkata')
    today = timezone.now().astimezone(kolkata_tz).date()

    attendance = Attendance.objects.filter(
        user=request.user, date=today, is_punched_in=True
    ).first()

    if not attendance:
        return JsonResponse({'status': 'error', 'message': 'No active punch-in found.'}, status=400)

    if attendance.early_out_approval_status in ('pending', 'approved'):
        return JsonResponse({
            'status': 'info',
            'message': f'Request already {attendance.early_out_approval_status}.'
        })

    reason = request.POST.get('reason', '').strip()
    if not reason:
        return JsonResponse({'status': 'error', 'message': 'Reason is required.'}, status=400)

    worked_hours = attendance.get_worked_seconds() / 3600
    attendance.early_out_reason = reason
    attendance.early_out_requested_at = timezone.now()
    attendance.early_out_approval_status = 'pending'
    attendance.save()

    # Notify all admins
    admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            message=(
                f"🚪 Early Punch-Out Request: {request.user.get_display_name()} wants to leave after "
                f"{worked_hours:.1f}h. Reason: {reason[:80]}{'…' if len(reason) > 80 else ''}"
            ),
            url=f'/admin-attendance/',
        )

    return JsonResponse({
        'status': 'success',
        'message': '✅ Early punch-out request submitted. Awaiting admin approval.'
    })


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
def add_customer(request):
    """
    Allows logged-in employees to create new Buyer or Seller leads directly.
    The lead is automatically attributed and assigned to the employee who added it
    with their login (created_by=request.user, assigned_to=request.user).
    """
    redirect_url = request.POST.get('next') or request.GET.get('next') or reverse('employee_portal:customer_list')

    if request.method == 'POST':
        form = EmployeeCustomerCreateForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.assigned_to = request.user
            customer.save()

            # Audit activity
            CustomerActivityLog.objects.create(
                customer=customer,
                employee=request.user,
                action='Lead Created',
                description=f"Created as {customer.get_customer_type_display()} by {request.user.username} via Employee Portal and assigned to their personal pipeline."
            )

            party_label = "Buyer / Contractor" if customer.customer_type == 'buyer' else "Customer / Seller / Vendor"
            display_name = customer.first_name or customer.company_name or customer.phone
            messages.success(
                request,
                f"🎉 Successfully added new {party_label} '{display_name}' ({customer.phone})! The lead has been automatically assigned to your pipeline."
            )
            return redirect(redirect_url)
        else:
            error_msgs = []
            for field, errors in form.errors.items():
                for err in errors:
                    error_msgs.append(f"{field.replace('_', ' ').title()}: {err}")

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'errors': form.errors, 'message': "; ".join(error_msgs)}, status=400)

            for msg in error_msgs:
                messages.error(request, msg)

            if request.POST.get('from_modal') == '1':
                return redirect(redirect_url)

            existing_states = list(Customer.objects.exclude(state__isnull=True).exclude(state='').values_list('state', flat=True).distinct().order_by('state'))
            state_choices = [s for s in existing_states if s and s.strip()]
            return render(request, 'employee_portal/add_customer.html', {
                'form': form,
                'state_choices': state_choices,
                'next': redirect_url
            })

    # GET request - Full page add customer form
    initial_type = request.GET.get('type', 'seller')
    form = EmployeeCustomerCreateForm(initial={
        'customer_type': initial_type,
        'country': 'India',
        'status': 'lead',
        'lead_source': 'manual',
    })
    existing_states = list(Customer.objects.exclude(state__isnull=True).exclude(state='').values_list('state', flat=True).distinct().order_by('state'))
    state_choices = [s for s in existing_states if s and s.strip()]
    return render(request, 'employee_portal/add_customer.html', {
        'form': form,
        'state_choices': state_choices,
        'next': redirect_url,
        'initial_type': initial_type
    })


@login_required
@employee_required
def check_customer_duplicate(request):
    """
    Checks if a customer/lead with the given mobile number already exists in the CRM.
    Returns existing details for popup with direct profile redirect and skip options.
    """
    phone_query = request.GET.get('phone', '').strip()
    if not phone_query:
        return JsonResponse({'exists': False})

    import re
    from zoneinfo import ZoneInfo
    clean_digits = re.sub(r'\D', '', phone_query)
    phone10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits

    if len(phone10) < 10:
        return JsonResponse({'exists': False})

    existing = Customer.objects.filter(
        Q(phone__endswith=phone10) | Q(whatsapp_number__endswith=phone10)
    ).select_related('assigned_to', 'created_by').first()

    if not existing:
        return JsonResponse({'exists': False})

    assigned_name = 'Unassigned'
    if existing.assigned_to:
        assigned_name = existing.assigned_to.get_full_name() or existing.assigned_to.username

    created_by_name = 'N/A'
    if existing.created_by:
        created_by_name = existing.created_by.get_full_name() or existing.created_by.username

    ist_tz = ZoneInfo("Asia/Kolkata")
    created_at_str = ''
    if existing.created_at:
        created_at_str = existing.created_at.astimezone(ist_tz).strftime('%d %b %Y, %I:%M %p')

    full_name = f"{existing.first_name or ''} {existing.last_name or ''}".strip()
    display_name = full_name or existing.company_name or existing.phone

    profile_url = reverse('employee_portal:customer_detail', kwargs={'customer_id': existing.id})

    return JsonResponse({
        'exists': True,
        'customer': {
            'id': existing.id,
            'name': display_name,
            'first_name': existing.first_name or '',
            'last_name': existing.last_name or '',
            'company_name': existing.company_name or '',
            'customer_type': existing.customer_type,
            'customer_type_display': existing.get_customer_type_display(),
            'phone': existing.phone,
            'whatsapp_number': existing.whatsapp_number or '',
            'email': existing.email or '',
            'city': existing.city or '',
            'state': existing.state or '',
            'status': existing.get_status_display() if hasattr(existing, 'get_status_display') else existing.status,
            'lead_source': existing.get_lead_source_display() if hasattr(existing, 'get_lead_source_display') else existing.lead_source,
            'assigned_to': assigned_name,
            'created_by': created_by_name,
            'created_at': created_at_str,
            'profile_url': profile_url,
        }
    })


@login_required
@employee_required
@attendance_required
def customer_list(request):
    """
    Lists customers for employee with full location filtering (state, city, pincode),
    dynamic page sizing, and easy assignment/claiming of unassigned leads.
    """
    # 1. Handle Claiming / Assignment actions
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'claim_single':
            customer_id = request.POST.get('customer_id')
            customer = Customer.objects.filter(id=customer_id, assigned_to__isnull=True).first()
            if customer:
                customer.assigned_to = request.user
                customer.save()
                messages.success(request, f"Lead #{customer.id} ({customer.first_name or customer.phone}) successfully claimed and assigned to you!")
            else:
                messages.error(request, "This lead is already assigned or could not be found.")
            referer = request.META.get('HTTP_REFERER')
            return redirect(referer or 'employee_portal:customer_list')

        elif action in ('bulk_claim', 'bulk_assign'):
            customer_ids = request.POST.getlist('selected_customers')
            if customer_ids:
                target_user = request.user
                assign_to_id = request.POST.get('assign_to_user')
                if assign_to_id and (request.user.role in ['manager', 'admin'] or request.user.is_superuser):
                    try:
                        target_user = User.objects.get(id=assign_to_id)
                    except User.DoesNotExist:
                        target_user = request.user

                updated_count = Customer.objects.filter(id__in=customer_ids).update(assigned_to=target_user)
                messages.success(request, f"Successfully assigned {updated_count} contact(s) to {target_user.username}!")
            else:
                messages.warning(request, "No contacts selected.")
            referer = request.META.get('HTTP_REFERER')
            return redirect(referer or 'employee_portal:customer_list')

    # 2. Assignment Scope Filter
    assigned_filter = request.GET.get('assigned_to', 'my').strip()
    if assigned_filter == 'unassigned':
        qs = Customer.objects.filter(assigned_to__isnull=True).order_by('-created_at')
    elif assigned_filter == 'all' and (request.user.role in ['manager', 'admin'] or request.user.is_superuser):
        qs = Customer.objects.all().order_by('-created_at')
    else:
        assigned_filter = 'my'
        qs = Customer.objects.filter(Q(assigned_to=request.user) | Q(created_by=request.user)).order_by('-created_at')

    # 3. Filters
    customer_type_filter = request.GET.get('customer_type', '').strip()
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    source_filter = request.GET.get('lead_source', '').strip()
    state_filter = request.GET.get('state', '').strip()
    city_filter = request.GET.get('city', '').strip()
    pincode_filter = request.GET.get('pincode', '').strip()

    if customer_type_filter in ('buyer', 'seller'):
        qs = qs.filter(customer_type=customer_type_filter)

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
    if state_filter:
        qs = qs.filter(state__icontains=state_filter)
    if city_filter:
        qs = qs.filter(city__icontains=city_filter)
    if pincode_filter:
        qs = qs.filter(pincode__icontains=pincode_filter)

    # 4. Filtered Count
    total_filtered_count = qs.count()

    # Quick Summary Counts
    my_total_count = Customer.objects.filter(Q(assigned_to=request.user) | Q(created_by=request.user)).count()
    unassigned_total_count = Customer.objects.filter(assigned_to__isnull=True).count()
    my_buyers_count = Customer.objects.filter(Q(assigned_to=request.user) | Q(created_by=request.user), customer_type='buyer').count()
    my_sellers_count = Customer.objects.filter(Q(assigned_to=request.user) | Q(created_by=request.user), customer_type='seller').count()
    unassigned_buyers_count = Customer.objects.filter(assigned_to__isnull=True, customer_type='buyer').count()
    unassigned_sellers_count = Customer.objects.filter(assigned_to__isnull=True, customer_type='seller').count()

    # 5. Dynamic Page Size
    per_page_str = request.GET.get('per_page', '25')
    try:
        per_page = int(per_page_str)
        if per_page not in [10, 15, 25, 50, 100, 250]:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    existing_sources = list(Customer.objects.exclude(lead_source__isnull=True).exclude(lead_source='').values_list('lead_source', flat=True).distinct().order_by('lead_source'))
    source_choices = [(src, src.replace('_', ' ').title()) for src in existing_sources if src]

    existing_states = list(Customer.objects.exclude(state__isnull=True).exclude(state='').values_list('state', flat=True).distinct().order_by('state'))
    state_choices = [s for s in existing_states if s and s.strip()]

    employees = None
    if request.user.role in ['manager', 'admin'] or request.user.is_superuser:
        employees = User.objects.filter(is_active=True).exclude(is_superuser=True)

    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'source_filter': source_filter,
        'state_filter': state_filter,
        'city_filter': city_filter,
        'pincode_filter': pincode_filter,
        'current_customer_type': customer_type_filter,
        'assigned_filter': assigned_filter,
        'per_page': per_page,
        'total_filtered_count': total_filtered_count,
        'my_total_count': my_total_count,
        'unassigned_total_count': unassigned_total_count,
        'my_buyers_count': my_buyers_count,
        'my_sellers_count': my_sellers_count,
        'unassigned_buyers_count': unassigned_buyers_count,
        'unassigned_sellers_count': unassigned_sellers_count,
        'status_choices': Customer.STATUS_CHOICES,
        'source_choices': source_choices,
        'state_choices': state_choices,
        'employees': employees,
        'create_customer_form': EmployeeCustomerCreateForm(initial={'country': 'India', 'lead_source': 'manual', 'status': 'lead', 'customer_type': 'buyer'}),
    }
    return render(request, 'employee_portal/customer_list.html', context)


@login_required
@employee_required
@attendance_required
def territory_directory(request):
    """
    Regional Market Directory for Employees:
    Displays combined Buyer and Seller figures by State, City, and Pin Code across the market.
    Enables employees to check market figures for any territory they are contacting,
    view registered contacts, and claim unassigned buyer/seller leads to their pipeline.
    """
    # 1. Handle Claiming / Assignment actions
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'claim_single':
            customer_id = request.POST.get('customer_id')
            customer = Customer.objects.filter(id=customer_id, assigned_to__isnull=True).first()
            if customer:
                customer.assigned_to = request.user
                customer.save()
                messages.success(request, f"Lead #{customer.id} ({customer.first_name or customer.phone}) successfully claimed and assigned to your pipeline!")
            else:
                messages.error(request, "This lead is already assigned or not found.")
            return redirect(request.META.get('HTTP_REFERER') or 'employee_portal:territory_directory')

        elif action in ('bulk_claim', 'bulk_assign'):
            customer_ids = request.POST.getlist('selected_customers')
            if customer_ids:
                target_user = request.user
                assign_to_id = request.POST.get('assign_to_user')
                if assign_to_id and (request.user.role in ['manager', 'admin'] or request.user.is_superuser):
                    try:
                        target_user = User.objects.get(id=assign_to_id)
                    except User.DoesNotExist:
                        target_user = request.user

                updated_count = Customer.objects.filter(id__in=customer_ids).update(assigned_to=target_user)
                messages.success(request, f"Successfully assigned {updated_count} contact(s) to {target_user.username}!")
            else:
                messages.warning(request, "No contacts selected.")
            return redirect(request.META.get('HTTP_REFERER') or 'employee_portal:territory_directory')

    # Query Params
    search_query = request.GET.get('q', '').strip()
    selected_state = request.GET.get('state', '').strip()
    selected_city = request.GET.get('city', '').strip()
    selected_pincode = request.GET.get('pincode', '').strip()
    active_tab = request.GET.get('tab', 'states').strip()
    selected_type = request.GET.get('customer_type', '').strip()

    # Base contacts queryset
    contacts_qs = Customer.objects.select_related('assigned_to').all().order_by('-created_at')

    if search_query:
        contacts_qs = contacts_qs.filter(
            Q(state__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(pincode__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(company_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    if selected_state:
        contacts_qs = contacts_qs.filter(state__icontains=selected_state)
    if selected_city:
        contacts_qs = contacts_qs.filter(city__icontains=selected_city)
    if selected_pincode:
        contacts_qs = contacts_qs.filter(pincode__icontains=selected_pincode)
    if selected_type in ('buyer', 'seller'):
        contacts_qs = contacts_qs.filter(customer_type=selected_type)

    # 1. State-level Figures
    state_qs = Customer.objects.exclude(state__isnull=True).exclude(state='')
    if search_query:
        state_qs = state_qs.filter(Q(state__icontains=search_query) | Q(city__icontains=search_query) | Q(pincode__icontains=search_query))

    state_figures = list(state_qs.values('state').annotate(
        total=Count('id'),
        buyers=Count('id', filter=Q(customer_type='buyer')),
        sellers=Count('id', filter=Q(customer_type='seller')),
        my_assigned=Count('id', filter=Q(assigned_to=request.user)),
        unassigned=Count('id', filter=Q(assigned_to__isnull=True))
    ).order_by('-total')[:100])

    for item in state_figures:
        tot = item['total'] or 1
        item['buyer_pct'] = round((item['buyers'] / tot) * 100, 1)
        item['seller_pct'] = round((item['sellers'] / tot) * 100, 1)

    # 2. City-level Figures
    city_qs = Customer.objects.exclude(city__isnull=True).exclude(city='')
    if search_query:
        city_qs = city_qs.filter(Q(city__icontains=search_query) | Q(state__icontains=search_query) | Q(pincode__icontains=search_query))
    if selected_state:
        city_qs = city_qs.filter(state__icontains=selected_state)

    city_figures = list(city_qs.values('city', 'state').annotate(
        total=Count('id'),
        buyers=Count('id', filter=Q(customer_type='buyer')),
        sellers=Count('id', filter=Q(customer_type='seller')),
        my_assigned=Count('id', filter=Q(assigned_to=request.user)),
        unassigned=Count('id', filter=Q(assigned_to__isnull=True))
    ).order_by('-total')[:150])

    for item in city_figures:
        tot = item['total'] or 1
        item['buyer_pct'] = round((item['buyers'] / tot) * 100, 1)
        item['seller_pct'] = round((item['sellers'] / tot) * 100, 1)

    # 3. Pincode-level Figures
    pin_qs = Customer.objects.exclude(pincode__isnull=True).exclude(pincode='')
    if search_query:
        pin_qs = pin_qs.filter(Q(pincode__icontains=search_query) | Q(city__icontains=search_query) | Q(state__icontains=search_query))
    if selected_state:
        pin_qs = pin_qs.filter(state__icontains=selected_state)
    if selected_city:
        pin_qs = pin_qs.filter(city__icontains=selected_city)

    pincode_figures = list(pin_qs.values('pincode', 'city', 'state').annotate(
        total=Count('id'),
        buyers=Count('id', filter=Q(customer_type='buyer')),
        sellers=Count('id', filter=Q(customer_type='seller')),
        my_assigned=Count('id', filter=Q(assigned_to=request.user)),
        unassigned=Count('id', filter=Q(assigned_to__isnull=True))
    ).order_by('-total')[:150])

    for item in pincode_figures:
        tot = item['total'] or 1
        item['buyer_pct'] = round((item['buyers'] / tot) * 100, 1)
        item['seller_pct'] = round((item['sellers'] / tot) * 100, 1)

    # 4. Overall KPIs
    total_states_count = Customer.objects.exclude(state__isnull=True).exclude(state='').values('state').distinct().count()
    total_cities_count = Customer.objects.exclude(city__isnull=True).exclude(city='').values('city').distinct().count()
    total_pincodes_count = Customer.objects.exclude(pincode__isnull=True).exclude(pincode='').values('pincode').distinct().count()
    total_buyers_count = Customer.objects.filter(customer_type='buyer').count()
    total_sellers_count = Customer.objects.filter(customer_type='seller').count()
    total_unassigned_count = Customer.objects.filter(assigned_to__isnull=True).count()
    my_assigned_total = Customer.objects.filter(assigned_to=request.user).count()

    # Pagination for contacts table
    paginator = Paginator(contacts_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    employees = None
    if request.user.role in ['manager', 'admin'] or request.user.is_superuser:
        employees = User.objects.filter(is_active=True).exclude(is_superuser=True)

    existing_states = list(Customer.objects.exclude(state__isnull=True).exclude(state='').values_list('state', flat=True).distinct().order_by('state'))

    context = {
        'state_figures': state_figures,
        'city_figures': city_figures,
        'pincode_figures': pincode_figures,
        'contacts': page_obj,
        'total_filtered_contacts': contacts_qs.count(),
        'total_states_count': total_states_count,
        'total_cities_count': total_cities_count,
        'total_pincodes_count': total_pincodes_count,
        'total_buyers_count': total_buyers_count,
        'total_sellers_count': total_sellers_count,
        'total_unassigned_count': total_unassigned_count,
        'my_assigned_total': my_assigned_total,
        'search_query': search_query,
        'selected_state': selected_state,
        'selected_city': selected_city,
        'selected_pincode': selected_pincode,
        'selected_type': selected_type,
        'active_tab': active_tab,
        'employees': employees,
        'existing_states': existing_states,
    }
    return render(request, 'employee_portal/territory_directory.html', context)


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
            updated_cust = edit_form.save()
            party_lbl = updated_cust.get_customer_type_display()
            CustomerActivityLog.objects.create(
                customer=updated_cust,
                employee=request.user,
                action="Profile Updated",
                description=f"{party_lbl} profile details updated by {request.user.username}."
            )
            messages.success(request, f"{party_lbl} profile updated successfully.")
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
    """Converts a Lead status to Customer status or switches party type between Buyer and Seller."""
    if request.user.is_superuser or request.user.role == 'admin':
        customer = get_object_or_404(Customer, id=customer_id)
    else:
        customer = get_object_or_404(
            Customer,
            Q(id=customer_id) & (Q(assigned_to=request.user) | Q(created_by=request.user))
        )
    
    target_type = request.POST.get('target_type') or request.GET.get('target_type')
    target_status = request.POST.get('target_status') or request.GET.get('target_status')
    
    if target_type in ('buyer', 'seller'):
        customer.customer_type = target_type
        customer.save()
        type_label = "Buyer / Contractor" if target_type == 'buyer' else "Customer / Seller / Vendor"
        CustomerActivityLog.objects.create(
            customer=customer,
            employee=request.user,
            action="Classification Changed",
            description=f"Account classified as {type_label}."
        )
        messages.success(request, f"{customer.first_name} classification updated to {type_label}.")
        return redirect('employee_portal:customer_detail', customer_id=customer_id)
        
    if target_status == 'customer' or customer.status == 'lead' or customer.status == 'prospect':
        customer.status = 'customer'
        customer.save()
        type_label = customer.get_customer_type_display()
        CustomerActivityLog.objects.create(
            customer=customer,
            employee=request.user,
            action="Lead Converted",
            description=f"Status changed to Active {type_label}."
        )
        messages.success(request, f"{customer.first_name} converted to Active {type_label} successfully!")
    else:
        messages.info(request, "Account is already active.")
        
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


# ==============================================================================
# VENDOR SEARCH & SYNC (GOOGLE PLACES & OSM) - EMPLOYEE SCOPED
# ==============================================================================
from vendor_network.models import VendorProfile
from vendor_network.services.google_places_fetcher import fetch_and_save_google_places
from core.models import WhatsAppChat, WhatsAppLead

@login_required
@employee_required
def vendor_search(request):
    """
    Allows employees to search places using Google Places API (or OSM)
    and sync them as Buyer/Contractor or Seller/Vendor directly into CRM.
    Displays only records searched/synced by this employee.
    """
    my_vendors = VendorProfile.objects.filter(
        Q(created_by=request.user) | Q(assigned_to=request.user)
    ).order_by('-updated_at')[:50]

    status_msg = None
    message = None
    synced_count = None

    if request.method == 'POST':
        query = request.POST.get('search_query', '').strip()
        party_type = request.POST.get('party_type', 'SELLER').upper()
        if party_type not in ('SELLER', 'BUYER'):
            party_type = 'SELLER'

        if query:
            res = fetch_and_save_google_places(query=query, user=request.user, party_type=party_type)
            status_msg = res.get('status')
            synced_count = res.get('synced_count', 0)
            if status_msg == 'success':
                party_label = "Buyers / Contractors" if party_type == 'BUYER' else "Sellers / Vendors"
                message = f"Found and synced {synced_count} {party_label} for '{query}' successfully!"
                messages.success(request, message)
            else:
                message = res.get('message', 'Failed to fetch places.')
                messages.error(request, message)

            # Refresh list
            my_vendors = VendorProfile.objects.filter(
                Q(created_by=request.user) | Q(assigned_to=request.user)
            ).order_by('-updated_at')[:50]
        else:
            messages.warning(request, "Please enter a location or business name to search.")

    return render(request, 'employee_portal/vendor_search.html', {
        'vendors': my_vendors,
        'status_msg': status_msg,
        'message': message,
        'synced_count': synced_count,
    })


@login_required
@employee_required
def vendor_directory(request):
    """
    Directory of all vendors and buyers searched/assigned to the logged-in employee.
    Filterable by Party Type (All, Buyers, Sellers), Category, City, Status, and Search text.
    """
    party_type = request.GET.get('party_type', '').upper()
    category = request.GET.get('category', '')
    city = request.GET.get('city', '')
    status = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    qs = VendorProfile.objects.filter(
        Q(created_by=request.user) | Q(assigned_to=request.user)
    ).order_by('-updated_at')

    if party_type in ('SELLER', 'BUYER'):
        qs = qs.filter(party_type=party_type)
    if category:
        qs = qs.filter(category__iexact=category)
    if city:
        qs = qs.filter(city__icontains=city)
    if status:
        qs = qs.filter(enrichment_status=status)
    if query:
        qs = qs.filter(
            Q(store_name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(mobile_number__icontains=query) |
            Q(street_address__icontains=query) |
            Q(city__icontains=query)
        )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Filter dropdown options (scoped to this employee's data)
    my_categories = VendorProfile.objects.filter(
        Q(created_by=request.user) | Q(assigned_to=request.user)
    ).exclude(category__isnull=True).exclude(category='').values_list('category', flat=True).distinct().order_by('category')

    my_cities = VendorProfile.objects.filter(
        Q(created_by=request.user) | Q(assigned_to=request.user)
    ).exclude(city__isnull=True).exclude(city='').values_list('city', flat=True).distinct().order_by('city')

    # Total counts for tabs
    total_all = VendorProfile.objects.filter(Q(created_by=request.user) | Q(assigned_to=request.user)).count()
    total_buyers = VendorProfile.objects.filter(Q(created_by=request.user) | Q(assigned_to=request.user), party_type='BUYER').count()
    total_sellers = VendorProfile.objects.filter(Q(created_by=request.user) | Q(assigned_to=request.user), party_type='SELLER').count()

    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']

    return render(request, 'employee_portal/vendor_directory.html', {
        'page_obj': page_obj,
        'vendors': page_obj,
        'all_categories': my_categories,
        'all_cities': my_cities,
        'total_all': total_all,
        'total_buyers': total_buyers,
        'total_sellers': total_sellers,
        'current_party_type': party_type,
        'current_category': category,
        'current_city': city,
        'current_status': status,
        'current_query': query,
        'query_string': query_params.urlencode(),
    })


@login_required
@employee_required
def convert_vendor_to_customer(request, vendor_id):
    """
    Converts a searched Vendor/Buyer into an official Customer/Buyer lead in the employee's CRM pipeline.
    Allows passing ?target_type=buyer or ?target_type=seller.
    """
    vendor = get_object_or_404(VendorProfile, id=vendor_id)
    phone = vendor.mobile_number or vendor.phone_number or ''

    requested_type = request.GET.get('target_type') or request.POST.get('target_type')
    if requested_type in ('buyer', 'seller'):
        cust_type = requested_type
    else:
        cust_type = 'seller' if vendor.party_type == 'SELLER' else 'buyer'

    if phone:
        existing = Customer.objects.filter(phone=phone).first()
        if existing:
            messages.info(request, f"Contact with phone {phone} already exists as '{existing.first_name}'.")
            return redirect('employee_portal:customer_detail', customer_id=existing.id)

    new_cust = Customer.objects.create(
        first_name=vendor.store_name,
        phone=phone or f"TEMP_{vendor.id}",
        email=vendor.email_address or None,
        company_name=vendor.store_name,
        address=vendor.street_address or '',
        city=vendor.city or '',
        state=vendor.state or '',
        pincode=vendor.pincode or '',
        customer_type=cust_type,
        lead_source='manual',
        status='lead',
        assigned_to=request.user,
        created_by=request.user,
        notes=f"Converted from {vendor.get_party_type_display()} search on {timezone.localdate().strftime('%d %b %Y')}. Category: {vendor.category or 'N/A'}"
    )

    vendor.enrichment_status = 'CONVERTED'
    vendor.save()

    messages.success(request, f"Successfully converted '{vendor.store_name}' into a {cust_type.title()} lead!")
    return redirect('employee_portal:customer_detail', customer_id=new_cust.id)


from django.views.decorators.csrf import csrf_exempt

# ==============================================================================
# WHATSAPP INBOX - EMPLOYEE SCOPED
# ==============================================================================
@login_required
@employee_required
def whatsapp_inbox(request):
    """
    Dedicated WhatsApp Inbox for employees.
    Strictly isolated: Displays only assigned/created customers and buyers.
    Filterable by Party Type (All, Buyers, Sellers) and customer search.
    """
    party_type = request.GET.get('party_type', '').lower()
    query = request.GET.get('q', '').strip()
    active_cust_id = request.GET.get('customer_id', '').strip()

    if active_cust_id and active_cust_id.isdigit():
        target_cust = Customer.objects.filter(id=active_cust_id).first()
        if target_cust and target_cust.assigned_to is None:
            target_cust.assigned_to = request.user
            target_cust.save(update_fields=['assigned_to'])

    # Scope to this employee
    from core.models import WhatsAppMessageStatus

    failed_wamids = list(WhatsAppMessageStatus.objects.filter(status='failed').values_list('wamid', flat=True))
    failed_phones = list(WhatsAppMessageStatus.objects.filter(status='failed').values_list('recipient_id', flat=True))
    
    failed_chat_filter = (
        Q(whatsapp_chats__direction='outgoing', whatsapp_chats__wamid__isnull=True) |
        Q(whatsapp_chats__direction='outgoing', whatsapp_chats__wamid='') |
        (Q(whatsapp_chats__direction='outgoing', whatsapp_chats__wamid__in=failed_wamids) if failed_wamids else Q(pk__in=[])) |
        (Q(phone__in=failed_phones) | Q(whatsapp_number__in=failed_phones) if failed_phones else Q(pk__in=[]))
    )

    qs = Customer.objects.filter(
        Q(assigned_to=request.user) | Q(created_by=request.user) | (Q(id=active_cust_id) if active_cust_id and active_cust_id.isdigit() else Q(pk__in=[]))
    ).annotate(
        last_chat_time=Max('whatsapp_chats__timestamp')
    ).distinct().order_by('-last_chat_time', '-updated_at')

    if party_type in ('buyer', 'seller'):
        qs = qs.filter(customer_type=party_type)
    elif party_type in ('failed', 'unsent'):
        qs = qs.filter(failed_chat_filter)

    if query:
        qs = qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(company_name__icontains=query)
        )

    # Counts
    my_base_qs = Customer.objects.filter(Q(assigned_to=request.user) | Q(created_by=request.user))
    my_total_customers = my_base_qs.count()
    my_buyers_count = my_base_qs.filter(customer_type='buyer').count()
    my_sellers_count = my_base_qs.filter(customer_type='seller').count()
    my_failed_count = my_base_qs.filter(failed_chat_filter).distinct().count()

    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    page_cust_ids = [c.id for c in page_obj]
    failed_cust_ids_in_page = set(
        Customer.objects.filter(id__in=page_cust_ids).filter(failed_chat_filter).values_list('id', flat=True)
    )
    for c in page_obj:
        c.has_failed_message = c.id in failed_cust_ids_in_page

    return render(request, 'employee_portal/whatsapp_inbox.html', {
        'page_obj': page_obj,
        'customers': page_obj,
        'total_count': my_total_customers,
        'buyers_count': my_buyers_count,
        'sellers_count': my_sellers_count,
        'failed_count': my_failed_count,
        'current_party_type': party_type,
        'current_query': query,
        'active_customer_id': active_cust_id,
    })


@login_required
@employee_required
def get_whatsapp_chat(request, customer_id):
    """
    Fetches WhatsApp message thread for a customer.
    Ensures employee can access their own assigned/created customers or claim unassigned ones.
    """
    if request.user.is_superuser or request.user.role == 'admin':
        customer = get_object_or_404(Customer, id=customer_id)
    else:
        customer = Customer.objects.filter(id=customer_id).first()
        if not customer:
            return JsonResponse({'status': 'error', 'message': 'Customer not found.'}, status=404)
        if customer.assigned_to is None:
            customer.assigned_to = request.user
            customer.save(update_fields=['assigned_to'])
        elif customer.assigned_to != request.user and customer.created_by != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied. Customer is assigned to another employee.'}, status=403)

    from core.models import WhatsAppMessageStatus
    from core.utils import format_whatsapp_phone

    chats = WhatsAppChat.objects.filter(customer=customer).order_by('timestamp')
    target_clean_phone = format_whatsapp_phone(customer.whatsapp_number or customer.phone)

    # Collect wamids to batch-fetch delivery statuses
    wamids = [c.wamid for c in chats if c.wamid]
    status_map = {}
    if wamids:
        for st in WhatsAppMessageStatus.objects.filter(wamid__in=wamids):
            status_map[st.wamid] = st

    from core.utils import get_whatsapp_window_status, format_india_time

    # Compute accurate 24h window status
    window_status = get_whatsapp_window_status(customer=customer)
    window_24h_expired = not window_status['is_open']

    # Check recipient latest error (e.g. 131047: Re-engagement message)
    latest_failed = WhatsAppMessageStatus.objects.filter(
        recipient_id=target_clean_phone,
        status='failed'
    ).order_by('-timestamp').first()

    chat_data = []
    from zoneinfo import ZoneInfo
    ist_tz = ZoneInfo("Asia/Kolkata")

    for chat in chats:
        st = status_map.get(chat.wamid)
        delivery_status = st.status if st else ('sent' if chat.direction == 'outgoing' else None)
        err_code = st.error_code if st else (latest_failed.error_code if (latest_failed and chat.direction == 'outgoing' and not st) else None)
        err_title = st.error_title if st else (latest_failed.error_title if (latest_failed and chat.direction == 'outgoing' and not st) else None)

        if timezone.is_aware(chat.timestamp):
            chat_ist = chat.timestamp.astimezone(ist_tz)
        else:
            chat_ist = timezone.make_aware(chat.timestamp, timezone.utc).astimezone(ist_tz)

        chat_data.append({
            'id': chat.id,
            'message': chat.message,
            'direction': chat.direction,
            'attachment_url': chat.attachment.url if chat.attachment else None,
            'attachment_type': chat.attachment_type,
            'wamid': chat.wamid,
            'delivery_status': delivery_status,
            'error_code': err_code,
            'error_title': err_title,
            'time': chat_ist.strftime('%I:%M %p'),
            'date_str': chat_ist.strftime('%Y-%m-%d'),
            'timestamp': chat_ist.strftime('%I:%M %p'),
            'timestamp_iso': chat_ist.isoformat(),
            'timestamp_formatted': chat_ist.strftime('%I:%M %p | %d %b %Y'),
        })

    full_name = f"{customer.first_name} {customer.last_name}".strip()
    return JsonResponse({
        'status': 'success',
        'chats': chat_data,
        'customer_name': full_name or customer.first_name,
        'company_name': customer.company_name or '',
        'phone': customer.whatsapp_number or customer.phone,
        'customer_type': customer.get_customer_type_display(),
        'city': customer.city or '',
        'window_24h_expired': window_24h_expired,
        'window_is_open': window_status['is_open'],
        'window_remaining_str': window_status['formatted_remaining'],
        'window_status_mode': window_status['status_mode'],
        'latest_error_title': latest_failed.error_title if latest_failed else None,
    })


@login_required
@employee_required
def send_whatsapp_message(request, customer_id):
    """
    Sends an outgoing WhatsApp message to the customer from employee portal
    and immediately dispatches it to the recipient's phone via Meta Cloud API.
    Supports auto-attaching Seller Onboarding Guide PDF and logs wamid for delivery tracking.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)

    if request.user.is_superuser or request.user.role == 'admin':
        customer = get_object_or_404(Customer, id=customer_id)
    else:
        customer = Customer.objects.filter(id=customer_id).first()
        if not customer:
            return JsonResponse({'status': 'error', 'message': 'Customer not found.'}, status=404)
        if customer.assigned_to is None:
            customer.assigned_to = request.user
            customer.save(update_fields=['assigned_to'])
        elif customer.assigned_to != request.user and customer.created_by != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied. Customer is assigned to another employee.'}, status=403)

    message_text = request.POST.get('message', '').strip()
    attachment_file = request.FILES.get('attachment')
    attach_seller_guide = request.POST.get('attach_seller_guide') in ('true', '1', True)

    if not message_text and not attachment_file and not attach_seller_guide:
        return JsonResponse({'status': 'error', 'message': 'Message or attachment cannot be empty.'}, status=400)

    # 1. Target recipient phone number
    target_phone = customer.whatsapp_number or customer.phone

    # 2. Dispatch via Meta WhatsApp Cloud API
    from core.utils import (
        send_text_message,
        send_document_message,
        send_seller_onboarding_template,
        get_whatsapp_window_status,
        format_india_time,
        DEFAULT_SELLER_GUIDE_PUBLIC_URL,
        DEFAULT_SELLER_GUIDE_PDF_FILENAME,
        DEFAULT_SELLER_GUIDE_PDF_PATH
    )

    api_dispatched = False
    chosen_wamid = None
    api_error = None
    chat_attachment = attachment_file
    chat_attachment_type = attachment_file.content_type if attachment_file else None

    # Check 24h window status
    window_status = get_whatsapp_window_status(customer=customer)
    is_window_open = window_status['is_open']

    # A. If seller guide PDF should be attached (or onboarding initiated)
    if attach_seller_guide:
        chat_attachment = DEFAULT_SELLER_GUIDE_PDF_PATH
        chat_attachment_type = 'application/pdf'

        if is_window_open:
            # Inside 24h: Send single native document message with caption (Cost-saving session!)
            doc_ok, doc_wamid, doc_err = send_document_message(
                target_phone,
                DEFAULT_SELLER_GUIDE_PUBLIC_URL,
                DEFAULT_SELLER_GUIDE_PDF_FILENAME,
                caption=message_text,
                return_details=True
            )
            if doc_ok:
                api_dispatched = True
                chosen_wamid = doc_wamid
            elif doc_err and ('131047' in str(doc_err) or 'Re-engagement' in str(doc_err)):
                # If Meta rejected free-form due to 24h window closure, automatically fallback to approved template!
                tmpl_ok, tmpl_wamid, tmpl_err = send_seller_onboarding_template(target_phone, return_details=True)
                if tmpl_ok:
                    api_dispatched = True
                    chosen_wamid = tmpl_wamid
                else:
                    api_error = tmpl_err
            else:
                api_error = doc_err
        else:
            # Outside 24h: Meta blocks free-form, so immediately dispatch approved Meta template!
            tmpl_ok, tmpl_wamid, tmpl_err = send_seller_onboarding_template(target_phone, return_details=True)
            if tmpl_ok:
                api_dispatched = True
                chosen_wamid = tmpl_wamid
            else:
                api_error = tmpl_err

    # B. Send text message (if seller guide was not attached)
    elif message_text:
        txt_ok, txt_wamid, txt_err = send_text_message(target_phone, message_text, return_details=True)
        if txt_ok:
            api_dispatched = True
            chosen_wamid = txt_wamid
        elif txt_err and ('131047' in str(txt_err) or 'Re-engagement' in str(txt_err)):
            # If text was onboarding message, auto-recover with template
            if 'Welcome to Apni Factory' in message_text:
                tmpl_ok, tmpl_wamid, tmpl_err = send_seller_onboarding_template(target_phone, return_details=True)
                if tmpl_ok:
                    api_dispatched = True
                    chosen_wamid = tmpl_wamid
                    chat_attachment = DEFAULT_SELLER_GUIDE_PDF_PATH
                    chat_attachment_type = 'application/pdf'
                else:
                    api_error = tmpl_err
            else:
                api_error = txt_err
        else:
            api_error = txt_err

    # 3. Save to chat history
    chat = WhatsAppChat.objects.create(
        customer=customer,
        direction='outgoing',
        message=message_text,
        attachment=chat_attachment,
        attachment_type=chat_attachment_type,
        wamid=chosen_wamid,
        timestamp=timezone.now()
    )

    # 4. Update WhatsApp lead state for live human agent handoff
    try:
        from core.models import WhatsAppLead
        from core.utils import format_whatsapp_phone
        lead, _ = WhatsAppLead.objects.get_or_create(phone_number=format_whatsapp_phone(target_phone))
        lead.customer = customer
        lead.needs_human = True
        lead.save()
    except Exception:
        pass

    from zoneinfo import ZoneInfo
    ist_tz = ZoneInfo("Asia/Kolkata")
    chat_ist = chat.timestamp.astimezone(ist_tz) if timezone.is_aware(chat.timestamp) else timezone.make_aware(chat.timestamp, timezone.utc).astimezone(ist_tz)

    return JsonResponse({
        'status': 'success',
        'message_id': chat.id,
        'text': chat.message,
        'dispatched': api_dispatched,
        'wamid': chosen_wamid,
        'api_error': api_error,
        'attachment_url': chat.attachment.url if chat.attachment else None,
        'attachment_type': chat.attachment_type,
        'time': chat_ist.strftime('%I:%M %p'),
        'date_str': chat_ist.strftime('%Y-%m-%d'),
        'timestamp': chat_ist.strftime('%I:%M %p'),
        'timestamp_iso': chat_ist.isoformat(),
    })


@login_required
@employee_required
def start_whatsapp_chat(request):
    """
    Seamlessly initiates or redirects to a WhatsApp chat in the Employee CRM WhatsApp Inbox
    from vendor search, directory, or customer cards.
    """
    customer_id = request.GET.get('customer_id')
    vendor_id = request.GET.get('vendor_id')

    if customer_id:
        customer = get_object_or_404(
            Customer,
            Q(id=customer_id) & (Q(assigned_to=request.user) | Q(created_by=request.user))
        )
        return redirect(f"/employee/whatsapp/?customer_id={customer.id}")

    if vendor_id:
        vendor = get_object_or_404(
            VendorProfile,
            Q(id=vendor_id) & (Q(created_by=request.user) | Q(assigned_to=request.user))
        )
        phone = vendor.mobile_number or vendor.phone_number or ''

        # Check if customer already exists for this phone
        existing = None
        if phone:
            existing = Customer.objects.filter(phone=phone).first()

        if not existing:
            cust_type = 'seller' if vendor.party_type == 'SELLER' else 'buyer'
            existing = Customer.objects.create(
                first_name=vendor.store_name,
                phone=phone or f"TEMP_{vendor.id}",
                email=vendor.email_address or None,
                company_name=vendor.store_name,
                address=vendor.street_address or '',
                city=vendor.city or '',
                state=vendor.state or '',
                pincode=vendor.pincode or '',
                customer_type=cust_type,
                lead_source='manual',
                status='lead',
                assigned_to=request.user,
                created_by=request.user,
                notes=f"Auto-created from {vendor.get_party_type_display()} on {timezone.localdate().strftime('%d %b %Y')} for WhatsApp support."
            )

        return redirect(f"/employee/whatsapp/?customer_id={existing.id}")

    return redirect('employee_portal:whatsapp_inbox')


@login_required
@employee_required
def whatsapp_search_contacts(request):
    """
    Live AJAX search for WhatsApp contacts for employee.
    Detects if query is a phone number and checks if it exists in the database.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'status': 'success', 'results': [], 'is_phone': False, 'phone_in_db': False})

    digits = ''.join(c for c in q if c.isdigit())
    is_phone = len(digits) >= 7
    clean_10 = digits[-10:] if len(digits) >= 10 else digits

    # Find matching customers assigned to or created by this employee
    query_filter = (Q(assigned_to=request.user) | Q(created_by=request.user)) & (
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(company_name__icontains=q)
    )
    if digits:
        query_filter |= (Q(assigned_to=request.user) | Q(created_by=request.user)) & (
            Q(phone__icontains=digits) | Q(whatsapp_number__icontains=digits)
        )
        if len(digits) >= 10:
            query_filter |= (Q(assigned_to=request.user) | Q(created_by=request.user)) & (
                Q(phone__endswith=clean_10) | Q(whatsapp_number__endswith=clean_10)
            )

    matches = Customer.objects.filter(query_filter).distinct()[:15]
    
    results = []
    for c in matches:
        full_name = f"{c.first_name or ''} {c.last_name or ''}".strip()
        results.append({
            'id': c.id,
            'name': full_name or c.company_name or f"Customer {c.phone[-4:] if c.phone else ''}",
            'phone': c.whatsapp_number or c.phone or '',
            'company': c.company_name or '',
            'type': c.get_customer_type_display() if hasattr(c, 'get_customer_type_display') else c.customer_type,
            'city': c.city or '',
        })

    # Check specifically if the exact phone number is in the entire database
    phone_in_db = False
    existing_cust_data = None
    if len(digits) >= 10:
        existing_cust = Customer.objects.filter(
            Q(phone=clean_10) | Q(whatsapp_number=clean_10) |
            Q(phone__endswith=clean_10) | Q(whatsapp_number__endswith=clean_10)
        ).first()
        if existing_cust:
            phone_in_db = True
            is_mine = (existing_cust.assigned_to == request.user or existing_cust.created_by == request.user)
            existing_cust_data = {
                'id': existing_cust.id,
                'name': f"{existing_cust.first_name or ''} {existing_cust.last_name or ''}".strip() or existing_cust.company_name or f"Customer {existing_cust.phone[-4:]}",
                'phone': existing_cust.whatsapp_number or existing_cust.phone,
                'type': existing_cust.get_customer_type_display() if hasattr(existing_cust, 'get_customer_type_display') else existing_cust.customer_type,
                'is_mine': is_mine,
                'assigned_to_me': is_mine,
            }

    return JsonResponse({
        'status': 'success',
        'query': q,
        'is_phone': is_phone,
        'digits': digits,
        'clean_phone': clean_10,
        'phone_in_db': phone_in_db,
        'existing_customer': existing_cust_data,
        'results': results,
    })


@csrf_exempt
@login_required
@employee_required
def whatsapp_start_new_chat(request):
    """
    Employee initiates a WhatsApp conversation with a new or unsaved phone number.
    If customer not in database, creates a new Customer assigned to this employee.
    If customer exists and is unassigned, assigns to this employee.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST method required.'}, status=405)

    from core.utils import (
        send_text_message,
        send_document_message,
        send_seller_onboarding_template,
        get_whatsapp_window_status,
        format_india_time,
        format_whatsapp_phone,
        DEFAULT_SELLER_GUIDE_PUBLIC_URL,
        DEFAULT_SELLER_GUIDE_PDF_FILENAME,
        DEFAULT_SELLER_GUIDE_PDF_PATH
    )
    from core.models import WhatsAppLead

    raw_phone = request.POST.get('phone', '').strip()
    customer_name = request.POST.get('name', '').strip()
    customer_type = request.POST.get('customer_type', 'buyer').strip().lower()
    initial_message = request.POST.get('initial_message', '').strip()
    attach_seller_guide = request.POST.get('attach_seller_guide') in ('true', '1', True)

    digits = ''.join(c for c in raw_phone if c.isdigit())
    if len(digits) < 10:
        return JsonResponse({'status': 'error', 'message': 'Please enter a valid 10-digit mobile number.'}, status=400)

    clean_phone = format_whatsapp_phone(raw_phone)
    short_phone = clean_phone[2:] if clean_phone.startswith('91') and len(clean_phone) == 12 else clean_phone

    # Search for existing customer
    customer = Customer.objects.filter(
        Q(phone=clean_phone) | Q(phone=short_phone) |
        Q(whatsapp_number=clean_phone) | Q(whatsapp_number=short_phone)
    ).first()

    is_new = False
    if not customer:
        customer = Customer.objects.create(
            first_name=customer_name or f"Lead {short_phone[-4:]}",
            phone=clean_phone,
            whatsapp_number=clean_phone,
            customer_type=customer_type,
            lead_source='whatsapp'
        )
        is_new = True
    else:
        if customer_name and not customer.first_name:
            customer.first_name = customer_name
        if not customer.whatsapp_number:
            customer.whatsapp_number = clean_phone
        customer.save()

    target_phone = customer.whatsapp_number or customer.phone
    lead, _ = WhatsAppLead.objects.get_or_create(phone_number=format_whatsapp_phone(target_phone))
    lead.customer = customer
    lead.needs_human = True
    lead.save()

    # Check 24h window
    window_status = get_whatsapp_window_status(customer=customer, phone=target_phone)
    is_window_open = window_status['is_open']

    sent_chat = None
    if initial_message or attach_seller_guide:
        chosen_wamid = None
        attachment_path = None
        attachment_type = None

        if attach_seller_guide:
            attachment_path = DEFAULT_SELLER_GUIDE_PDF_PATH
            attachment_type = 'application/pdf'

            if is_window_open:
                # Inside 24h window: send document with caption
                doc_ok, doc_wamid, doc_err = send_document_message(
                    target_phone,
                    DEFAULT_SELLER_GUIDE_PUBLIC_URL,
                    DEFAULT_SELLER_GUIDE_PDF_FILENAME,
                    caption=initial_message,
                    return_details=True
                )
                if doc_wamid:
                    chosen_wamid = doc_wamid
                elif doc_err and ('131047' in str(doc_err) or 'Re-engagement' in str(doc_err)):
                    tmpl_ok, tmpl_wamid, _ = send_seller_onboarding_template(target_phone, return_details=True)
                    if tmpl_wamid:
                        chosen_wamid = tmpl_wamid
            else:
                # Outside 24h window: send approved template
                tmpl_ok, tmpl_wamid, _ = send_seller_onboarding_template(target_phone, return_details=True)
                if tmpl_wamid:
                    chosen_wamid = tmpl_wamid
        elif initial_message:
            txt_ok, txt_wamid, txt_err = send_text_message(target_phone, initial_message, return_details=True)
            if txt_wamid:
                chosen_wamid = txt_wamid
            elif txt_err and ('131047' in str(txt_err) or 'Re-engagement' in str(txt_err)) and 'Welcome to Apni Factory' in initial_message:
                tmpl_ok, tmpl_wamid, _ = send_seller_onboarding_template(target_phone, return_details=True)
                if tmpl_wamid:
                    chosen_wamid = tmpl_wamid
                    attachment_path = DEFAULT_SELLER_GUIDE_PDF_PATH
                    attachment_type = 'application/pdf'

        chat = WhatsAppChat.objects.create(
            customer=customer,
            message=initial_message,
            direction='outgoing',
            attachment=attachment_path,
            attachment_type=attachment_type,
            wamid=chosen_wamid,
            timestamp=timezone.now()
        )
        from zoneinfo import ZoneInfo
        ist_tz = ZoneInfo("Asia/Kolkata")
        chat_ist = chat.timestamp.astimezone(ist_tz) if timezone.is_aware(chat.timestamp) else timezone.make_aware(chat.timestamp, timezone.utc).astimezone(ist_tz)

        sent_chat = {
            'id': chat.id,
            'message': chat.message,
            'wamid': chat.wamid,
            'attachment_url': chat.attachment.url if chat.attachment else None,
            'time': chat_ist.strftime('%I:%M %p'),
            'date_str': chat_ist.strftime('%Y-%m-%d'),
            'timestamp': chat_ist.strftime('%I:%M %p'),
            'timestamp_iso': chat_ist.isoformat(),
        }

    return JsonResponse({
        'status': 'success',
        'is_new': is_new,
        'customer': {
            'id': customer.id,
            'name': f"{customer.first_name or ''} {customer.last_name or ''}".strip() or customer.company_name or customer.phone,
            'first_name': customer.first_name,
            'phone': customer.whatsapp_number or customer.phone,
            'customer_type': customer.get_customer_type_display() if hasattr(customer, 'get_customer_type_display') else customer.customer_type,
        },
        'sent_chat': sent_chat,
        'redirect_url': f"/employee/whatsapp/?customer_id={customer.id}"
    })
