from django.urls import path
from . import views

app_name = 'internal_chat'

urlpatterns = [
    path('', views.chat_home, name='chat_home'),
    path('dm/<int:user_id>/', views.start_direct_chat, name='start_direct_chat'),
    path('group/create/', views.create_group_room, name='create_group_room'),
    path('<int:room_id>/messages/', views.get_messages, name='get_messages'),
    path('<int:room_id>/send/', views.send_message, name='send_message'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('rooms/', views.get_rooms_list, name='get_rooms_list'),
    path('presence/update/', views.update_presence, name='update_presence'),
    path('presence/', views.get_presence, name='get_presence'),
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('admin/', views.admin_monitor, name='admin_monitor'),
]
