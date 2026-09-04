import json
import mimetypes
from datetime import timedelta

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


# ===========================================================================
# PRESENCE HEARTBEAT
# ===========================================================================

@login_required
def update_presence(request):
    """Heartbeat — called every 10 seconds by JS to mark user online."""
    UserPresence.mark_online(request.user)
    return JsonResponse({'status': 'ok', 'online': True})


@login_required
def get_presence(request):
    """Returns list of currently online user IDs."""
    online_ids = UserPresence.get_online_user_ids()
    return JsonResponse({'online_user_ids': online_ids})


# ===========================================================================
# MAIN CHAT HOME — dual-pane WhatsApp layout
# ===========================================================================

@login_required
def chat_home(request):
    """Main chat inbox. Shows conversation list on the left."""
    UserPresence.mark_online(request.user)
    user = request.user

    # All rooms this user is a member of
    rooms = ChatRoom.objects.filter(members=user).prefetch_related('members').order_by('-updated_at')

    # Enrich each room with display info
    room_data = []
    total_unread = 0
    for room in rooms:
        last_msg = room.last_message()
        unread = room.unread_count(user)
        total_unread += unread
        other = room.get_other_member(user) if room.room_type == ChatRoom.DIRECT else None
        online_ids = UserPresence.get_online_user_ids()
        room_data.append({
            'room': room,
            'display_name': room.get_display_name(user),
            'last_message': last_msg,
            'unread': unread,
            'other_user': other,
            'other_online': other.pk in online_ids if other else False,
        })

    # All employees/admins this user can start a DM with
    all_users = User.objects.exclude(pk=user.pk).filter(is_active=True).order_by('first_name', 'username')

    # Auto-select room if ?room=<id> passed
    active_room_id = request.GET.get('room')

    return render(request, 'internal_chat/chat_home.html', {
        'room_data': room_data,
        'all_users': all_users,
        'total_unread': total_unread,
        'active_room_id': active_room_id,
        'online_ids': UserPresence.get_online_user_ids(),
    })


# ===========================================================================
# START / GET DM ROOM
# ===========================================================================

@login_required
def start_direct_chat(request, user_id):
    """Creates or opens a DM room between logged-in user and user_id."""
    other = get_object_or_404(User, pk=user_id)
    room, created = ChatRoom.get_or_create_direct_room(request.user, other)
    return redirect(f'/chat/?room={room.pk}')


# ===========================================================================
# GET MESSAGES (POLLING ENDPOINT)
# ===========================================================================

@login_required
def get_messages(request, room_id):
    """
    Returns JSON messages for a room, supporting incremental polling.
    Optional ?after=<timestamp> to get only new messages.
    """
    # Validate access
    room = get_object_or_404(ChatRoom, pk=room_id)
    if not is_admin_or_manager(request.user) and not room.members.filter(pk=request.user.pk).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    UserPresence.mark_online(request.user)

    # Mark messages as read
    unread_msgs = room.messages.exclude(sender=request.user).exclude(read_by=request.user)
    for msg in unread_msgs:
        msg.read_by.add(request.user)
    room.save()  # triggers updated_at

    after_str = request.GET.get('after')
    if after_str:
        try:
            from datetime import datetime
            after_dt = datetime.fromisoformat(after_str)
            messages_qs = room.messages.filter(timestamp__gt=after_dt).select_related('sender')
        except ValueError:
            messages_qs = room.messages.order_by('-timestamp')[:50]
            messages_qs = list(reversed(list(messages_qs)))
    else:
        messages_qs = list(room.messages.order_by('-timestamp')[:60])
        messages_qs = list(reversed(messages_qs))

    # Online users
    online_ids = UserPresence.get_online_user_ids()

    # Room member info
    members = [{
        'id': m.pk,
        'name': m.get_full_name() or m.username,
        'initials': (m.get_full_name() or m.username)[:2].upper(),
        'online': m.pk in online_ids,
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
    """Send a new message to a room."""
    room = get_object_or_404(ChatRoom, pk=room_id)
    if not room.members.filter(pk=request.user.pk).exists():
        return JsonResponse({'error': 'Not a member of this room'}, status=403)

    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')

    if not content and not attachment:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    att_type = None
    att_name = None
    if attachment:
        mime, _ = mimetypes.guess_type(attachment.name)
        if mime and mime.startswith('image/'):
            att_type = 'image'
        elif mime and mime.startswith('audio/'):
            att_type = 'audio'
        else:
            att_type = 'file'
        att_name = attachment.name

    msg = ChatMessage.objects.create(
        room=room,
        sender=request.user,
        content=content,
        attachment=attachment,
        attachment_type=att_type,
        attachment_name=att_name,
    )
    # Sender has read their own message
    msg.read_by.add(request.user)
    # Update room timestamp for ordering
    room.save()

    UserPresence.mark_online(request.user)

    return JsonResponse({
        'status': 'sent',
        'message': msg.to_dict(current_user=request.user),
    })


# ===========================================================================
# DELETE MESSAGE (soft)
# ===========================================================================

@login_required
@require_POST
def delete_message(request, message_id):
    msg = get_object_or_404(ChatMessage, pk=message_id)
    # Only sender or admin can delete
    if msg.sender != request.user and not is_admin_or_manager(request.user):
        return JsonResponse({'error': 'Not allowed'}, status=403)
    msg.is_deleted = True
    msg.save()
    return JsonResponse({'status': 'deleted', 'message_id': message_id})


# ===========================================================================
# CREATE GROUP ROOM
# ===========================================================================

@login_required
@require_POST
def create_group_room(request):
    """Create a new group chat room."""
    name = request.POST.get('name', '').strip()
    member_ids = request.POST.getlist('member_ids')

    if not name:
        return JsonResponse({'error': 'Group name is required'}, status=400)

    room = ChatRoom.objects.create(
        name=name,
        room_type=ChatRoom.GROUP,
        created_by=request.user,
    )
    # Add creator + selected members
    room.members.add(request.user)
    for mid in member_ids:
        try:
            u = User.objects.get(pk=int(mid))
            room.members.add(u)
        except (User.DoesNotExist, ValueError):
            pass

    return JsonResponse({'status': 'created', 'room_id': room.pk, 'redirect': f'/chat/?room={room.pk}'})


# ===========================================================================
# GET ROOMS LIST (for sidebar polling)
# ===========================================================================

@login_required
def get_rooms_list(request):
    """Returns updated room list with unread counts — called every 5s for sidebar badge."""
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
    return JsonResponse({'rooms': data, 'total_unread': total_unread})


# ===========================================================================
# ADMIN — MONITOR ALL CONVERSATIONS
# ===========================================================================

@login_required
def admin_monitor(request):
    """Admin-only: view all chat rooms and conversations."""
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
        })

    all_users = User.objects.filter(is_active=True).order_by('first_name', 'username')

    return render(request, 'internal_chat/admin_monitor.html', {
        'room_data': room_data,
        'search': search,
        'all_users': all_users,
        'active_room_id': request.GET.get('room'),
    })
