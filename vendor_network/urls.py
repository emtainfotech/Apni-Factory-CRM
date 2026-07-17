from django.urls import path
from . import api_views, views

app_name = 'vendor_network'

urlpatterns = [
    path('search/', views.VendorSearchView.as_view(), name='vendor-search'),
    path('api/vendors/', api_views.VendorListAPIView.as_view(), name='vendor-list'),
    path('api/vendors/sync-osm/', api_views.SyncOSMVendorsAPIView.as_view(), name='sync-osm'),
    path('directory/', views.VendorDirectoryView.as_view(), name='vendor-directory'),
    path('delete/', views.VendorDeleteView.as_view(), name='vendor-delete'),
]
