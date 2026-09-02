from django.core.management.base import BaseCommand
from core.services import telegram_service

class Command(BaseCommand):
    help = "Sends a test alert message to verify Telegram Bot configuration."

    def handle(self, *args, **options):
        token = telegram_service.get_bot_token()
        chat_id = telegram_service.get_default_chat_id()

        self.stdout.write(f"TELEGRAM_BOT_TOKEN: {'Configured (' + token[:6] + '...)' if token else 'NOT CONFIGURED'}")
        self.stdout.write(f"TELEGRAM_CHAT_ID:   {chat_id if chat_id else 'NOT CONFIGURED'}")

        if not token or not chat_id:
            self.stderr.write(self.style.ERROR("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env or settings.py"))
            return

        self.stdout.write("Sending test message...")
        test_msg = (
            "🎉 <b>APNI FACTORY TELEGRAM BOT CONNECTED</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ Telegram alert integration is active and functioning!\n"
            "• Service: <b>ApniFactory CRM (Port 8001)</b>\n"
            "• Server Errors (500s) will be posted here in real-time.\n"
            "• Employee Login Approval requests will appear with 1-click action buttons.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Type /status or /help to interact with the bot.</i>"
        )
        res = telegram_service.send_message(test_msg, sync=True)
        if res and res.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"SUCCESS: Test message delivered to chat {chat_id}!"))
        else:
            self.stderr.write(self.style.ERROR(f"FAILED to send message: {res}"))
