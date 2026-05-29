from django.urls import path
from . import views

app_name = 'employee_portal'

urlpatterns = [
    # Dashboard Home
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Attendance Controls
    path('attendance/', views.attendance_history, name='attendance_history'),
    path('attendance/punch-in/', views.punch_in, name='punch_in'),
    path('attendance/punch-out/', views.punch_out, name='punch_out'),
    path('attendance/toggle-break/', views.toggle_break, name='toggle_break'),
    path('attendance/apply-leave/', views.apply_leave, name='apply_leave'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('leads/kanban/', views.lead_kanban, name='lead_kanban'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/log-call/', views.log_call, name='log_call'),
    path('customers/<int:customer_id>/convert/', views.convert_lead, name='convert_lead'),
    
    # Orders (synced from hostinger)
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    
    # Invoices (marketing invoices)
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.create_invoice, name='create_invoice'),
    path('invoices/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:invoice_id>/finalize/', views.finalize_invoice, name='finalize_invoice'),
    path('invoices/<int:invoice_id>/pdf/', views.download_invoice_pdf, name='download_invoice_pdf'),
    path('invoices/<int:invoice_id>/send-email/', views.send_invoice_email, name='send_invoice_email'),
    path('invoices/<int:invoice_id>/send-whatsapp/', views.send_invoice_whatsapp, name='send_invoice_whatsapp'),
]
