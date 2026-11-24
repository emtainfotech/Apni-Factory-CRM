from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q, Case, When
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.files.storage import default_storage
from django.contrib.auth.mixins import LoginRequiredMixin
from concurrent.futures import ThreadPoolExecutor
from django.db import connection

from .models import VendorProfile
from .services.google_places_fetcher import fetch_and_save_google_places
from core.models import Customer, WhatsAppChat, WhatsAppQuickReply
from core.utils import send_template_message, format_whatsapp_phone, get_approved_meta_templates

PHONE_FILTER_Q = (
    (Q(phone_number__isnull=False) & ~Q(phone_number='')) |
    (Q(mobile_number__isnull=False) & ~Q(mobile_number=''))
)

def get_filtered_vendors_queryset(params):
    """
    Returns a VendorProfile QuerySet filtered by the provided request parameters.
    """
    store_name = params.get('store_name', '').strip() if hasattr(params, 'get') else ''
    phone_number = params.get('phone_number', '').strip() if hasattr(params, 'get') else ''
    street_address = params.get('street_address', '').strip() if hasattr(params, 'get') else ''
    status = params.get('status', '').strip() if hasattr(params, 'get') else ''

    if hasattr(params, 'getlist'):
        categories_selected = params.getlist('categories')
    elif isinstance(params.get('categories'), list):
        categories_selected = params.get('categories')
    elif params.get('categories'):
        categories_selected = [c.strip() for c in str(params.get('categories')).split(',') if c.strip()]
    else:
        categories_selected = []

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

    return vendors

class VendorSearchView(LoginRequiredMixin, View):
    template_name = 'vendor_network/vendor_search.html'

    def get(self, request):
        if request.GET.get('clear') == '1':
            request.session.pop('last_fetched_vendor_ids', None)
            request.session.pop('last_search_query', None)
            return redirect('vendor_network:vendor-search')

        last_fetched_ids = request.session.get('last_fetched_vendor_ids', [])
        search_query = request.session.get('last_search_query', '')

        vendors = []
        if last_fetched_ids:
            preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(last_fetched_ids)])
            vendors = VendorProfile.objects.filter(id__in=last_fetched_ids).order_by(preserved_order)

        context = {
            'vendors': vendors,
            'search_query': search_query,
            'has_searched': bool(last_fetched_ids or search_query),
            'synced_count': len(vendors) if vendors else None,
            'message': None,
            'status': None
        }
        return render(request, self.template_name, context)

    def post(self, request):
        query = request.POST.get('search_query', '').strip()
        party_type = request.POST.get('party_type', 'SELLER')
        context = {
            'vendors': [],
            'synced_count': 0,
            'search_query': query,
            'has_searched': True,
            'message': '',
            'status': ''
        }

        if query:
            result = fetch_and_save_google_places(query, user=request.user, party_type=party_type)
            status = result.get('status')
            synced_count = result.get('synced_count', 0)
            vendor_ids = result.get('vendor_ids', [])

            context['status'] = status
            context['synced_count'] = synced_count
            context['message'] = result.get('message', f"Successfully synced {synced_count} vendors for '{query}'.")

            if vendor_ids:
                preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(vendor_ids)])
                vendors = VendorProfile.objects.filter(id__in=vendor_ids).order_by(preserved_order)
                context['vendors'] = vendors
                request.session['last_fetched_vendor_ids'] = vendor_ids
                request.session['last_search_query'] = query
            else:
                context['vendors'] = []
                request.session['last_fetched_vendor_ids'] = []
                request.session['last_search_query'] = query
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

        vendors = get_filtered_vendors_queryset(request.GET)

        # Total counts
        total_db_count = VendorProfile.objects.count()
        filtered_count = vendors.count()
        filtered_with_phone_count = vendors.filter(PHONE_FILTER_Q).count()
        is_filtered = bool(store_name or phone_number or street_address or status or categories_selected)

        # Pagination: 50 per page
        paginator = Paginator(vendors, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get unique categories for the filter dropdown
        all_categories = VendorProfile.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True).distinct().order_by('category')

        # Preserve query params for pagination links
        query_params_copy = request.GET.copy()
        if 'page' in query_params_copy:
            del query_params_copy['page']

        # WhatsApp Quick Replies & Meta Templates
        quick_replies = WhatsAppQuickReply.objects.filter(is_active=True).order_by('title')
        approved_templates = []
        try:
            approved_templates = get_approved_meta_templates()
        except Exception:
            pass

        context = {
            'vendors': page_obj,
            'page_obj': page_obj,
            'filters': {
                'store_name': store_name,
                'phone_number': phone_number,
                'street_address': street_address,
                'status': status,
                'categories': categories_selected
            },
            'total_db_count': total_db_count,
            'filtered_count': filtered_count,
            'filtered_with_phone_count': filtered_with_phone_count,
            'is_filtered': is_filtered,
            'quick_replies': quick_replies,
            'approved_templates': approved_templates,
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
            
        return redirect(request.META.get('HTTP_REFERER', 'vendor_network:vendor-directory'))

class SendVendorMetaTemplateView(LoginRequiredMixin, View):
    """
    Sends an approved Meta WhatsApp template to filtered or selected vendors.
    """
    def post(self, request):
        target_type = request.POST.get('target_type', 'filtered').strip().lower()
        template_name = request.POST.get('template_name', '').strip()
        language_code = request.POST.get('language_code', 'en').strip() or 'en'
        header_image_url = request.POST.get('header_image_url', '').strip()
        auto_register_customer = request.POST.get('auto_register_customer', 'true') in ('true', '1', 'on')
        mark_contacted = request.POST.get('mark_contacted', 'true') in ('true', '1', 'on')

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        if not template_name:
            err = "Please select or enter a Meta Template Name."
            if is_ajax:
                return JsonResponse({'success': False, 'message': err}, status=400)
            messages.error(request, err)
            return redirect(request.META.get('HTTP_REFERER', 'vendor_network:vendor-directory'))

        # Check for uploaded media file for template header
        if 'header_media_file' in request.FILES:
            uploaded_file = request.FILES['header_media_file']
            try:
                saved_path = default_storage.save(f'whatsapp_templates/{uploaded_file.name}', uploaded_file)
                header_image_url = request.build_absolute_uri(default_storage.url(saved_path))
            except Exception as e:
                print(f"Error saving header media file: {e}")

        # If header_image_url is empty, check if template matches a quick reply with header url
        if not header_image_url:
            qr = WhatsAppQuickReply.objects.filter(meta_template_names__icontains=template_name).first()
            if qr and qr.meta_template_header_media_url:
                header_image_url = qr.meta_template_header_media_url

        # Determine target vendors
        if target_type == 'selected':
            vendor_ids = request.POST.getlist('vendor_ids')
            if not vendor_ids and request.POST.get('vendor_ids'):
                vendor_ids = [vid.strip() for vid in str(request.POST.get('vendor_ids')).split(',') if vid.strip()]
            vendors_qs = VendorProfile.objects.filter(id__in=vendor_ids)
        else:
            vendors_qs = get_filtered_vendors_queryset(request.POST)

        # Filter vendors with at least one phone field
        vendors_to_process = list(vendors_qs.filter(PHONE_FILTER_Q))
        total_targeted = len(vendors_to_process)

        if total_targeted == 0:
            msg = "No vendors with valid phone numbers found for the selected criteria."
            if is_ajax:
                return JsonResponse({'success': False, 'message': msg, 'total_targeted': 0, 'sent_count': 0}, status=400)
            messages.warning(request, msg)
            return redirect(request.META.get('HTTP_REFERER', 'vendor_network:vendor-directory'))

        sent_count = 0
        failed_count = 0
        skipped_count = 0
        details = []

        def dispatch_to_vendor(vendor):
            raw_phone = (vendor.mobile_number or vendor.phone_number or '').strip()
            clean_phone = format_whatsapp_phone(raw_phone)

            if not clean_phone or not clean_phone.isdigit() or len(clean_phone) < 10:
                return {
                    'vendor_id': vendor.id,
                    'store_name': vendor.store_name,
                    'phone': raw_phone,
                    'status': 'skipped',
                    'error': 'Invalid or missing phone number'
                }

            try:
                success, wamid, err_msg = send_template_message(
                    to_number=clean_phone,
                    template_name=template_name,
                    language_code=language_code,
                    header_image_url=header_image_url or None,
                    return_details=True
                )

                if success:
                    # Update CRM customer & chat if enabled
                    if auto_register_customer:
                        try:
                            cust, _ = Customer.objects.get_or_create(
                                phone=clean_phone,
                                defaults={
                                    'first_name': vendor.store_name or 'Vendor',
                                    'company_name': vendor.store_name or '',
                                    'customer_type': 'seller' if getattr(vendor, 'party_type', 'SELLER') == 'SELLER' else 'buyer',
                                    'address': vendor.street_address or '',
                                    'city': vendor.city or '',
                                    'state': vendor.state or '',
                                    'pincode': vendor.pincode or '',
                                    'assigned_to': request.user if request.user.is_authenticated else None,
                                    'created_by': request.user if request.user.is_authenticated else None,
                                    'lead_source': 'vendor_network',
                                    'whatsapp_number': clean_phone,
                                }
                            )
                            WhatsAppChat.objects.create(
                                customer=cust,
                                message=f"[Meta Template Sent]: {template_name}",
                                direction='outgoing',
                                wamid=wamid or '',
                            )
                        except Exception as e:
                            print(f"Error registering customer for vendor {vendor.id}: {e}")

                    # Update vendor status/notes
                    if mark_contacted:
                        try:
                            if vendor.enrichment_status in ('PENDING', 'SCRAPED_SUCCESS'):
                                vendor.enrichment_status = 'CONTACTED'
                            now_str = timezone.now().strftime('%d %b %Y, %I:%M %p')
                            user_str = request.user.username if request.user.is_authenticated else 'System'
                            note_line = f"Meta template '{template_name}' sent on {now_str} by {user_str}."
                            vendor.notes = f"{vendor.notes}\n{note_line}" if vendor.notes else note_line
                            vendor.save(update_fields=['enrichment_status', 'notes', 'updated_at'])
                        except Exception as e:
                            print(f"Error updating vendor {vendor.id}: {e}")

                    return {
                        'vendor_id': vendor.id,
                        'store_name': vendor.store_name,
                        'phone': clean_phone,
                        'status': 'sent',
                        'wamid': wamid
                    }
                else:
                    return {
                        'vendor_id': vendor.id,
                        'store_name': vendor.store_name,
                        'phone': clean_phone,
                        'status': 'failed',
                        'error': err_msg or 'Meta API Error'
                    }
            except Exception as ex:
                return {
                    'vendor_id': vendor.id,
                    'store_name': vendor.store_name,
                    'phone': clean_phone,
                    'status': 'failed',
                    'error': str(ex)
                }
            finally:
                connection.close()

        # Threaded dispatch
        max_workers = min(6, max(1, total_targeted))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(dispatch_to_vendor, vendors_to_process))

        for r in results:
            if r['status'] == 'sent':
                sent_count += 1
            elif r['status'] == 'failed':
                failed_count += 1
            else:
                skipped_count += 1
            details.append(r)

        summary_msg = f"Successfully dispatched Meta template '{template_name}' to {sent_count} vendor(s)."
        if failed_count > 0:
            summary_msg += f" {failed_count} delivery attempt(s) failed."
        if skipped_count > 0:
            summary_msg += f" {skipped_count} skipped due to invalid phone numbers."

        if is_ajax:
            return JsonResponse({
                'success': True,
                'total_targeted': total_targeted,
                'sent_count': sent_count,
                'failed_count': failed_count,
                'skipped_count': skipped_count,
                'template_name': template_name,
                'message': summary_msg,
                'details': details[:50]
            })

        if sent_count > 0:
            messages.success(request, summary_msg)
        else:
            messages.error(request, summary_msg)

        return redirect(request.META.get('HTTP_REFERER', 'vendor_network:vendor-directory'))
