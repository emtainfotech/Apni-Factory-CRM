"""
report_builder.py — Apni Factory CRM
=====================================
Central reporting engine that gathers all admin dashboard figures
(CRM metrics, e-commerce data, employee stats, attendance) for a
given date range and returns a structured dict ready for WhatsApp formatting.

Usage:
    from core.report_builder import build_dashboard_report, format_whatsapp_report
    data   = build_dashboard_report(start_date, end_date, label="Today")
    text   = format_whatsapp_report(data)
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q, Sum, Count
from django.utils import timezone

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ist_now():
    return datetime.now(tz=IST)


def _date_today_ist():
    return _ist_now().date()


# ---------------------------------------------------------------------------
# Core report builder
# ---------------------------------------------------------------------------

def build_dashboard_report(start_date, end_date, label="Today"):
    """
    Collect all dashboard metrics for the date range [start_date, end_date].
    Both are `datetime.date` objects.
    Returns a rich dict usable by format_whatsapp_report().
    """
    from authentication.models import User
    from core.models import (
        Customer, Invoice, Attendance, CallLog,
        CustomerActivityLog, LeaveRequest, Transaction,
    )

    # Lazy-import remote models to avoid breaking if hostinger_db is unavailable
    try:
        from hostinger_data.models import (
            Users as HostingerUser, Companies, Brands, Products, Orders,
            Wallet, Credits, Advertisements, Tickets,
            Customers as HostingerCustomer,
        )
        from django.db.models import Subquery, OuterRef
        from hostinger_data.models import OrderStatus
        _remote_ok = True
    except Exception:
        _remote_ok = False

    today = _date_today_ist()

    # ---- Date range filters ----
    crm_filter   = {'created_at__date__gte': start_date, 'created_at__date__lte': end_date}
    start_dt     = datetime(start_date.year, start_date.month, start_date.day, tzinfo=IST)
    end_dt       = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=IST)

    # ---- CRM Stats ----
    total_customers    = Customer.objects.count()
    total_leads        = Customer.objects.filter(status='lead').count()
    new_customers      = Customer.objects.filter(**crm_filter).count()
    total_invoices     = Invoice.objects.count()
    period_invoices    = Invoice.objects.filter(**crm_filter).count()
    period_revenue     = Invoice.objects.filter(**crm_filter).aggregate(t=Sum('total_amount'))['t'] or 0

    # ---- Call Stats ----
    total_calls     = CallLog.objects.filter(**crm_filter).count()
    connected_calls = CallLog.objects.filter(call_status='connected', **crm_filter).count()
    followups_due   = CallLog.objects.filter(follow_up_date__date=today).count()

    # ---- HR Stats ----
    pending_leaves  = LeaveRequest.objects.filter(status='pending').count()
    total_employees = User.objects.exclude(Q(role='admin') | Q(is_superuser=True)).count()

    # Attendance for date range
    att_qs      = Attendance.objects.filter(date__gte=start_date, date__lte=end_date)
    present_att = att_qs.filter(status__in=['present', 'half_day']).count()
    absent_att  = att_qs.filter(status='absent').count()

    # Today's punch-in
    today_att        = Attendance.objects.filter(date=today)
    punched_in_today = today_att.filter(is_punched_in=True).count()
    on_break_today   = today_att.filter(on_break=True).count()

    # ---- Employee-wise stats ----
    employees = list(
        User.objects.exclude(Q(role='admin') | Q(is_superuser=True))
        .filter(is_employee_active=True)
        .order_by('username')
    )
    emp_stats = []
    for emp in employees:
        att_today   = Attendance.objects.filter(user=emp, date=today).first()
        calls       = CallLog.objects.filter(employee=emp, **crm_filter).count()
        created     = Customer.objects.filter(created_by=emp, **crm_filter).count()
        updated     = CustomerActivityLog.objects.filter(employee=emp, **crm_filter).count()
        followups   = CallLog.objects.filter(employee=emp, follow_up_date__date=today).count()
        assigned    = Customer.objects.filter(assigned_to=emp).count()

        status = "🔴 Absent"
        if att_today:
            if att_today.is_punched_in:
                status = "🟢 Active" if not att_today.on_break else "🟡 On Break"
            elif att_today.punch_out:
                status = "⚫ Left"
            else:
                status = "🟠 Punched In"

        emp_stats.append({
            'name':      emp.get_display_name() or emp.username,
            'username':  emp.username,
            'status':    status,
            'calls':     calls,
            'created':   created,
            'updated':   updated,
            'followups': followups,
            'assigned':  assigned,
        })

    # ---- Remote E-commerce Stats ----
    remote_stats = {}
    if _remote_ok:
        try:
            total_orders   = Orders.objects.count()
            period_orders  = Orders.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date).count()
            total_sales    = Orders.objects.aggregate(t=Sum('grandtotal'))['t'] or 0
            period_sales   = Orders.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date).aggregate(t=Sum('grandtotal'))['t'] or 0
            total_sellers  = HostingerUser.objects.count()
            total_buyers   = HostingerCustomer.objects.count()
            total_products = Products.objects.count()
            total_tickets  = Tickets.objects.count()
            total_companies= Companies.objects.count()

            # Order status breakdown
            latest_status_subquery = OrderStatus.objects.filter(
                order_id=OuterRef('id')
            ).order_by('-created_at', '-id').values('status')[:1]

            annotated = Orders.objects.annotate(latest_status=Subquery(latest_status_subquery))
            active_orders   = annotated.exclude(latest_status__in=['Delivered', 'Cancelled', 'Returned']).count()
            pending_orders  = annotated.filter(latest_status__icontains='pending').count()
            delivered_orders= annotated.filter(latest_status__icontains='delivered').count()
            cancelled_orders= annotated.filter(latest_status__icontains='cancelled').count()

            remote_stats = {
                'total_orders':    total_orders,
                'period_orders':   period_orders,
                'total_sales':     total_sales,
                'period_sales':    period_sales,
                'total_sellers':   total_sellers,
                'total_buyers':    total_buyers,
                'total_products':  total_products,
                'total_tickets':   total_tickets,
                'total_companies': total_companies,
                'active_orders':   active_orders,
                'pending_orders':  pending_orders,
                'delivered_orders':delivered_orders,
                'cancelled_orders':cancelled_orders,
            }
        except Exception as e:
            remote_stats = {'error': str(e)}

    return {
        'label':            label,
        'start_date':       start_date,
        'end_date':         end_date,
        'generated_at':     _ist_now().strftime('%d %b %Y, %I:%M %p IST'),
        # CRM
        'total_customers':  total_customers,
        'total_leads':      total_leads,
        'new_customers':    new_customers,
        'total_invoices':   total_invoices,
        'period_invoices':  period_invoices,
        'period_revenue':   float(period_revenue),
        # Calls
        'total_calls':      total_calls,
        'connected_calls':  connected_calls,
        'followups_due':    followups_due,
        # HR
        'total_employees':  total_employees,
        'pending_leaves':   pending_leaves,
        'punched_in_today': punched_in_today,
        'on_break_today':   on_break_today,
        'present_att':      present_att,
        'absent_att':       absent_att,
        # Employee details
        'employees':        emp_stats,
        # Remote/E-commerce
        'remote':           remote_stats,
    }


# ---------------------------------------------------------------------------
# WhatsApp Message Formatter
# ---------------------------------------------------------------------------

def format_whatsapp_report(data, include_employee_detail=False, compact=False):
    """
    Convert the report dict into a WhatsApp-safe text message (4096 char limit).
    WhatsApp only renders *bold*, _italic_, ~strikethrough~, ```code```.
    Employee scorecard is omitted by default for clean executive reports.
    """
    d = data
    remote = d.get('remote', {})
    label = d.get('label', 'Report')
    date_range = ""
    if d['start_date'] == d['end_date']:
        date_range = d['start_date'].strftime('%d %b %Y')
    else:
        date_range = f"{d['start_date'].strftime('%d %b')} – {d['end_date'].strftime('%d %b %Y')}"

    lines = []
    lines.append(f"📊 *Apni Factory CRM — {label} Report*")
    lines.append(f"📅 {date_range}  |  ⏱ {d['generated_at']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    # CRM Section
    lines.append("🏢 *CRM OVERVIEW*")
    lines.append(f"  👥 Total Customers: *{d['total_customers']:,}*")
    lines.append(f"  🆕 New ({label}): *{d['new_customers']:,}*")
    lines.append(f"  🎯 Active Leads: *{d['total_leads']:,}*")
    lines.append(f"  📋 Total Invoices: *{d['total_invoices']:,}*")
    lines.append(f"  🧾 Period Invoices: *{d['period_invoices']:,}*")
    lines.append(f"  💰 Period Revenue: *₹{d['period_revenue']:,.0f}*")
    lines.append("")

    # Calls
    lines.append("📞 *CALL ACTIVITY*")
    lines.append(f"  📲 Total Calls ({label}): *{d['total_calls']:,}*")
    lines.append(f"  ✅ Connected: *{d['connected_calls']:,}*")
    lines.append(f"  🔔 Follow-ups Due Today: *{d['followups_due']:,}*")
    lines.append("")

    # Ecommerce
    if remote and not remote.get('error'):
        lines.append("🛒 *E-COMMERCE (Apni Factory App)*")
        lines.append(f"  📦 Total Orders: *{remote.get('total_orders', 0):,}*")
        lines.append(f"  🛍️ Period Orders: *{remote.get('period_orders', 0):,}*")
        lines.append(f"  💵 Total Sales: *₹{remote.get('total_sales', 0):,.0f}*")
        lines.append(f"  📈 Period Sales: *₹{remote.get('period_sales', 0):,.0f}*")
        lines.append(f"  ⏳ Active Orders: *{remote.get('active_orders', 0):,}*")
        lines.append(f"  🕐 Pending Orders: *{remote.get('pending_orders', 0):,}*")
        lines.append(f"  ✔️ Delivered: *{remote.get('delivered_orders', 0):,}*")
        lines.append(f"  ❌ Cancelled: *{remote.get('cancelled_orders', 0):,}*")
        lines.append(f"  🏪 Sellers: *{remote.get('total_sellers', 0):,}*")
        lines.append(f"  👤 Buyers: *{remote.get('total_buyers', 0):,}*")
        lines.append(f"  📦 Products: *{remote.get('total_products', 0):,}*")
        lines.append(f"  🎫 Support Tickets: *{remote.get('total_tickets', 0):,}*")
        lines.append("")
    elif remote.get('error'):
        lines.append(f"⚠️ E-commerce data unavailable: {remote['error'][:80]}")
        lines.append("")

    # HR & Attendance
    lines.append("👔 *TEAM & ATTENDANCE*")
    lines.append(f"  👨‍💼 Total Staff: *{d['total_employees']:,}*")
    lines.append(f"  🟢 Punched In Today: *{d['punched_in_today']:,}*")
    lines.append(f"  🟡 On Break: *{d['on_break_today']:,}*")
    lines.append(f"  ✅ Present ({label}): *{d['present_att']:,}*")
    lines.append(f"  🔴 Absent ({label}): *{d['absent_att']:,}*")
    lines.append(f"  🏖️ Pending Leaves: *{d['pending_leaves']:,}*")
    lines.append("")

    # Employee Detail
    if include_employee_detail and d.get('employees'):
        lines.append("👤 *EMPLOYEE SCORECARD*")
        for emp in d['employees']:
            lines.append(
                f"  {emp['status']} *{emp['name']}*"
            )
            if not compact:
                lines.append(
                    f"    📞 Calls: {emp['calls']}  |  🆕 Created: {emp['created']}  |  📝 Updated: {emp['updated']}"
                )
                lines.append(
                    f"    🔔 Follow-ups: {emp['followups']}  |  👥 Assigned: {emp['assigned']}"
                )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 Reply *help* for available commands")
    lines.append("_Apni Factory CRM — Auto Report_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience wrappers for common date ranges
# ---------------------------------------------------------------------------

def get_today_report():
    today = _date_today_ist()
    data  = build_dashboard_report(today, today, label="Today")
    return format_whatsapp_report(data)


def get_yesterday_report():
    yesterday = _date_today_ist() - timedelta(days=1)
    data      = build_dashboard_report(yesterday, yesterday, label="Yesterday")
    return format_whatsapp_report(data)


def get_week_report():
    today      = _date_today_ist()
    week_start = today - timedelta(days=today.weekday())
    data       = build_dashboard_report(week_start, today, label="This Week")
    return format_whatsapp_report(data)


def get_month_report():
    today       = _date_today_ist()
    month_start = today.replace(day=1)
    data        = build_dashboard_report(month_start, today, label="This Month")
    return format_whatsapp_report(data)


def get_overall_report():
    from core.models import Customer
    try:
        first_customer = Customer.objects.order_by('created_at').first()
        start = first_customer.created_at.date() if first_customer else _date_today_ist()
    except Exception:
        start = _date_today_ist()
    today = _date_today_ist()
    data  = build_dashboard_report(start, today, label="Overall (All Time)")
    return format_whatsapp_report(data)


def get_custom_date_report(start_date, end_date):
    """start_date, end_date: datetime.date objects"""
    label = f"Custom ({start_date.strftime('%d %b')}–{end_date.strftime('%d %b %Y')})"
    data  = build_dashboard_report(start_date, end_date, label=label)
    return format_whatsapp_report(data)
