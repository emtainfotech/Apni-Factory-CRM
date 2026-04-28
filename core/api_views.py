from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Customer, CallLog

# 1. LOGIN API
@api_view(['POST'])
@permission_classes([AllowAny])
def app_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'status': True,
            'token': token.key,
            'user_id': user.id,
            'name': user.first_name or user.username
        })
    return Response({'status': False, 'message': 'Invalid Credentials'}, status=400)

# 2. CHECK IF NUMBER EXISTS
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_number(request):
    phone = request.data.get('phone', '')
    # Logic: Match last 10 digits to handle +91 or 0 prefix
    clean_phone = phone.replace(" ", "").replace("-", "")[-10:]
    
    customer = Customer.objects.filter(phone__icontains=clean_phone).first()
    
    if customer:
        return Response({
            'exists': True,
            'customer_id': customer.id,
            'name': f"{customer.first_name} {customer.last_name}",
            'company': customer.company_name
        })
    return Response({'exists': False})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_call_log(request):
    try:
        # Check if we are updating an existing log or creating a new one
        log_id = request.data.get('log_id') 
        
        customer_id = request.data.get('customer_id')
        remark = request.data.get('remark')
        status = request.data.get('status')
        duration = request.data.get('duration')

        if log_id:
            # --- UPDATE MODE ---
            log = CallLog.objects.get(id=log_id)
            log.remark = remark
            log.call_status = status
            log.save()
            return Response({'status': True, 'message': 'Remark Updated Successfully'})
        
        else:
            # --- CREATE MODE ---
            customer = Customer.objects.get(id=customer_id)
            CallLog.objects.create(
                customer=customer,
                employee=request.user,
                call_status=status,
                remark=remark,
                call_duration=duration
            )
            return Response({'status': True, 'message': 'Call Log Saved Successfully'})

    except Exception as e:
        return Response({'status': False, 'message': str(e)}, status=500)
    
# core/api_views.py (Add these to the bottom)
from .models import WhatsAppChat # Import this if not already there

# 4. GET ASSIGNED CUSTOMERS LIST
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_customers(request):
    # Fetch customers assigned to the logged-in employee
    customers = Customer.objects.filter(assigned_to=request.user).order_by('-created_at')
    
    data = []
    for c in customers:
        data.append({
            'id': c.id,
            'name': f"{c.first_name} {c.last_name}",
            'phone': c.phone,
            'company': c.company_name,
            'status': c.get_status_display(),
            'is_verified': c.is_gst_verified
        })
    return Response({'status': True, 'data': data})

# 5. GET FULL CUSTOMER PROFILE (Details + Calls + WhatsApp)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_detail(request, customer_id):
    try:
        c = Customer.objects.get(id=customer_id)
        
        # A. Basic Details
        profile = {
            'id': c.id,
            'name': f"{c.first_name} {c.last_name}",
            'phone': c.phone,
            'email': c.email,
            'company': c.company_name,
            'gst': c.gst_number,
            'address': f"{c.address}, {c.city}, {c.state}",
            'status': c.get_status_display(),
        }

        # B. Call Logs
        logs = []
        for log in c.call_logs.all().order_by('-created_at')[:20]: # Last 20 calls
            logs.append({
                'status': log.get_call_status_display(),
                'remark': log.remark,
                'duration': log.call_duration,
                'date': log.created_at.strftime("%d %b, %I:%M %p")
            })

        # C. WhatsApp Chats
        chats = []
        for chat in c.whatsapp_chats.all().order_by('-timestamp')[:20]: # Last 20 msgs
            chats.append({
                'message': chat.message,
                'direction': chat.direction, # 'incoming' or 'outgoing'
                'date': chat.timestamp.strftime("%d %b, %I:%M %p")
            })

        return Response({
            'status': True, 
            'profile': profile, 
            'logs': logs, 
            'chats': chats
        })

    except Customer.DoesNotExist:
        return Response({'status': False, 'message': 'Customer not found'}, status=404)