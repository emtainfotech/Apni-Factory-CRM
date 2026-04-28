from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .mobile_api_utils import verify_gst_for_mobile

@api_view(['POST'])
@permission_classes([AllowAny]) # Allowing public access for now, can be restricted with IsAuthenticated if needed
def mobile_gst_check(request):
    """
    Endpoint for Mobile Application to check GST details.
    Expected Payload: {"gst_number": "..."}
    """
    gst_number = request.data.get('gst_number')
    
    if not gst_number:
        return Response({
            'status': False,
            'message': 'gst_number is required'
        }, status=400)

    is_valid, data, error = verify_gst_for_mobile(gst_number)

    if is_valid:
        return Response({
            'status': True,
            'message': 'GST verified successfully',
            'data': data
        })
    else:
        return Response({
            'status': False,
            'message': error or 'Verification failed'
        }, status=400)
