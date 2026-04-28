from django.urls import path
from . import views
from . import gst_api_view
from . import api_views
from . import mobile_api_views

urlpatterns = [
    path('dashboard/admin/', views.admin_dashboard, name='dashboard_admin'),
    path('dashboard/manager/', views.manager_dashboard, name='dashboard_manager'),
    path('dashboard/employee/', views.employee_dashboard, name='dashboard_employee'),
    path('dashboard/agent/', views.agent_dashboard, name='dashboard_agent'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_crm_user, name='create_crm_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('users/<int:user_id>/profile/', views.user_detail, name='user_detail'),
    path('notifications/get/', views.get_notifications, name='get_notifications'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('notifications/history/', views.notification_history, name='notification_history'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/upload/', views.bulk_upload_customers, name='bulk_upload_customers'),
    path('customers/download-sample/', views.download_sample_file, name='download_sample_file'),
    path('customers/<int:customer_id>/', views.customer_profile, name='customer_profile'),
    path('api/cities/', views.api_get_cities, name='api_get_cities'),
    path('api/pincode-details/', views.api_get_pincode_details, name='api_get_pincode_details'),
    path('api/city-pincodes/', views.api_get_pincodes_for_city, name='api_get_pincodes_for_city'),
    path('core-verify/', gst_api_view.gst_verify_view, name='core_verify'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('api/login/', api_views.app_login),
    path('api/check-number/', api_views.check_number),
    path('api/save-log/', api_views.save_call_log),
    path('api/my-customers/', api_views.my_customers),
    path('api/customer-detail/<int:customer_id>/', api_views.get_customer_detail),
    path('api/mobile/gst-check/', mobile_api_views.mobile_gst_check, name='mobile_gst_check'), ## Mobile Application API end Points
]