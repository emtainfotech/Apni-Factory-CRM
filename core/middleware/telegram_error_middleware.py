import traceback
import logging
from django.utils.deprecation import MiddlewareMixin
from core.services import telegram_service

logger = logging.getLogger(__name__)

class TelegramErrorMiddleware(MiddlewareMixin):
    """
    Middleware that captures unhandled exceptions (500s) and automatically dispatches
    a formatted real-time alert to the configured Telegram chat/channel.
    """

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'Unknown')

    def process_exception(self, request, exception):
        try:
            # Ignore standard 404 Http404 or common non-500 redirects
            from django.http import Http404
            if isinstance(exception, Http404):
                return None

            user_str = "Anonymous"
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_str = f"{request.user.username} (ID: {request.user.id}, Role: {getattr(request.user, 'role', 'user')})"

            tb_str = traceback.format_exc()
            ip_addr = self.get_client_ip(request)

            telegram_service.send_system_error_alert(
                service_name="ApniFactory CRM",
                error_type=type(exception).__name__,
                error_msg=str(exception),
                path=request.get_full_path(),
                method=request.method,
                traceback_text=tb_str,
                user_info=user_str,
                ip_address=ip_addr
            )
        except Exception as e:
            logger.exception(f"TelegramErrorMiddleware failed to dispatch alert: {e}")

        # Let Django continue standard error processing
        return None
