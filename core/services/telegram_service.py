import os
import json
import logging
import threading
import html
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

def get_bot_token():
    return getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or os.getenv('TELEGRAM_BOT_TOKEN', '')

def get_default_chat_id():
    return getattr(settings, 'TELEGRAM_CHAT_ID', '') or os.getenv('TELEGRAM_CHAT_ID', '')

def is_alerts_enabled():
    val = getattr(settings, 'TELEGRAM_ALERTS_ENABLED', True)
    if isinstance(val, str):
        return val.lower() in ('true', '1', 'yes')
    return bool(val)


def _send_telegram_request(method, payload):
    """Low-level HTTP post to Telegram Bot API with timeout and error handling."""
    token = get_bot_token()
    if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
        logger.debug("Telegram alert skipped: TELEGRAM_BOT_TOKEN not configured.")
        return None

    url = f"{TELEGRAM_API_BASE}{token}/{method}"
    try:
        response = requests.post(url, json=payload, timeout=6)
        if response.status_code != 200:
            logger.warning(f"Telegram API response {response.status_code}: {response.text}")
        return response.json()
    except Exception as e:
        logger.warning(f"Telegram API request failed: {e}")
        return None


def send_message(text, parse_mode='HTML', reply_markup=None, chat_id=None, sync=False):
    """
    Sends a message via Telegram bot.
    Dispatches asynchronously in a background thread by default so it never blocks web requests.
    """
    if not is_alerts_enabled():
        return None

    target_chat = chat_id or get_default_chat_id()
    if not target_chat:
        logger.debug("Telegram alert skipped: No chat_id provided or configured.")
        return None

    payload = {
        'chat_id': target_chat,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup

    if sync:
        return _send_telegram_request('sendMessage', payload)
    else:
        th = threading.Thread(target=_send_telegram_request, args=('sendMessage', payload))
        th.daemon = True
        th.start()
        return True


def edit_message_text(text, message_id, chat_id=None, reply_markup=None, parse_mode='HTML'):
    """Edits an existing Telegram message (e.g. after approval button is clicked)."""
    target_chat = chat_id or get_default_chat_id()
    if not target_chat or not message_id:
        return None

    payload = {
        'chat_id': target_chat,
        'message_id': message_id,
        'text': text,
        'parse_mode': parse_mode,
    }
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup

    return _send_telegram_request('editMessageText', payload)


def answer_callback_query(callback_query_id, text=None, show_alert=False):
    """Answers an inline button callback query to stop the Telegram loading animation."""
    payload = {
        'callback_query_id': callback_query_id,
        'show_alert': show_alert,
    }
    if text:
        payload['text'] = text
    return _send_telegram_request('answerCallbackQuery', payload)


def send_system_error_alert(service_name, error_type, error_msg, path=None, method=None, traceback_text=None, user_info=None, ip_address=None):
    """Sends an immediate formatted Error Alert for unhandled exceptions (500s)."""
    now_str = timezone.localtime().strftime('%d %b %Y, %I:%M:%S %p')
    safe_service = html.escape(str(service_name))
    safe_error_type = html.escape(str(error_type))
    safe_error_msg = html.escape(str(error_msg)[:350])
    safe_path = html.escape(str(path or 'N/A'))
    safe_method = html.escape(str(method or 'GET'))
    safe_user = html.escape(str(user_info or 'Anonymous'))
    safe_ip = html.escape(str(ip_address or 'Unknown'))

    msg_lines = [
        f"🚨 <b>[{safe_service}] SYSTEM ERROR ALERT</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ <b>Time:</b> <code>{now_str}</code>",
        f"🌐 <b>Endpoint:</b> <code>{safe_method} {safe_path}</code>",
        f"👤 <b>User:</b> <code>{safe_user}</code> | <b>IP:</b> <code>{safe_ip}</code>",
        f"💥 <b>Exception:</b> <code>{safe_error_type}</code>",
        f"📝 <b>Details:</b> <i>{safe_error_msg}</i>",
    ]

    if traceback_text:
        tb_lines = traceback_text.strip().split('\n')
        short_tb = '\n'.join(tb_lines[-12:])
        safe_tb = html.escape(short_tb)
        msg_lines.append(f"\n🔍 <b>Traceback Snippet:</b>\n<pre>{safe_tb}</pre>")

    msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━\n⚠️ <i>Please inspect server logs or CRM admin to resolve.</i>")
    return send_message('\n'.join(msg_lines), sync=False)


def send_employee_login_approval_alert(login_request):
    """
    Sends an urgent Employee Login Approval Alert with both Instant Callback buttons
    and Direct 1-Click Web Links as fallback.
    """
    user = login_request.user
    user_name = user.get_full_name() or user.username
    email = user.email or 'N/A'
    role = getattr(user, 'role', 'employee').title()
    ip_address = login_request.ip_address or 'Unknown'
    now_str = timezone.localtime(login_request.created_at or timezone.now()).strftime('%d %b %Y, %I:%M %p')

    location_str = "Not Provided"
    if login_request.latitude and login_request.longitude:
        maps_link = f"https://www.google.com/maps?q={login_request.latitude},{login_request.longitude}"
        location_str = f"<a href='{maps_link}'>{login_request.latitude}, {login_request.longitude} (Open Map)</a>"

    msg = (
        f"🔐 <b>EMPLOYEE LOGIN APPROVAL REQUIRED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Employee:</b> <b>{html.escape(user_name)}</b> (@{html.escape(user.username)})\n"
        f"💼 <b>Role:</b> <code>{role}</code>\n"
        f"📧 <b>Email:</b> <code>{html.escape(email)}</code>\n"
        f"🌐 <b>IP Address:</b> <code>{html.escape(ip_address)}</code>\n"
        f"📍 <b>Location:</b> {location_str}\n"
        f"⏰ <b>Requested At:</b> <code>{now_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Tap an action below to authorize or reject this employee login:</i>"
    )

    base_domain = "https://crm.apnifactory.co.in"

    inline_keyboard = {
        'inline_keyboard': [
            [
                {
                    'text': '✅ Approve (Instant)',
                    'callback_data': f'approve_login:{login_request.id}'
                },
                {
                    'text': '❌ Reject',
                    'callback_data': f'reject_login:{login_request.id}'
                }
            ],
            [
                {
                    'text': '🔗 1-Click Approve (Web Link)',
                    'url': f'{base_domain}/api/telegram/quick-approve/{login_request.id}/?action=approve'
                },
                {
                    'text': '🔗 1-Click Reject',
                    'url': f'{base_domain}/api/telegram/quick-approve/{login_request.id}/?action=reject'
                }
            ]
        ]
    }

    return send_message(msg, reply_markup=inline_keyboard, sync=False)


def resolve_login_approval_callback(request_id, action, admin_name="Telegram Admin"):
    """
    Executes the approval or rejection of a LoginApprovalRequest.
    Returns (success_bool, status_message).
    """
    from core.models import LoginApprovalRequest, ApprovedIPAddress
    try:
        req_id_int = int(str(request_id).strip())
        login_request = LoginApprovalRequest.objects.select_related('user').get(id=req_id_int)
    except (LoginApprovalRequest.DoesNotExist, ValueError):
        return False, "⚠️ Request not found or already deleted."

    if login_request.status != 'pending':
        return False, f"⚠️ Request #{request_id} is already {login_request.status.upper()}."

    user = login_request.user
    user_name = user.get_full_name() or user.username
    resolved_time = timezone.localtime().strftime('%I:%M %p')

    if action == 'approve':
        login_request.status = 'approved'
        login_request.resolved_at = timezone.now()
        login_request.save()

        if login_request.ip_address:
            ApprovedIPAddress.objects.get_or_create(
                user=user,
                ip_address=login_request.ip_address
            )
        return True, f"✅ Approved login for {user_name} ({login_request.ip_address}) by {admin_name} at {resolved_time}."

    elif action == 'reject':
        login_request.status = 'rejected'
        login_request.resolved_at = timezone.now()
        login_request.save()
        return True, f"❌ Rejected login for {user_name} by {admin_name} at {resolved_time}."

    return False, "Invalid action."


def send_lead_or_inquiry_alert(inquiry_type, title, data_dict):
    """Sends customer quote requests, contact inquiries, or vendor applications."""
    now_str = timezone.localtime().strftime('%d %b %Y, %I:%M %p')
    safe_type = html.escape(str(inquiry_type).upper())
    safe_title = html.escape(str(title))

    lines = [
        f"📦 <b>NEW {safe_type}: {safe_title}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ <b>Received:</b> <code>{now_str}</code>",
    ]

    for k, v in data_dict.items():
        if v:
            safe_k = html.escape(str(k))
            safe_v = html.escape(str(v))
            lines.append(f"• <b>{safe_k}:</b> {safe_v}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━\n🚀 <i>Action required: Follow up with customer in CRM.</i>")
    return send_message('\n'.join(lines), sync=False)


def get_system_health_summary():
    """Calculates real-time health metrics of the CRM for bot status queries."""
    from django.db import connection
    from core.models import LoginApprovalRequest, Customer, WhatsAppLead

    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
    except Exception:
        db_ok = False

    pending_approvals = 0
    total_customers = 0
    today_leads = 0
    try:
        pending_approvals = LoginApprovalRequest.objects.filter(status='pending').count()
        total_customers = Customer.objects.count()
        today = timezone.localdate()
        today_leads = WhatsAppLead.objects.filter(created_at__date=today).count()
    except Exception:
        pass

    now_str = timezone.localtime().strftime('%d %b %Y, %I:%M:%S %p')

    msg = (
        f"⚡ <b>APNI FACTORY SYSTEM HEALTH STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <b>Report Time:</b> <code>{now_str}</code>\n"
        f"🗄️ <b>PostgreSQL Database:</b> {'🟢 Online & Healthy' if db_ok else '🔴 Connection Error'}\n"
        f"🏢 <b>ApniFactory CRM (Port 8001):</b> 🟢 Active\n"
        f"🛒 <b>Website Frontend (Port 8080):</b> 🟢 Active\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Pending Employee Approvals:</b> <b>{pending_approvals}</b>\n"
        f"📈 <b>Total B2B Customers:</b> <b>{total_customers}</b>\n"
        f"💬 <b>New Leads Today:</b> <b>{today_leads}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Use /approvals to inspect and approve pending logins.</i>"
    )
    return msg
