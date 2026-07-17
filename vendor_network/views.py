from django.shortcuts import render, redirect
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q
from .models import VendorProfile
from .services.google_places_fetcher import fetch_and_save_google_places
from django.contrib.auth.mixins import LoginRequiredMixin

class VendorSearchView(LoginRequiredMixin, View):
    template_name = 'vendor_network/vendor_search.html'

    def get(self, request):
        vendors = VendorProfile.objects.all().order_by('-id')[:100]
        context = {
            'vendors': vendors,
            'synced_count': None,
            'message': None,
            'status': None
        }
        return render(request, self.template_name, context)

    def post(self, request):
        query = request.POST.get('search_query')
        context = {
            'vendors': VendorProfile.objects.all().order_by('-id')[:100],
            'synced_count': 0,
            'message': '',
            'status': ''
        }

        if query:
            result = fetch_and_save_google_places(query)
            context['status'] = result.get('status')
            context['message'] = result.get('message', f"Successfully synced {result.get('synced_count')} vendors.")
            context['synced_count'] = result.get('synced_count')
            # Refresh vendor list after syncing
            context['vendors'] = VendorProfile.objects.all().order_by('-id')[:100]
        else:
            context['status'] = 'error'
            context['message'] = 'Please enter a search query.'

        return render(request, self.template_name, context)

class VendorDirectoryView(LoginRequiredMixin, View):
    def get(self, request):
        query_params = request.GET
        store_name = query_params.get('store_name', '')
        phone_number = query_params.get('phone_number', '')
        street_address = query_params.get('street_address', '')
        status = query_params.get('status', '')
        categories_selected = request.GET.getlist('categories')

        vendors = VendorProfile.objects.all().order_by('-updated_at')

        if store_name:
            vendors = vendors.filter(store_name__icontains=store_name)
        if phone_number:
            vendors = vendors.filter(
                Q(phone_number__icontains=phone_number) | 
                Q(mobile_number__icontains=phone_number)
            )
        if street_address:
            vendors = vendors.filter(street_address__icontains=street_address)
        if status:
            vendors = vendors.filter(enrichment_status=status)
        if categories_selected:
            vendors = vendors.filter(category__in=categories_selected)

        # Pagination: 50 per page
        paginator = Paginator(vendors, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get unique categories for the filter
        all_categories = VendorProfile.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True).distinct().order_by('category')

        # Preserve query params for pagination
        query_params_copy = request.GET.copy()
        if 'page' in query_params_copy:
            del query_params_copy['page']

        context = {
            'vendors': page_obj,  # Use page_obj for the template
            'page_obj': page_obj,
            'filters': {
                'store_name': store_name,
                'phone_number': phone_number,
                'street_address': street_address,
                'status': status,
                'categories': categories_selected
            },
            'status_choices': VendorProfile.STATUS_CHOICES,
            'all_categories': all_categories,
            'query_string': query_params_copy.urlencode()
        }
        return render(request, 'vendor_network/vendor_directory.html', context)

class VendorDeleteView(LoginRequiredMixin, View):
    def post(self, request):
        vendor_ids = request.POST.getlist('vendor_ids')
        if vendor_ids:
            VendorProfile.objects.filter(id__in=vendor_ids).delete()
            messages.success(request, f"Successfully deleted {len(vendor_ids)} vendor(s).")
        else:
            messages.error(request, "No vendors selected for deletion.")
            
        # Redirect back to where they came from
        return redirect(request.META.get('HTTP_REFERER', 'vendor_network:vendor-directory'))
