from django.urls import path
from . import views

app_name = 'internal_chat'

urlpatterns = [
    # Main chat page (dual-pane)
    path('', views.chat_home, name='chat_home'),

    # Start DM with a specific user
    path('dm/<int:user_id>/', views.start_direct_chat, name='start_direct_chat'),

    # Create group room
    path('group/create/', views.create_group_room, name='create_group_room'),

    # Message API (polling)
    path('<int:room_id>/messages/', views.get_messages, name='get_messages'),
    path('<int:room_id>/send/', views.send_message, name='send_message'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),

    # Rooms list for sidebar badge refresh
    path('rooms/', views.get_rooms_list, name='get_rooms_list'),

    # Presence
    path('presence/update/', views.update_presence, name='update_presence'),
    path('presence/', views.get_presence, name='get_presence'),

    # Admin monitor
    path('admin/', views.admin_monitor, name='admin_monitor'),
]
