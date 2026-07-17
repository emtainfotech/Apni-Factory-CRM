from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import VendorProfile
from .services.osm_fetcher import fetch_and_sync_osm_vendors

class SyncOSMVendorsAPIView(APIView):
    """
    POST /api/vendors/sync-osm/
    Body: {"city": "Indore"}
    Triggers the synchronous Overpass fetch and saves to DB.
    """
    def post(self, request):
        city = request.data.get('city', 'Indore')
        result = fetch_and_sync_osm_vendors(city_name=city)
        if result.get('status') == 'success':
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VendorListAPIView(APIView):
    """
    GET /api/vendors/
    Returns a simple list of all vendors in the DB.
    """
    def get(self, request):
        # Using simple serialization since we didn't define a ModelSerializer explicitly to save time.
        # For production, define a VendorProfileSerializer.
        vendors = VendorProfile.objects.all()[:100] # Limiting to 100 for safety
        data = [
            {
                "id": v.id,
                "place_id": v.place_id,
                "store_name": v.store_name,
                "category": v.category,
                "street_address": v.street_address,
                "mobile_number": v.mobile_number,
                "email_address": v.email_address,
                "website_url": v.website_url,
                "enrichment_status": v.enrichment_status
            }
            for v in vendors
        ]
        return Response(data, status=status.HTTP_200_OK)
