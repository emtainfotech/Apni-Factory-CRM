from django.urls import path
from . import api_views

app_name = 'vendor_network'

urlpatterns = [
    path('api/vendors/', api_views.VendorListAPIView.as_view(), name='vendor-list'),
    path('api/vendors/sync-osm/', api_views.SyncOSMVendorsAPIView.as_view(), name='sync-osm'),
]
