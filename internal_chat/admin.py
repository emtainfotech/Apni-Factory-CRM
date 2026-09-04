from django.contrib import admin
from .models import ChatRoom, ChatMessage, UserPresence


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['id', '__str__', 'room_type', 'created_by', 'created_at', 'updated_at']
    list_filter = ['room_type']
    filter_horizontal = ['members']
    search_fields = ['name', 'members__username']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'room', 'sender', 'content_preview', 'timestamp', 'is_deleted']
    list_filter = ['is_deleted', 'room__room_type']
    search_fields = ['content', 'sender__username', 'room__name']
    readonly_fields = ['timestamp']

    def content_preview(self, obj):
        return obj.content[:60] if obj.content else '(attachment)'
    content_preview.short_description = 'Content'


@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_online', 'last_seen']
    list_filter = ['is_online']
