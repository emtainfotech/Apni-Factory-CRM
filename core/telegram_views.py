import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from core.services import telegram_service

logger = logging.getLogger(__name__)

@csrf_exempt
def telegram_webhook_view(request):
    """
    Webhook endpoint to receive updates directly from Telegram Bot API via HTTPS POST.
    """
    if request.method != 'POST':
        return HttpResponse("ApniFactory Telegram Webhook Endpoint Active.", content_type="text/plain")

    try:
        body = request.body.decode('utf-8')
        update = json.loads(body)

        # 1. Inline button click callback
        if 'callback_query' in update:
            cb = update['callback_query']
            cb_id = cb['id']
            data = cb.get('data', '')
            from_user = cb.get('from', {})
            admin_name = from_user.get('first_name', 'Admin')
            if from_user.get('username'):
                admin_name = f"@{from_user['username']}"

            if data.startswith('approve_login:') or data.startswith('reject_login:'):
                action, req_id = data.split(':')
                act_type = 'approve' if 'approve' in action else 'reject'
                success, msg_text = telegram_service.resolve_login_approval_callback(req_id, act_type, admin_name=admin_name)
                telegram_service.answer_callback_query(cb_id, text=msg_text, show_alert=True)

        # 2. Text Command
        elif 'message' in update and 'text' in update['message']:
            msg = update['message']
            chat_id = msg['chat']['id']
            text = msg.get('text', '').strip()
            command = text.split()[0].lower() if text else ''

            if command in ('/start', '/help'):
                welcome_msg = (
                    "👋 <b>Apni Factory Alert Bot is Active!</b>\n\n"
                    "• /status — Real-time system health\n"
                    "• /approvals — Pending employee logins\n"
                    "• /stats — Today's B2B leads & quotes"
                )
                telegram_service.send_message(welcome_msg, chat_id=chat_id, sync=True)

            elif command in ('/status', '/health'):
                health_msg = telegram_service.get_system_health_summary()
                telegram_service.send_message(health_msg, chat_id=chat_id, sync=True)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        logger.exception(f"Error handling Telegram webhook: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
