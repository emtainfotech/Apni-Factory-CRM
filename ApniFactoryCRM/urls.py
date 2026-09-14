"""
URL configuration for ApniFactoryCRM project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

from core.views import health_check, check_new_notifications


from core import telegram_views

def whatsapp_root_redirect(request):
    """
    Intelligently routes /whatsapp/inbox/ and /whatsapp/ to:
    - /employee/whatsapp/ for logged-in employees
    - /core/whatsapp/inbox/ for admins/managers
    Preserves all query strings (e.g. ?customer_id=447).
    """
    query = request.GET.urlencode()
    query_str = f"?{query}" if query else ""
    if request.user.is_authenticated and getattr(request.user, 'role', '') == 'employee' and not request.user.is_superuser:
        return redirect(f"/employee/whatsapp/{query_str}")
    return redirect(f"/core/whatsapp/inbox/{query_str}")

urlpatterns = [
    path('whatsapp/inbox/', whatsapp_root_redirect, name='root_whatsapp_inbox'),
    path('whatsapp/', whatsapp_root_redirect, name='root_whatsapp'),
    path('notifications/check-new/', check_new_notifications, name='root_check_new_notifications'),
    path('api/telegram/webhook/', telegram_views.telegram_webhook_view, name='telegram_webhook'),
    path('api/telegram/quick-approve/<int:request_id>/', telegram_views.quick_approve_view, name='telegram_quick_approve'),

    path('health/', health_check, name='health_check'),
    path('', lambda request: redirect('dashboard_admin', permanent=False)),
    path('authentication/', include('authentication.urls')),
    path('core/', include('core.urls')),
    path('employee/', include('employee_portal.urls')),
    path('vendor-network/', include('vendor_network.urls')),
    path('chat/', include('internal_chat.urls', namespace='internal_chat')),
    path('api/v1/', include('api.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve media files in production as well for WhatsApp attachments
from django.views.static import serve
from django.urls import re_path
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

