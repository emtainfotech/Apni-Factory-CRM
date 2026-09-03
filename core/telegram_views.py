import json
import logging
import html
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from core.services import telegram_service
from core.models import LoginApprovalRequest

logger = logging.getLogger(__name__)

@csrf_exempt
def telegram_webhook_view(request):
    """
    Webhook endpoint to receive updates directly from Telegram Bot API via HTTPS POST.
    URL: https://crm.apnifactory.co.in/api/telegram/webhook/
    """
    if request.method != 'POST':
        return HttpResponse("ApniFactory Telegram Webhook Active. Send POST updates from Telegram.", content_type="text/plain")

    try:
        body = request.body.decode('utf-8')
        update = json.loads(body)

        # 1. Inline Button Click (Callback Query)
        if 'callback_query' in update:
            cb = update['callback_query']
            cb_id = cb['id']
            data = cb.get('data', '')
            from_user = cb.get('from', {})
            admin_name = from_user.get('first_name', 'Admin')
            if from_user.get('username'):
                admin_name = f"@{from_user['username']}"

            message = cb.get('message', {})
            message_id = message.get('message_id')
            chat_id = message.get('chat', {}).get('id')

            if data.startswith('approve_login:') or data.startswith('reject_login:'):
                action, req_id = data.split(':')
                act_type = 'approve' if 'approve' in action else 'reject'
                success, msg_text = telegram_service.resolve_login_approval_callback(req_id, act_type, admin_name=admin_name)
                
                # Acknowledge popup to user
                telegram_service.answer_callback_query(cb_id, text=msg_text, show_alert=True)

                # Update message card
                if message_id and chat_id:
                    orig_text = message.get('text', '')
                    status_header = "✅ <b>LOGIN APPROVED</b>" if act_type == 'approve' else "❌ <b>LOGIN REJECTED</b>"
                    updated_text = (
                        f"{status_header}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{html.escape(orig_text)}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>Resolved by:</b> {html.escape(admin_name)}\n"
                        f"⏰ <b>At:</b> <code>{timezone.localtime().strftime('%I:%M:%S %p')}</code>"
                    )
                    telegram_service.edit_message_text(updated_text, message_id=message_id, chat_id=chat_id)

        # 2. Text Command
        elif 'message' in update and 'text' in update['message']:
            msg = update['message']
            chat_id = msg['chat']['id']
            text = msg.get('text', '').strip()
            from_user = msg.get('from', {})
            first_name = from_user.get('first_name', 'Admin')
            command = text.split()[0].lower() if text else ''

            if command in ('/start', '/help'):
                welcome_msg = (
                    f"👋 <b>Welcome, {html.escape(first_name)}!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🤖 <b>Apni Factory Central Alert & Support Bot</b>\n"
                    f"I monitor both <b>ApniFactory CRM</b> & <b>Website</b> to send instant alerts and handle actions.\n\n"
                    f"📋 <b>Available Commands:</b>\n"
                    f"• ⚡ <code>/status</code> or <code>/health</code> — Check real-time system health & metrics\n"
                    f"• 🔐 <code>/approvals</code> — List and approve pending employee logins\n"
                    f"• 📊 <code>/stats</code> — Today's B2B leads, quotes & customer activity\n"
                    f"• 🏓 <code>/ping</code> — Test bot responsiveness\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔔 <i>You will automatically receive alerts for 500 server errors, login approvals, and customer quote requests.</i>"
                )
                telegram_service.send_message(welcome_msg, chat_id=chat_id, sync=True)

            elif command in ('/status', '/health'):
                health_msg = telegram_service.get_system_health_summary()
                telegram_service.send_message(health_msg, chat_id=chat_id, sync=True)

            elif command == '/approvals':
                pending_requests = LoginApprovalRequest.objects.filter(status='pending').select_related('user').order_by('-created_at')[:10]
                if not pending_requests.exists():
                    telegram_service.send_message("✅ <b>No pending employee login approvals right now!</b>", chat_id=chat_id, sync=True)
                else:
                    telegram_service.send_message(f"🔐 <b>Found {pending_requests.count()} Pending Login Request(s):</b>", chat_id=chat_id, sync=True)
                    for req in pending_requests:
                        user = req.user
                        user_name = user.get_full_name() or user.username
                        time_str = timezone.localtime(req.created_at).strftime('%d %b, %I:%M %p')
                        card_text = (
                            f"👤 <b>Employee:</b> {html.escape(user_name)} (@{html.escape(user.username)})\n"
                            f"🌐 <b>IP:</b> <code>{html.escape(req.ip_address or 'Unknown')}</code>\n"
                            f"⏰ <b>Time:</b> {time_str}"
                        )
                        keyboard = {
                            'inline_keyboard': [
                                [
                                    {'text': '✅ Approve', 'callback_data': f'approve_login:{req.id}'},
                                    {'text': '❌ Reject', 'callback_data': f'reject_login:{req.id}'}
                                ],
                                [
                                    {'text': '🔗 1-Click Approve (Web)', 'url': f'https://crm.apnifactory.co.in/api/telegram/quick-approve/{req.id}/?action=approve'}
                                ]
                            ]
                        }
                        telegram_service.send_message(card_text, reply_markup=keyboard, chat_id=chat_id, sync=True)

            elif command == '/ping':
                telegram_service.send_message("🏓 <b>Pong!</b> ApniFactory Webhook Bot is online.", chat_id=chat_id, sync=True)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        logger.exception(f"Error handling Telegram webhook: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def quick_approve_view(request, request_id):
    """
    Direct 1-Click Web Approval Endpoint.
    Allows admins to tap a link in Telegram to authorize an employee login directly from any browser.
    URL: /api/telegram/quick-approve/<request_id>/?action=approve|reject
    """
    action = request.GET.get('action', 'approve').lower()
    act_type = 'approve' if action == 'approve' else 'reject'

    success, msg = telegram_service.resolve_login_approval_callback(
        request_id=request_id,
        action=act_type,
        admin_name="Admin (1-Click Link)"
    )

    try:
        login_req = LoginApprovalRequest.objects.select_related('user').get(id=request_id)
        user_name = login_req.user.get_full_name() or login_req.user.username
        ip_addr = login_req.ip_address
        status_now = login_req.status.upper()
    except Exception:
        user_name = "Employee"
        ip_addr = "N/A"
        status_now = "UNKNOWN"

    is_approved = (status_now == 'APPROVED')
    theme_color = "#16a34a" if is_approved else ("#dc2626" if status_now == 'REJECTED' else "#d97706")
    icon = "✅" if is_approved else ("❌" if status_now == 'REJECTED' else "⚠️")
    title = f"Login {status_now}"

    html_resp = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Apni Factory CRM</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background: #0f172a;
            color: #f1f5f9;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }}
        .card {{
            background: #1e293b;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 36px 28px;
            max-width: 440px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
        }}
        .badge-icon {{
            font-size: 3rem;
            margin-bottom: 12px;
            display: inline-block;
        }}
        h2 {{
            color: {theme_color};
            margin: 0 0 8px 0;
            font-weight: 800;
        }}
        p.subtitle {{
            color: #94a3b8;
            font-size: 0.95rem;
            margin: 0 0 24px 0;
        }}
        .info-box {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 16px;
            text-align: left;
            margin-bottom: 24px;
            font-size: 0.88rem;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .info-row:last-child {{
            margin-bottom: 0;
        }}
        .label {{
            color: #64748b;
        }}
        .val {{
            font-weight: 600;
            color: #e2e8f0;
        }}
        .btn {{
            display: inline-block;
            width: 100%;
            padding: 12px;
            background: #2563eb;
            color: #fff;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 700;
            font-size: 0.95rem;
            box-sizing: border-box;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: #1d4ed8;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge-icon">{icon}</div>
        <h2>{title}</h2>
        <p class="subtitle">{msg}</p>

        <div class="info-box">
            <div class="info-row">
                <span class="label">Employee:</span>
                <span class="val">{html.escape(user_name)}</span>
            </div>
            <div class="info-row">
                <span class="label">IP Address:</span>
                <span class="val"><code>{html.escape(ip_addr)}</code></span>
            </div>
            <div class="info-row">
                <span class="label">Status:</span>
                <span class="val" style="color: {theme_color};">{status_now}</span>
            </div>
            <div class="info-row">
                <span class="label">Time:</span>
                <span class="val">{timezone.localtime().strftime('%I:%M:%S %p')}</span>
            </div>
        </div>

        <a href="/dashboard/admin/" class="btn">Open CRM Admin Dashboard →</a>
    </div>
</body>
</html>"""

    return HttpResponse(html_resp, content_type="text/html")
