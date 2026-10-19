"""
whatsapp_report_sender.py — Apni Factory CRM
==============================================
Handles WhatsApp report dispatching and incoming admin commands:
  - Command parsing: /report, today, yesterday, overall, week, month, custom <date> to <date>, help
  - Morning (6 AM) and Evening (8 PM) scheduled dispatch
  - Message chunking (respecting Meta's 4096 character limit)
  - Admin recipient authorization & logging
"""

import logging
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q

from core.models import AdminReportRecipient
from core.report_builder import (
    build_dashboard_report,
    format_whatsapp_report,
    get_today_report,
    get_yesterday_report,
    get_overall_report,
    get_week_report,
    get_month_report,
    get_custom_date_report,
)
from core.utils import send_text_message, format_whatsapp_phone

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# WhatsApp message safe length limit
MAX_WHATSAPP_LEN = 3800


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_phone_digits(phone_str: str) -> str:
    """Extract digits and return the last 10 digits for Indian numbers."""
    if not phone_str:
        return ""
    digits = "".join(c for c in str(phone_str) if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        return digits[2:]
    return digits[-10:] if len(digits) >= 10 else digits


def is_admin_report_recipient(phone_str: str) -> bool:
    """
    Checks if phone_str matches ANY registered AdminReportRecipient
    (active or inactive) or any CRM admin/superuser.
    Used to guarantee that customer onboarding chatbot messages are NEVER
    sent to admin reporting phone numbers.
    """
    clean_10 = normalize_phone_digits(phone_str)
    if not clean_10:
        return False

    for recipient in AdminReportRecipient.objects.all():
        if normalize_phone_digits(recipient.phone) == clean_10:
            return True

    try:
        from authentication.models import User
        if User.objects.filter(
            Q(is_superuser=True) | Q(role='admin'),
            phone_number__endswith=clean_10
        ).exists():
            return True
    except Exception:
        pass

    return False


def find_authorized_recipient(sender_phone: str):
    """
    Check if sender_phone belongs to an active AdminReportRecipient with allow_commands=True,
    or a superuser with that phone number.
    Returns AdminReportRecipient instance or a synthetic admin obj, or None.
    """
    clean_10 = normalize_phone_digits(sender_phone)
    if not clean_10:
        return None

    # 1. Match AdminReportRecipient
    for recipient in AdminReportRecipient.objects.filter(is_active=True, allow_commands=True):
        if normalize_phone_digits(recipient.phone) == clean_10:
            return recipient

    # 2. Fallback: match superuser phone number
    try:
        from authentication.models import User
        admin_user = User.objects.filter(
            Q(is_superuser=True) | Q(role='admin'),
            phone_number__endswith=clean_10
        ).first()
        if admin_user:
            # Auto-create or wrap
            rec, _ = AdminReportRecipient.objects.get_or_create(
                phone=clean_10,
                defaults={
                    'name': admin_user.get_full_name() or admin_user.username or 'Admin',
                    'report_type': 'morning',
                    'include_employee_detail': False,
                    'is_active': True,
                    'allow_commands': True,
                }
            )
            return rec
    except Exception as e:
        logger.warning(f"Error checking admin user phone: {e}")

    return None


def split_message_if_needed(text: str, max_len: int = MAX_WHATSAPP_LEN) -> list[str]:
    """
    Splits long messages gracefully along paragraph/section boundaries
    so that WhatsApp Meta API doesn't truncate or reject (>4096 chars).
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_len and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def send_whatsapp_chunks(to_number: str, text: str) -> tuple[bool, str]:
    """
    Send text to recipient, splitting into chunks if necessary.
    Returns (success, error_message).
    """
    chunks = split_message_if_needed(text)
    total = len(chunks)
    all_success = True
    last_err = ""

    for idx, chunk in enumerate(chunks, 1):
        # Add page indicator if multiple chunks
        if total > 1:
            header = f"📄 *Part {idx}/{total}*\n"
            content = header + chunk
        else:
            content = chunk

        success, wamid, err = send_text_message(to_number, content, return_details=True)
        if not success:
            all_success = False
            last_err = err or "Unknown dispatch error"
            logger.error(f"Failed to send chunk {idx}/{total} to {to_number}: {last_err}")
        else:
            logger.info(f"Report chunk {idx}/{total} sent to {to_number} (wamid: {wamid})")

        # Brief pause between chunks if multiple
        if total > 1 and idx < total:
            time.sleep(1)

    return all_success, last_err


# ---------------------------------------------------------------------------
# Date parsing for custom commands
# ---------------------------------------------------------------------------

DATE_FORMATS = [
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
    "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
]


def parse_date_string(date_str: str) -> date | None:
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_custom_range(text: str) -> tuple[date | None, date | None]:
    """
    Parses dates from messages like:
      - custom 2026-10-01 to 2026-10-10
      - custom 01-10-2026 to 10-10-2026
      - custom 01/10/2026 - 10/10/2026
      - custom 2026-10-05 (single date)
    """
    # Remove command prefix
    cleaned = re.sub(r'^(custom|date|dates|report)\s+', '', text, flags=re.IGNORECASE).strip()

    # Split by 'to', 'until', 'till', '-', '—'
    delimiters = [r'\s+to\s+', r'\s+till\s+', r'\s+until\s+', r'\s+-\s+', r'\s+—\s+']
    for delim in delimiters:
        parts = re.split(delim, cleaned, flags=re.IGNORECASE)
        if len(parts) == 2:
            d1 = parse_date_string(parts[0])
            d2 = parse_date_string(parts[1])
            if d1 and d2:
                if d1 > d2:
                    d1, d2 = d2, d1
                return d1, d2

    # Single date
    single = parse_date_string(cleaned)
    if single:
        return single, single

    return None, None


# ---------------------------------------------------------------------------
# Help Menu
# ---------------------------------------------------------------------------

def get_help_message() -> str:
    return (
        "📊 *APNI FACTORY CRM — REPORT BOT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send any of these commands to get instant reports:\n\n"
        "🔹 */report* or *today*\n"
        "   Current day's live figures & employee punch status\n\n"
        "🔹 *yesterday* or *last day*\n"
        "   Yesterday's complete figures\n\n"
        "🔹 *week* or *this week*\n"
        "   Current week to date\n\n"
        "🔹 *month* or *this month*\n"
        "   Current month to date\n\n"
        "🔹 *overall* or *all*\n"
        "   All-time lifetime metrics (Orders, Revenue, Customers)\n\n"
        "🔹 *custom <date> to <date>*\n"
        "   Custom range report\n"
        "   _Example:_ `custom 01-10-2026 to 10-10-2026`\n"
        "   _Example:_ `custom 2026-10-05` (single date)\n\n"
        "🔹 *staff* or *team*\n"
        "   Team scorecard, calls & followups today\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ *Daily Automated Reports:*\n"
        "• Morning 6:00 AM (Today's live summary)\n"
        "• Evening 8:00 PM (Today's end of day summary)\n\n"
        "_Apni Factory CRM Automation_"
    )


# ---------------------------------------------------------------------------
# Inbound Admin Command Processor
# ---------------------------------------------------------------------------

def handle_admin_whatsapp_command(sender_phone: str, raw_text: str) -> tuple[bool, str]:
    """
    Checks if message from sender_phone is an authorized admin report command.
    If so, generates the requested report and sends it via WhatsApp.

    Returns:
        (handled: bool, message: str)
        handled = True if it was an admin command from authorized number (intercepted).
        handled = False if not an admin command or unauthorized (continue normal CRM bot flow).
    """
    if not raw_text or not sender_phone:
        return False, "Empty message or phone"

    text = raw_text.strip()
    cmd = text.lower()

    # List of triggers
    is_report_trigger = (
        cmd in ['/report', 'report', 'today', '/today', 'today report', 'aaj ka report'] or
        cmd in ['yesterday', 'last day', 'lastday', 'kal ka report', 'previous', 'prev'] or
        cmd in ['overall', 'all', '/overall', 'total', 'all time', 'all-time'] or
        cmd in ['week', 'this week', 'weekly', 'is hafte'] or
        cmd in ['month', 'this month', 'monthly', 'is mahine'] or
        cmd in ['staff', 'team', 'employees', 'employee', 'scorecard'] or
        cmd in ['help', '/help', 'menu', 'commands', 'report help', '?', 'hi', 'hello', 'start', 'reset', 'info'] or
        cmd.startswith('custom') or
        (cmd.startswith('report ') and any(char.isdigit() for char in cmd))
    )

    if not is_report_trigger:
        return False, "Not a report command"

    # Verify authorization
    recipient = find_authorized_recipient(sender_phone)
    if not recipient:
        logger.info(f"Report command '{text}' from unauthorized number {sender_phone} — ignored.")
        return False, "Unauthorized number"

    logger.info(f"Authorized report command '{text}' received from {recipient.name} ({sender_phone})")

    # Generate appropriate response
    try:
        if cmd in ['help', '/help', 'menu', 'commands', 'report help', '?', 'hi', 'hello', 'start', 'reset', 'info']:
            reply_text = get_help_message()

        elif cmd in ['/report', 'report', 'today', '/today', 'today report', 'aaj ka report']:
            reply_text = get_today_report()

        elif cmd in ['yesterday', 'last day', 'lastday', 'kal ka report', 'previous', 'prev']:
            reply_text = get_yesterday_report()

        elif cmd in ['overall', 'all', '/overall', 'total', 'all time', 'all-time']:
            reply_text = get_overall_report()

        elif cmd in ['week', 'this week', 'weekly', 'is hafte']:
            reply_text = get_week_report()

        elif cmd in ['month', 'this month', 'monthly', 'is mahine']:
            reply_text = get_month_report()

        elif cmd in ['staff', 'team', 'employees', 'employee', 'scorecard']:
            today = datetime.now(tz=IST).date()
            data = build_dashboard_report(today, today, label="Today — Staff Scorecard")
            reply_text = format_whatsapp_report(data, include_employee_detail=True, compact=False)

        elif cmd.startswith('custom') or (cmd.startswith('report ') and any(char.isdigit() for char in cmd)):
            start_d, end_d = parse_custom_range(text)
            if not start_d:
                reply_text = (
                    "⚠️ *Could not recognize dates.*\n\n"
                    "Please use one of these formats:\n"
                    "• `custom 01-10-2026 to 10-10-2026`\n"
                    "• `custom 2026-10-01 to 2026-10-10`\n"
                    "• `custom 05-10-2026` (single day)\n\n"
                    "Reply *help* to see all commands."
                )
            else:
                reply_text = get_custom_date_report(start_d, end_d)
        else:
            reply_text = get_today_report()

        # Send response via WhatsApp
        success, err = send_whatsapp_chunks(sender_phone, reply_text)
        if not success:
            logger.error(f"Failed to dispatch command response to {sender_phone}: {err}")
            return True, f"Generated but delivery failed: {err}"

        return True, "Report delivered successfully"

    except Exception as e:
        logger.exception(f"Error handling admin report command from {sender_phone}: {e}")
        error_msg = f"⚠️ *Error generating report:* {str(e)[:150]}\nPlease try again shortly."
        send_text_message(sender_phone, error_msg)
        return True, f"Error: {e}"


# ---------------------------------------------------------------------------
# Scheduled Senders (Morning & Evening)
# ---------------------------------------------------------------------------

def send_morning_reports() -> dict:
    """
    Sends the morning 6 AM daily report to all registered active recipients.
    Sends today's figures (as requested: 'in morning send todays day instead of yesterday').
    Employee scorecard is omitted for clean executive report.
    """
    recipients = list(AdminReportRecipient.objects.filter(
        is_active=True,
        report_type__in=['morning', 'both']
    ))

    if not recipients:
        if not AdminReportRecipient.objects.exists():
            logger.info("send_morning_reports: No recipients found in database. Auto-seeding primary admin 9340547135...")
            primary = AdminReportRecipient.objects.create(
                name="Admin (Primary)",
                phone="9340547135",
                report_type="both",
                is_active=True
            )
            recipients = [primary]
        else:
            logger.warning("send_morning_reports: No active morning report recipients configured.")
            return {'status': 'no_recipients', 'count': 0, 'success': 0, 'failed': 0}

    logger.info(f"Generating morning report (today) for {len(recipients)} recipients...")
    report_text = get_today_report()

    results = []
    success_count = 0
    fail_count = 0

    for rec in recipients:
        phone = rec.phone
        ok, err = send_whatsapp_chunks(phone, report_text)
        if ok:
            success_count += 1
            results.append({'phone': phone, 'name': rec.name, 'status': 'sent'})
        else:
            fail_count += 1
            results.append({'phone': phone, 'name': rec.name, 'status': 'failed', 'error': err})

    return {
        'status': 'completed',
        'count': len(recipients),
        'success': success_count,
        'failed': fail_count,
        'details': results
    }


def send_evening_reports() -> dict:
    """
    Sends the evening 8 PM daily report (current day's figures to date)
    to all registered active recipients.
    """
    recipients = list(AdminReportRecipient.objects.filter(
        is_active=True,
        report_type__in=['evening', 'both']
    ))

    if not recipients:
        if not AdminReportRecipient.objects.exists():
            logger.info("send_evening_reports: No recipients found in database. Auto-seeding primary admin 9340547135...")
            primary = AdminReportRecipient.objects.create(
                name="Admin (Primary)",
                phone="9340547135",
                report_type="both",
                is_active=True
            )
            recipients = [primary]
        else:
            logger.warning("send_evening_reports: No active evening report recipients configured.")
            return {'status': 'no_recipients', 'count': 0, 'success': 0, 'failed': 0}

    logger.info(f"Generating evening report (today) for {len(recipients)} recipients...")
    report_text = get_today_report()

    results = []
    success_count = 0
    fail_count = 0

    for rec in recipients:
        phone = rec.phone
        ok, err = send_whatsapp_chunks(phone, report_text)
        if ok:
            success_count += 1
            results.append({'phone': phone, 'name': rec.name, 'status': 'sent'})
        else:
            fail_count += 1
            results.append({'phone': phone, 'name': rec.name, 'status': 'failed', 'error': err})

    return {
        'status': 'completed',
        'count': len(recipients),
        'success': success_count,
        'failed': fail_count,
        'details': results
    }


def send_test_report_to_number(phone_number: str, report_type: str = "today") -> tuple[bool, str]:
    """
    Test helper triggered from Admin CRM UI or management command.
    """
    if report_type == "yesterday":
        text = get_yesterday_report()
    elif report_type == "overall":
        text = get_overall_report()
    else:
        text = get_today_report()

    return send_whatsapp_chunks(phone_number, text)
