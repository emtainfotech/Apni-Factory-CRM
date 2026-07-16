from django.urls import path
from . import views
from . import gst_api_view
from . import api_views
from . import mobile_api_views

urlpatterns = [
    path('dashboard/admin/', views.admin_dashboard, name='dashboard_admin'),
    path('dashboard/manager/', views.manager_dashboard, name='dashboard_manager'),
    path('dashboard/agent/', views.agent_dashboard, name='dashboard_agent'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_crm_user, name='create_crm_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('users/<int:user_id>/profile/', views.user_detail, name='user_detail'),
    path('profile/', views.user_profile, name='user_profile'),
    path('notifications/get/', views.get_notifications, name='get_notifications'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('notifications/history/', views.notification_history, name='notification_history'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/upload/', views.bulk_upload_customers, name='bulk_upload_customers'),
    path('customers/download-sample/', views.download_sample_file, name='download_sample_file'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/log-call/', views.log_call, name='log_call'),
    path('customers/<int:customer_id>/convert/', views.convert_lead, name='convert_lead'),
    path('customers/<int:customer_id>/update-status/', views.update_customer_status, name='update_customer_status'),
    path('leads/kanban/', views.lead_kanban, name='lead_kanban'),
    path('global-search/', views.global_search, name='global_search'),
    path('dashboard/admin/manage-leaves/', views.manage_leaves, name='manage_leaves'),
    path('dashboard/admin/approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('dashboard/admin/reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),
    path('dashboard/admin/whatsapp-marketing/', views.whatsapp_marketing, name='whatsapp_marketing'),
    path('dashboard/admin/whatsapp-marketing/sample/', views.whatsapp_marketing_sample, name='whatsapp_marketing_sample'),
    
    # Order Routes
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('products/', views.product_list, name='product_list'),

    # App Database Routes
    path('app-db/sellers/', views.app_user_list, name='app_user_list'),
    path('app-db/buyers/', views.app_customer_list, name='app_customer_list'),
    path('app-db/sellers/<int:user_id>/', views.app_user_detail, name='app_user_detail'),
    path('app-db/buyers/<int:customer_id>/', views.app_customer_detail, name='app_customer_detail'),
    path('banners/', views.banner_list, name='banner_list'),
    path('banners/add/', views.add_banner, name='add_banner'),
    path('banners/<int:banner_id>/edit/', views.edit_banner, name='edit_banner'),
    path('sliders/', views.slider_list, name='slider_list'),
    path('sliders/add/', views.add_slider, name='add_slider'),
    path('sliders/<int:slider_id>/edit/', views.edit_slider, name='edit_slider'),

    path('categories/', views.app_category_list, name='app_category_list'),
    path('categories/main/<int:main_category_id>/', views.app_category_detail, name='app_category_detail'),
    path('categories/category/<int:category_id>/', views.app_subcategory_list, name='app_subcategory_list'),
    path('brands/', views.app_brand_list, name='app_brand_list'),
    path('companies/', views.app_company_list, name='app_company_list'),
    path('support/tickets/', views.app_ticket_list, name='app_ticket_list'),
    path('wallet/transactions/', views.app_wallet_transactions, name='app_wallet_list'),
    path('faqs/', views.app_faq_list, name='app_faq_list'),

    # Invoice Routes
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.create_invoice, name='create_invoice'),
    path('invoices/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:invoice_id>/finalize/', views.finalize_invoice, name='finalize_invoice'),
    path('invoices/<int:invoice_id>/pdf/', views.download_invoice_pdf, name='download_invoice_pdf'),
    path('invoices/<int:invoice_id>/send-email/', views.send_invoice_email, name='send_invoice_email'),
    path('invoices/<int:invoice_id>/send-whatsapp/', views.send_invoice_whatsapp, name='send_invoice_whatsapp'),
    path('settings/tracking/', views.tracking_dashboard, name='tracking_dashboard'),

    path('api/cities/', views.api_get_cities, name='api_get_cities'),
    path('api/pincode-details/', views.api_get_pincode_details, name='api_get_pincode_details'),
    path('api/city-pincodes/', views.api_get_pincodes_for_city, name='api_get_pincodes_for_city'),
    path('core-verify/', gst_api_view.gst_verify_view, name='core_verify'),
    path('verify-gst/', views.verify_gst_ajax, name='verify_gst_ajax'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('whatsapp/inbox/', views.whatsapp_inbox, name='whatsapp_inbox'),
    path('whatsapp/chat/<int:customer_id>/', views.get_whatsapp_chat, name='get_whatsapp_chat'),
    path('whatsapp/send/<int:customer_id>/', views.send_whatsapp_message_ajax, name='send_whatsapp_message_ajax'),
    path('api/login/', api_views.app_login),
    path('api/check-number/', api_views.check_number),
    path('api/save-log/', api_views.save_call_log),
    path('api/my-customers/', api_views.my_customers),
    path('api/customer-detail/<int:customer_id>/', api_views.get_customer_detail),
    path('api/mobile/gst-check/', mobile_api_views.mobile_gst_check, name='mobile_gst_check'), ## Mobile Application API end Points
]