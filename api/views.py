from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.db import connections
from django.utils.text import slugify
import math
import json
import re

from hostinger_data.models import (
    Products, Categories, SubCategories, Brands,
    Sliders, ProductAttributes, ShadeCards, ProductImages
)
from core.models import Customer, CustomerActivityLog
from .serializers import (
    CategorySerializer, SubCategorySerializer, BrandSerializer,
    SliderSerializer, ProductListSerializer, ProductDetailSerializer,
    format_image_url, parse_multiple_images
)

def _get_box_packings_map():
    try:
        cursor = connections['hostinger_db'].cursor()
        cursor.execute("SELECT id, name FROM box_packings;")
        return {row[0]: row[1].strip() for row in cursor.fetchall()}
    except Exception:
        return {}

def _build_product_lookup_maps():
    cats = {c.id: c.name for c in Categories.objects.all()}
    subcats = {s.id: s.name for s in SubCategories.objects.all()}
    brands = {b.id: b.name for b in Brands.objects.all()}
    shades = {s.id: {'name': s.name, 'hex': s.hexcode or '#ffffff', 'image': format_image_url(s.image)} for s in ShadeCards.objects.all()}
    pack_map = _get_box_packings_map()
    return cats, subcats, brands, shades, pack_map

def _resolve_size_name(raw_qty, pack_map):
    if not raw_qty:
        return 'Standard'
    s_str = str(raw_qty).strip()
    if s_str.isdigit() and int(s_str) in pack_map:
        return pack_map[int(s_str)]
    return s_str

def _clean_html_description(raw_desc):
    if not raw_desc:
        return ''
    cleaned = re.sub(r'data-[a-zA-Z0-9_\-]+="[^"]*"', '', str(raw_desc))
    cleaned = re.sub(r'class="pDq2pG_selectionAnchorContainer"', '', cleaned, flags=re.I)
    cleaned = re.sub(r'<span aria-hidden="true" class="[^"]*"></span>', '', cleaned, flags=re.I)
    return cleaned.strip()

def _enrich_product_object(p, cats, subcats, brands, attrs_by_prod, shades, pack_map=None):
    p.category_name = cats.get(p.category_id, '')
    p.subcategory_name = subcats.get(p.subcategory_id, '')
    p.brand_name = brands.get(p.brand_id, '')
    
    prod_attrs = attrs_by_prod.get(str(p.product_id), []) or attrs_by_prod.get(str(p.id), [])
    
    if prod_attrs:
        prices = [a.price for a in prod_attrs if a.price is not None and a.price > 0]
        oldprices = [a.oldprice for a in prod_attrs if a.oldprice is not None and a.oldprice > 0]
        
        p.price = min(prices) if prices else 0.0
        
        if oldprices and min(oldprices) > p.price:
            p.oldprice = min(oldprices)
        else:
            p.oldprice = round(p.price * 1.25, 2)
    else:
        p.price = 0.0
        p.oldprice = 0.0
        
    p.is_top_deal = (p.id % 3 == 0)
    p.is_best_offer = (p.id % 4 == 0)
    p.is_new_arrival = True
    p.reviews_count = (p.id * 7) % 45 + 5
    p.rating = 4.0 + ((p.id % 10) / 10.0)
    return p

@api_view(['GET'])
@permission_classes([AllowAny])
def category_list_view(request):
    only_with_products = request.GET.get('only_with_products', 'true').lower() in ['true', '1', 'yes']
    categories = list(Categories.objects.filter(status=1).order_by('sequence', 'id'))
    subcategories = list(SubCategories.objects.filter(status=1).order_by('id'))
    
    subcats_by_cat = {}
    for sub in subcategories:
        subcats_by_cat.setdefault(sub.category_id, []).append(sub)
        
    prod_counts = {}
    for p in Products.objects.filter(status=1).only('category_id'):
        prod_counts[p.category_id] = prod_counts.get(p.category_id, 0) + 1
        
    filtered_categories = []
    for cat in categories:
        p_count = prod_counts.get(cat.id, 0)
        cat.product_count = p_count
        cat._prefetched_subcategories = subcats_by_cat.get(cat.id, [])
        if only_with_products and p_count == 0:
            continue
        filtered_categories.append(cat)
        
    filtered_categories.sort(key=lambda c: (c.sequence or 999, -c.product_count))
    serializer = CategorySerializer(filtered_categories, many=True)
    return Response({'status': 'success', 'data': serializer.data})

@api_view(['GET'])
@permission_classes([AllowAny])
def brand_list_view(request):
    brands = Brands.objects.filter(status=1).order_by('name')
    serializer = BrandSerializer(brands, many=True)
    return Response({'status': 'success', 'data': serializer.data})

@api_view(['GET'])
@permission_classes([AllowAny])
def slider_list_view(request):
    screen = request.GET.get('screen', 'home')
    sliders = Sliders.objects.filter(status=1).order_by('-id')
    if screen:
        sliders = sliders.filter(Q(screen__icontains=screen) | Q(screen=''))
    serializer = SliderSerializer(sliders, many=True)
    return Response({'status': 'success', 'data': serializer.data})

@api_view(['GET'])
@permission_classes([AllowAny])
def product_list_view(request):
    category_param = request.GET.get('category', '').strip()
    subcategory_param = request.GET.get('subcategory', '').strip()
    brand_params = request.GET.getlist('brand') or request.GET.getlist('brands')
    q_param = request.GET.get('q', '').strip()
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    is_top_deal = request.GET.get('is_top_deal')
    is_best_offer = request.GET.get('is_best_offer')
    sort_by = request.GET.get('sort', '-id')
    
    page = max(1, int(request.GET.get('page', 1)))
    page_size = min(50, max(1, int(request.GET.get('page_size', 12))))
    
    cats, subcats, brands_map, shades, pack_map = _build_product_lookup_maps()
    cat_slug_to_id = {slugify(name): cid for cid, name in cats.items()}
    subcat_slug_to_id = {slugify(name): sid for sid, name in subcats.items()}
    
    queryset = Products.objects.filter(status=1)
    
    if category_param:
        if category_param.isdigit():
            queryset = queryset.filter(category_id=int(category_param))
        elif category_param in cat_slug_to_id:
            queryset = queryset.filter(category_id=cat_slug_to_id[category_param])
        else:
            matching_cat_ids = [cid for cid, name in cats.items() if category_param.lower() in name.lower() or category_param.lower() in slugify(name)]
            if matching_cat_ids:
                queryset = queryset.filter(category_id__in=matching_cat_ids)
                
    if subcategory_param and subcategory_param != 'general':
        if subcategory_param.isdigit():
            queryset = queryset.filter(subcategory_id=int(subcategory_param))
        elif subcategory_param in subcat_slug_to_id:
            queryset = queryset.filter(subcategory_id=subcat_slug_to_id[subcategory_param])
            
    if brand_params:
        brand_ids = []
        for b in brand_params:
            if b.isdigit():
                brand_ids.append(int(b))
            else:
                brand_ids.extend([bid for bid, name in brands_map.items() if name.lower() == b.lower()])
        if brand_ids:
            queryset = queryset.filter(brand_id__in=brand_ids)
            
    if q_param:
        matching_cat_ids = [cid for cid, name in cats.items() if q_param.lower() in name.lower()]
        matching_brand_ids = [bid for bid, name in brands_map.items() if q_param.lower() in name.lower()]
        queryset = queryset.filter(
            Q(name__icontains=q_param) |
            Q(title__icontains=q_param) |
            Q(slug__icontains=q_param) |
            Q(description__icontains=q_param) |
            Q(category_id__in=matching_cat_ids) |
            Q(brand_id__in=matching_brand_ids)
        )
        
    all_products = list(queryset)
    
    prod_ids_str = [str(p.product_id) for p in all_products] + [str(p.id) for p in all_products]
    all_attrs = list(ProductAttributes.objects.filter(product_id__in=prod_ids_str))
    attrs_by_prod = {}
    for a in all_attrs:
        attrs_by_prod.setdefault(str(a.product_id), []).append(a)
        
    enriched_products = []
    for p in all_products:
        _enrich_product_object(p, cats, subcats, brands_map, attrs_by_prod, shades, pack_map)
        
        if min_price and str(min_price).replace('.', '', 1).isdigit() and p.price < float(min_price):
            continue
        if max_price and str(max_price).replace('.', '', 1).isdigit() and p.price > float(max_price):
            continue
            
        if is_top_deal in ['true', '1', True] and not p.is_top_deal:
            continue
        if is_best_offer in ['true', '1', True] and not p.is_best_offer:
            continue
            
        enriched_products.append(p)
        
    available_brand_names = sorted(list(set(p.brand_name for p in enriched_products if p.brand_name)))
    
    available_sizes = set()
    available_colors = set()
    for p in enriched_products:
        prod_attrs = attrs_by_prod.get(str(p.product_id), []) or attrs_by_prod.get(str(p.id), [])
        for a in prod_attrs:
            s_name = _resolve_size_name(a.quantity, pack_map)
            if s_name:
                available_sizes.add(s_name)
            if a.color and str(a.color).isdigit():
                shade_info = shades.get(int(a.color))
                if shade_info:
                    available_colors.add(shade_info['name'])
                    
    if sort_by == 'price_low_high':
        enriched_products.sort(key=lambda x: x.price)
    elif sort_by == 'price_high_low':
        enriched_products.sort(key=lambda x: x.price, reverse=True)
    elif sort_by == 'newest':
        enriched_products.sort(key=lambda x: x.id, reverse=True)
    else:
        enriched_products.sort(key=lambda x: x.id, reverse=True)
        
    total_count = len(enriched_products)
    total_pages = max(1, math.ceil(total_count / page_size))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = enriched_products[start_idx:end_idx]
    
    serializer = ProductListSerializer(page_items, many=True)
    
    return Response({
        'status': 'success',
        'pagination': {
            'total_count': total_count,
            'total_pages': total_pages,
            'current_page': page,
            'page_size': page_size,
            'has_next': page < total_pages,
            'has_previous': page > 1,
        },
        'filters': {
            'available_brands': available_brand_names,
            'available_sizes': sorted(list(available_sizes)),
            'available_colors': sorted(list(available_colors)),
        },
        'data': serializer.data
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail_view(request, slug):
    cats, subcats, brands_map, shades, pack_map = _build_product_lookup_maps()
    
    product = None
    if slug.isdigit():
        product = Products.objects.filter(Q(product_id=int(slug)) | Q(id=int(slug)), status=1).first()
    if not product:
        product = Products.objects.filter(slug=slug, status=1).first()
    if not product:
        product = Products.objects.filter(name__iexact=slug.replace('-', ' '), status=1).first()
        
    if not product:
        return Response({'status': 'error', 'message': f'Product not found for slug: {slug}'}, status=status.HTTP_404_NOT_FOUND)
        
    prod_attrs = list(ProductAttributes.objects.filter(Q(product_id=str(product.product_id)) | Q(product_id=str(product.id))))
    attrs_by_prod = {str(product.product_id): prod_attrs, str(product.id): prod_attrs}
    _enrich_product_object(product, cats, subcats, brands_map, attrs_by_prod, shades, pack_map)
    
    product.description = _clean_html_description(product.description)
    
    formatted_attrs = []
    color_map = {}
    sizes_map = {}
    
    parsed_main_images = parse_multiple_images(product.multipleimages)
    if not parsed_main_images and product.image:
        parsed_main_images = [format_image_url(product.image)]
        
    for a in prod_attrs:
        shade_info = shades.get(int(a.color)) if str(a.color).isdigit() else None
        c_name = shade_info['name'] if shade_info else 'Standard'
        c_hex = shade_info['hex'] if shade_info else '#ffffff'
        c_thumb = shade_info['image'] if (shade_info and shade_info['image']) else format_image_url(product.image)
        
        a.color_name = c_name
        a.color_hex = c_hex
        formatted_attrs.append(a)
        
        if c_name not in color_map:
            color_map[c_name] = {
                'color': c_name,
                'hex': c_hex,
                'thumbnail': c_thumb,
                'images': parsed_main_images
            }
            
        s_name = _resolve_size_name(a.quantity, pack_map)
        price_val = a.price or 0.0
        oldprice_val = a.oldprice or 0.0
        
        if oldprice_val <= price_val:
            oldprice_val = round(price_val * 1.25, 2)
            
        discount_pct = int(((oldprice_val - price_val) / oldprice_val) * 100) if oldprice_val > price_val else 0
        
        if s_name not in sizes_map or price_val < sizes_map[s_name]['price']:
            sizes_map[s_name] = {
                'name': s_name,
                'price': price_val,
                'mrp': oldprice_val,
                'discount_percent': discount_pct,
                'in_stock': True
            }
            
    product.attributes = formatted_attrs
    product.color_variants = list(color_map.values())
    product.sizes = list(sizes_map.values())
    
    sim_prods = list(Products.objects.filter(category_id=product.category_id, status=1).exclude(id=product.id)[:6])
    for sp in sim_prods:
        _enrich_product_object(sp, cats, subcats, brands_map, attrs_by_prod, shades, pack_map)
    product.similar_products = sim_prods
    
    serializer = ProductDetailSerializer(product)
    return Response({'status': 'success', 'data': serializer.data})

@api_view(['GET'])
@permission_classes([AllowAny])
def search_suggest_view(request):
    q = request.GET.get('q', '').strip().lower()
    if not q or len(q) < 2:
        return Response({'status': 'success', 'categories': [], 'products': []})
        
    cats, subcats, brands_map, shades, pack_map = _build_product_lookup_maps()
    
    matched_cats = []
    for cid, name in cats.items():
        if q in name.lower():
            matched_cats.append({
                'id': cid,
                'name': name,
                'slug': slugify(name),
                'url': f"/{slugify(name)}/"
            })
            if len(matched_cats) >= 5:
                break
                
    matched_prods = list(Products.objects.filter(status=1).filter(
        Q(name__icontains=q) | Q(title__icontains=q) | Q(slug__icontains=q)
    )[:6])
    
    prod_results = []
    for p in matched_prods:
        cat_name = cats.get(p.category_id, 'products')
        prod_results.append({
            'id': p.product_id,
            'name': p.name,
            'slug': p.slug,
            'image': format_image_url(p.image),
            'category_slug': slugify(cat_name),
            'url': f"/{slugify(cat_name)}/general/{p.slug}/"
        })
        
    return Response({
        'status': 'success',
        'categories': matched_cats,
        'products': prod_results
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def quote_create_view(request):
    data = request.data
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    product_name = data.get('product_name', '').strip()
    quantity = data.get('quantity', 1)
    message = data.get('message', '').strip()
    is_bundle = data.get('is_bundle_request', False)
    bundle_items = data.get('bundle_items', '')
    
    if not name:
        return Response({'status': 'error', 'message': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        clean_phone = phone if phone else f"web_{name.replace(' ', '_').lower()[:15]}"
        customer, _ = Customer.objects.get_or_create(
            phone=clean_phone,
            defaults={
                'first_name': name,
                'email': email,
                'lead_source': 'website',
                'status': 'lead',
                'notes': f"Product: {product_name}, Qty: {quantity}, Msg: {message}"
            }
        )
        
        CustomerActivityLog.objects.create(
            customer=customer,
            action='Website Quote Request',
            description=f"New Website Quote: {product_name} (Qty: {quantity}) - Msg: {message} {'(Bundle: ' + str(bundle_items) + ')' if is_bundle else ''}"
        )
        
        return Response({'status': 'success', 'message': 'Quote request received successfully. Our team will contact you shortly.'})
    except Exception as e:
        return Response({'status': 'error', 'message': f'Failed to process quote: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
