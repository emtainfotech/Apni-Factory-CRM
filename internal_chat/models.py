from django.db import models
from django.conf import settings
from django.utils import timezone


class ChatRoom(models.Model):
    """
    Represents a conversation — either a 1-on-1 Direct Message or a Group chat.
    """
    DIRECT = 'direct'
    GROUP = 'group'
    ROOM_TYPE_CHOICES = [
        (DIRECT, 'Direct Message'),
        (GROUP, 'Group Chat'),
    ]

    name = models.CharField(max_length=100, blank=True, null=True, help_text="Only for group chats")
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES, default=DIRECT)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_rooms'
    )
    avatar = models.ImageField(upload_to='chat/room_avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        if self.room_type == self.DIRECT:
            members = list(self.members.all())
            if len(members) >= 2:
                return f"DM: {members[0].get_full_name() or members[0].username} ↔ {members[1].get_full_name() or members[1].username}"
        return self.name or f"Room #{self.pk}"

    def get_display_name(self, for_user):
        """Returns room name as seen by a specific user (DM shows other person's name)."""
        if self.room_type == self.DIRECT:
            other = self.members.exclude(pk=for_user.pk).first()
            if other:
                return other.get_full_name() or other.username
        return self.name or f"Group Room #{self.pk}"

    def get_other_member(self, user):
        """For DM rooms, returns the other participant."""
        return self.members.exclude(pk=user.pk).first()

    def unread_count(self, user):
        """Count unread messages for a given user."""
        return self.messages.exclude(sender=user).exclude(read_by=user).count()

    def last_message(self):
        return self.messages.order_by('-timestamp').first()

    @classmethod
    def get_or_create_direct_room(cls, user1, user2):
        """Gets or creates a direct message room between exactly two users."""
        # Find existing DM room with both users
        rooms = cls.objects.filter(
            room_type=cls.DIRECT,
            members=user1
        ).filter(members=user2)
        for room in rooms:
            if room.members.count() == 2:
                return room, False
        # Create new DM room
        room = cls.objects.create(room_type=cls.DIRECT)
        room.members.add(user1, user2)
        return room, True


class ChatMessage(models.Model):
    """An individual message in a ChatRoom."""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_chat_messages'
    )
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to='chat/attachments/', null=True, blank=True)
    attachment_type = models.CharField(max_length=50, null=True, blank=True)  # image, file, audio
    attachment_name = models.CharField(max_length=255, null=True, blank=True)

    # Read receipts — who has seen this message
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='read_chat_messages', blank=True
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)  # soft delete

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.room}] {self.sender.username}: {self.content[:50]}"

    def to_dict(self, current_user=None):
        """Serialize for JSON API response."""
        sender_name = self.sender.get_full_name() or self.sender.username
        data = {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': sender_name,
            'sender_initials': sender_name[:2].upper(),
            'sender_role': getattr(self.sender, 'role', 'employee'),
            'sender_is_superuser': self.sender.is_superuser,
            'content': self.content if not self.is_deleted else '🚫 This message was deleted.',
            'is_deleted': self.is_deleted,
            'timestamp': self.timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
            'time_display': self.timestamp.strftime('%I:%M %p'),
            'date_display': self.timestamp.strftime('%d %b %Y'),
            'is_own': (self.sender_id == current_user.pk) if current_user else False,
            'read_by_count': self.read_by.count(),
        }
        if self.attachment:
            data['attachment_url'] = self.attachment.url
            data['attachment_type'] = self.attachment_type or 'file'
            data['attachment_name'] = self.attachment_name or self.attachment.name.split('/')[-1]
        return data


class UserPresence(models.Model):
    """Tracks online/last-seen status for each user via heartbeat pings."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='presence'
    )
    last_seen = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"

    @classmethod
    def mark_online(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        obj.is_online = True
        obj.last_seen = timezone.now()
        obj.save(update_fields=['is_online', 'last_seen'])
        return obj

    @classmethod
    def get_online_user_ids(cls):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(seconds=30)
        return list(cls.objects.filter(last_seen__gte=cutoff).values_list('user_id', flat=True))
