import requests
from django.core.management.base import BaseCommand
from core.services import telegram_service

class Command(BaseCommand):
    help = "Sets up or removes Telegram Webhook for ApniFactory CRM."

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, default='https://crm.apnifactory.co.in/api/telegram/webhook/', help='Webhook URL')
        parser.add_argument('--delete', action='store_true', help='Delete the webhook (switch to polling mode)')
        parser.add_argument('--info', action='store_true', help='Show current webhook info')

    def handle(self, *args, **options):
        token = telegram_service.get_bot_token()
        if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not configured."))
            return

        api_base = f"{telegram_service.TELEGRAM_API_BASE}{token}"

        if options['delete']:
            res = requests.post(f"{api_base}/deleteWebhook", json={'drop_pending_updates': False}, timeout=10)
            self.stdout.write(self.style.SUCCESS(f"deleteWebhook result: {res.json()}"))
            return

        if options['info']:
            res = requests.get(f"{api_base}/getWebhookInfo", timeout=10)
            self.stdout.write(self.style.SUCCESS(f"Webhook Info: {res.json()}"))
            return

        webhook_url = options['url']
        self.stdout.write(f"Setting Telegram Webhook to: {webhook_url}")
        res = requests.post(f"{api_base}/setWebhook", json={'url': webhook_url, 'drop_pending_updates': False}, timeout=15)
        data = res.json()
        if data.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"SUCCESS: Telegram Webhook active! URL: {webhook_url}"))
        else:
            self.stderr.write(self.style.ERROR(f"FAILED to set webhook: {data}"))

        # Verify
        info_res = requests.get(f"{api_base}/getWebhookInfo", timeout=10)
        self.stdout.write(f"Current Webhook Info: {info_res.json()}")
