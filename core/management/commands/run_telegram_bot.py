import time
import logging
import requests
import html
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.services import telegram_service
from core.models import LoginApprovalRequest

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Runs the interactive Telegram Bot polling daemon for ApniFactory CRM & Website alerts and approvals."

    def handle(self, *args, **options):
        token = telegram_service.get_bot_token()
        if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not configured in settings or .env."))
            self.stderr.write(self.style.WARNING("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to run the bot daemon."))
            return

        self.stdout.write(self.style.SUCCESS("Starting ApniFactory Telegram Bot daemon (polling mode)..."))
        
        # 1. Reset any existing webhook on startup to ensure getUpdates polling works cleanly
        try:
            requests.post(f"{telegram_service.TELEGRAM_API_BASE}{token}/deleteWebhook", json={'drop_pending_updates': False}, timeout=10)
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("ApniFactory Bot is ACTIVE & LISTENING for commands and button clicks!"))
        self.stdout.write(self.style.SUCCESS("Available commands: /status, /approvals, /health, /stats, /ping, /help"))

        offset = None
        url = f"{telegram_service.TELEGRAM_API_BASE}{token}/getUpdates"

        while True:
            try:
                params = {'timeout': 20}
                if offset:
                    params['offset'] = offset

                resp = requests.get(url, params=params, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get('result', []):
                        offset = update['update_id'] + 1
                        self.process_update(update)
                elif resp.status_code == 409:
                    self.stderr.write(
                        self.style.WARNING(
                            "Telegram returned 409 Conflict: Another instance of this bot is currently running. "
                            "Retrying in 5 seconds (only 1 instance can poll at a time)..."
                        )
                    )
                    time.sleep(5)
                else:
                    self.stderr.write(f"Telegram getUpdates returned {resp.status_code}: {resp.text}")
                    time.sleep(3)
            except requests.exceptions.RequestException as e:
                self.stderr.write(f"Network error in bot polling: {e}")
                time.sleep(5)
            except Exception as e:
                self.stderr.write(f"Unexpected error in bot polling: {e}")
                time.sleep(3)

    def process_update(self, update):
        # 1. Handle Inline Button Clicks (Callback Queries)
        if 'callback_query' in update:
            self.handle_callback_query(update['callback_query'])
            return

        # 2. Handle Text Messages & Commands
        if 'message' in update and 'text' in update['message']:
            self.handle_text_message(update['message'])

    def handle_text_message(self, message):
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        user_info = message.get('from', {})
        first_name = user_info.get('first_name', 'Admin')

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
                return

            telegram_service.send_message(
                f"🔐 <b>Found {pending_requests.count()} Pending Login Request(s):</b>",
                chat_id=chat_id,
                sync=True
            )

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
                        ]
                    ]
                }
                telegram_service.send_message(card_text, reply_markup=keyboard, chat_id=chat_id, sync=True)

        elif command == '/stats':
            from core.models import Customer, WhatsAppLead
            today = timezone.localdate()
            today_leads = WhatsAppLead.objects.filter(created_at__date=today).count()
            total_customers = Customer.objects.count()
            pending_approvals = LoginApprovalRequest.objects.filter(status='pending').count()

            stats_msg = (
                f"📊 <b>APNI FACTORY DAILY STATS SUMMARY</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 <b>Date:</b> <code>{today.strftime('%d %B %Y')}</code>\n"
                f"👥 <b>Total Customers in CRM:</b> <b>{total_customers}</b>\n"
                f"💬 <b>New WhatsApp Leads Today:</b> <b>{today_leads}</b>\n"
                f"🔐 <b>Pending Login Approvals:</b> <b>{pending_approvals}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚀 <i>Everything is running smoothly.</i>"
            )
            telegram_service.send_message(stats_msg, chat_id=chat_id, sync=True)

        elif command == '/ping':
            telegram_service.send_message("🏓 <b>Pong!</b> ApniFactory Bot is online and listening.", chat_id=chat_id, sync=True)

    def handle_callback_query(self, cb):
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

            # Acknowledge callback popup
            telegram_service.answer_callback_query(cb_id, text=msg_text, show_alert=True)

            # Update the original Telegram message to reflect resolution
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
