import mimetypes

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ChatMessage, ChatRoom, UserPresence

User = get_user_model()


def is_admin_or_manager(user):
    return user.is_superuser or getattr(user, 'role', '') in ('admin', 'manager')


def get_base_template(user):
    """Return the right base template depending on user role."""
    if is_admin_or_manager(user):
        return 'core/base.html'
    return 'employee_portal/base.html'


def create_message_notification(message):
    """Create in-app notification for all room members except the sender."""
    try:
        from authentication.models import Notification
        room = message.room
        sender_name = message.sender.get_full_name() or message.sender.username
        preview = message.content[:60] if message.content else '📎 Attachment'
        room_name = room.get_display_name(message.sender)
        notif_msg = f"💬 {sender_name}: {preview}"
        url = f'/chat/?room={room.pk}'

        for member in room.members.exclude(pk=message.sender_id):
            Notification.objects.create(
                recipient=member,
                message=notif_msg,
                url=url,
            )
    except Exception as e:
        print(f"Notification creation error: {e}")


# ===========================================================================
# PRESENCE
# ===========================================================================

@login_required
def update_presence(request):
    UserPresence.mark_online(request.user)
    return JsonResponse({'status': 'ok', 'online': True})


@login_required
def get_presence(request):
    online_ids = UserPresence.get_online_user_ids()
    return JsonResponse({'online_user_ids': online_ids})


# ===========================================================================
# NOTIFICATIONS API
# ===========================================================================

@login_required
def get_notifications(request):
    """Returns unread in-app notifications for the current user."""
    try:
        from authentication.models import Notification
        notifs = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).order_by('-created_at')[:20]
        data = [{
            'id': n.pk,
            'message': n.message,
            'url': n.url or '/chat/',
            'created_at': n.created_at.strftime('%d %b, %I:%M %p') if n.created_at else '',
        } for n in notifs]
        return JsonResponse({'notifications': data, 'count': notifs.count()})
    except Exception as e:
        return JsonResponse({'notifications': [], 'count': 0})


@login_required
@require_POST
def mark_notifications_read(request):
    """Mark all chat notifications as read."""
    try:
        from authentication.models import Notification
        Notification.objects.filter(recipient=request.user, is_read=False, url__contains='/chat/').update(is_read=True)
    except Exception:
        pass
    return JsonResponse({'status': 'ok'})


# ===========================================================================
# MAIN CHAT HOME
# ===========================================================================

@login_required
def chat_home(request):
    UserPresence.mark_online(request.user)
    user = request.user

    rooms = ChatRoom.objects.filter(members=user).prefetch_related('members').order_by('-updated_at')

    room_data = []
    total_unread = 0
    online_ids = UserPresence.get_online_user_ids()
    for room in rooms:
        last_msg = room.last_message()
        unread = room.unread_count(user)
        total_unread += unread
        other = room.get_other_member(user) if room.room_type == ChatRoom.DIRECT else None
        room_data.append({
            'room': room,
            'display_name': room.get_display_name(user),
            'last_message': last_msg,
            'unread': unread,
            'other_user': other,
            'other_online': other.pk in online_ids if other else False,
        })

    all_users = User.objects.exclude(pk=user.pk).filter(is_active=True).order_by('first_name', 'username')
    active_room_id = request.GET.get('room')

    return render(request, 'internal_chat/chat_home.html', {
        'room_data': room_data,
        'all_users': all_users,
        'total_unread': total_unread,
        'active_room_id': active_room_id,
        'online_ids': online_ids,
        'base_template': get_base_template(user),
        'is_admin': is_admin_or_manager(user),
    })


# ===========================================================================
# START DM
# ===========================================================================

@login_required
def start_direct_chat(request, user_id):
    other = get_object_or_404(User, pk=user_id)
    room, created = ChatRoom.get_or_create_direct_room(request.user, other)
    return redirect(f'/chat/?room={room.pk}')


# ===========================================================================
# GET MESSAGES (POLLING)
# ===========================================================================

@login_required
def get_messages(request, room_id):
    room = get_object_or_404(ChatRoom, pk=room_id)
    if not is_admin_or_manager(request.user) and not room.members.filter(pk=request.user.pk).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    UserPresence.mark_online(request.user)

    # Mark messages as read (only if member, not just monitoring admin)
    if room.members.filter(pk=request.user.pk).exists():
        unread_msgs = room.messages.exclude(sender=request.user).exclude(read_by=request.user)
        for msg in unread_msgs:
            msg.read_by.add(request.user)
        if unread_msgs.exists():
            room.save()

    after_str = request.GET.get('after')
    if after_str:
        try:
            from datetime import datetime
            after_dt = datetime.fromisoformat(after_str)
            messages_qs = list(room.messages.filter(timestamp__gt=after_dt).select_related('sender'))
        except ValueError:
            messages_qs = list(reversed(list(room.messages.order_by('-timestamp')[:60])))
    else:
        messages_qs = list(reversed(list(room.messages.order_by('-timestamp')[:60])))

    online_ids = UserPresence.get_online_user_ids()
    members = [{
        'id': m.pk,
        'name': m.get_full_name() or m.username,
        'initials': (m.get_full_name() or m.username)[:2].upper(),
        'online': m.pk in online_ids,
        'role': getattr(m, 'role', 'employee'),
    } for m in room.members.all()]

    return JsonResponse({
        'room_id': room.pk,
        'room_type': room.room_type,
        'room_name': room.get_display_name(request.user),
        'members': members,
        'messages': [msg.to_dict(current_user=request.user) for msg in messages_qs],
        'server_time': timezone.now().isoformat(),
    })


# ===========================================================================
# SEND MESSAGE
# ===========================================================================

@login_required
@require_POST
def send_message(request, room_id):
    room = get_object_or_404(ChatRoom, pk=room_id)
    # Admin can send to any room; employees must be members
    if not is_admin_or_manager(request.user) and not room.members.filter(pk=request.user.pk).exists():
        return JsonResponse({'error': 'Not a member of this room'}, status=403)

    # Auto-add admin to room if they send from monitor
    if is_admin_or_manager(request.user) and not room.members.filter(pk=request.user.pk).exists():
        room.members.add(request.user)

    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')

    if not content and not attachment:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    att_type = att_name = None
    if attachment:
        mime, _ = mimetypes.guess_type(attachment.name)
        att_type = 'image' if mime and mime.startswith('image/') else ('audio' if mime and mime.startswith('audio/') else 'file')
        att_name = attachment.name

    msg = ChatMessage.objects.create(
        room=room, sender=request.user, content=content,
        attachment=attachment, attachment_type=att_type, attachment_name=att_name,
    )
    msg.read_by.add(request.user)
    room.save()

    # Create notifications for all other members
    create_message_notification(msg)

    UserPresence.mark_online(request.user)

    return JsonResponse({'status': 'sent', 'message': msg.to_dict(current_user=request.user)})


# ===========================================================================
# DELETE MESSAGE
# ===========================================================================

@login_required
@require_POST
def delete_message(request, message_id):
    msg = get_object_or_404(ChatMessage, pk=message_id)
    if msg.sender != request.user and not is_admin_or_manager(request.user):
        return JsonResponse({'error': 'Not allowed'}, status=403)
    msg.is_deleted = True
    msg.save()
    return JsonResponse({'status': 'deleted', 'message_id': message_id})


# ===========================================================================
# CREATE GROUP
# ===========================================================================

@login_required
@require_POST
def create_group_room(request):
    name = request.POST.get('name', '').strip()
    member_ids = request.POST.getlist('member_ids')
    if not name:
        return JsonResponse({'error': 'Group name is required'}, status=400)

    room = ChatRoom.objects.create(name=name, room_type=ChatRoom.GROUP, created_by=request.user)
    room.members.add(request.user)
    for mid in member_ids:
        try:
            room.members.add(User.objects.get(pk=int(mid)))
        except (User.DoesNotExist, ValueError):
            pass

    return JsonResponse({'status': 'created', 'room_id': room.pk, 'redirect': f'/chat/?room={room.pk}'})


# ===========================================================================
# ROOMS LIST (sidebar badge)
# ===========================================================================

@login_required
def get_rooms_list(request):
    UserPresence.mark_online(request.user)
    rooms = ChatRoom.objects.filter(members=request.user).order_by('-updated_at')
    online_ids = UserPresence.get_online_user_ids()
    data = []
    total_unread = 0
    for room in rooms:
        last_msg = room.last_message()
        unread = room.unread_count(request.user)
        total_unread += unread
        other = room.get_other_member(request.user) if room.room_type == ChatRoom.DIRECT else None
        data.append({
            'id': room.pk,
            'name': room.get_display_name(request.user),
            'room_type': room.room_type,
            'unread': unread,
            'other_online': (other.pk in online_ids) if other else False,
            'last_message': last_msg.content[:60] if last_msg and last_msg.content else ('📎 Attachment' if last_msg and last_msg.attachment else ''),
            'last_time': last_msg.timestamp.strftime('%I:%M %p') if last_msg else '',
        })

    # Also get total unread notifications count
    try:
        from authentication.models import Notification
        notif_count = Notification.objects.filter(recipient=request.user, is_read=False, url__contains='/chat/').count()
    except Exception:
        notif_count = 0

    return JsonResponse({'rooms': data, 'total_unread': total_unread, 'notif_count': notif_count})


# ===========================================================================
# ADMIN MONITOR
# ===========================================================================

@login_required
def admin_monitor(request):
    if not is_admin_or_manager(request.user):
        return redirect('/chat/')

    search = request.GET.get('q', '').strip()
    rooms = ChatRoom.objects.prefetch_related('members', 'messages').order_by('-updated_at')

    if search:
        rooms = rooms.filter(
            Q(name__icontains=search) |
            Q(members__username__icontains=search) |
            Q(members__first_name__icontains=search) |
            Q(members__last_name__icontains=search) |
            Q(messages__content__icontains=search)
        ).distinct()

    room_data = []
    for room in rooms:
        last_msg = room.last_message()
        room_data.append({
            'room': room,
            'members': list(room.members.all()),
            'message_count': room.messages.count(),
            'last_message': last_msg,
            'admin_is_member': room.members.filter(pk=request.user.pk).exists(),
        })

    all_users = User.objects.filter(is_active=True).order_by('first_name', 'username')

    return render(request, 'internal_chat/admin_monitor.html', {
        'room_data': room_data,
        'search': search,
        'all_users': all_users,
        'active_room_id': request.GET.get('room'),
        'online_ids': UserPresence.get_online_user_ids(),
        'base_template': get_base_template(request.user),
    })
