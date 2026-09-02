from rest_framework import serializers
from django.utils.text import slugify
import json

IMAGE_PREFIX = "https://panel.apnifactory.co.in/storage/app/public/"

def format_image_url(path):
    if not path:
        return None
    path_str = str(path).strip()
    if path_str.startswith("http://") or path_str.startswith("https://"):
        return path_str
    # Remove leading slash or backslash
    path_str = path_str.lstrip("/\\")
    return f"{IMAGE_PREFIX}{path_str}"

def parse_multiple_images(val):
    if not val:
        return []
    if isinstance(val, list):
        return [format_image_url(img) for img in val if img]
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return [format_image_url(img) for img in parsed if img]
    except Exception:
        pass
    if isinstance(val, str) and val.strip():
        return [format_image_url(val.strip())]
    return []

class SubCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    maincategory_id = serializers.IntegerField(default=0)
    category_id = serializers.IntegerField()
    name = serializers.CharField()
    title = serializers.CharField(allow_blank=True, default='')
    slug = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    status = serializers.IntegerField(default=1)

    def get_slug(self, obj):
        return slugify(obj.name or '')

    def get_image(self, obj):
        return format_image_url(getattr(obj, 'image', None))

class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    maincategory_id = serializers.IntegerField(default=0)
    name = serializers.CharField()
    title = serializers.CharField(allow_blank=True, default='')
    slug = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    status = serializers.IntegerField(default=1)
    sequence = serializers.IntegerField(default=0)
    subcategories = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(default=0)

    def get_slug(self, obj):
        return slugify(obj.name or '')

    def get_image(self, obj):
        return format_image_url(getattr(obj, 'image', None))

    def get_subcategories(self, obj):
        subcats = getattr(obj, '_prefetched_subcategories', [])
        return SubCategorySerializer(subcats, many=True).data

class BrandSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    company_id = serializers.IntegerField(default=0)
    name = serializers.CharField()
    image = serializers.SerializerMethodField()
    status = serializers.IntegerField(default=1)

    def get_image(self, obj):
        return format_image_url(getattr(obj, 'image', None))

class SliderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    image = serializers.SerializerMethodField()
    screen = serializers.CharField(default='home')
    startdate = serializers.DateField(allow_null=True)
    enddate = serializers.DateField(allow_null=True)
    status = serializers.IntegerField(default=1)
    link = serializers.CharField(default='/products/')

    def get_image(self, obj):
        return format_image_url(getattr(obj, 'image', None))

class ShadeCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    category_id = serializers.IntegerField(default=0)
    hexcode = serializers.CharField(allow_null=True, allow_blank=True, default='#ffffff')
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        return format_image_url(getattr(obj, 'image', None))

class ProductAttributeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.CharField()
    color_id = serializers.CharField(source='color')
    color_name = serializers.CharField(default='')
    color_hex = serializers.CharField(default='')
    quantity = serializers.CharField(default='')
    price = serializers.FloatField(default=0.0)
    oldprice = serializers.FloatField(default=0.0)
    discount_percent = serializers.SerializerMethodField()

    def get_discount_percent(self, obj):
        old = getattr(obj, 'oldprice', 0.0) or 0.0
        cur = getattr(obj, 'price', 0.0) or 0.0
        if old and old > cur and cur > 0:
            return int(((old - cur) / old) * 100)
        return 0

class ProductListSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='product_id')
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    title = serializers.CharField(allow_blank=True, default='')
    category_id = serializers.IntegerField()
    category_name = serializers.CharField(default='')
    category_slug = serializers.SerializerMethodField()
    subcategory_id = serializers.IntegerField(default=0)
    subcategory_name = serializers.CharField(default='')
    subcategory_slug = serializers.SerializerMethodField()
    brand_id = serializers.IntegerField(default=0)
    brand_name = serializers.CharField(default='')
    image = serializers.SerializerMethodField()
    multiple_images = serializers.SerializerMethodField()
    price = serializers.FloatField(default=0.0)
    oldprice = serializers.FloatField(default=0.0)
    discount_percent = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(default=True)
    status = serializers.IntegerField(default=1)
    tax = serializers.IntegerField(default=18)
    hsncode = serializers.CharField(default='')
    is_top_deal = serializers.BooleanField(default=False)
    is_best_offer = serializers.BooleanField(default=False)
    is_new_arrival = serializers.BooleanField(default=True)
    reviews_count = serializers.IntegerField(default=0)
    rating = serializers.FloatField(default=4.5)

    def get_category_slug(self, obj):
        return slugify(getattr(obj, 'category_name', '') or '')

    def get_subcategory_slug(self, obj):
        sub_name = getattr(obj, 'subcategory_name', '') or ''
        return slugify(sub_name) if sub_name else 'general'

    def get_image(self, obj):
        return format_image_url(getattr(obj, 'image', None))

    def get_multiple_images(self, obj):
        return parse_multiple_images(getattr(obj, 'multipleimages', None))

    def get_discount_percent(self, obj):
        old = getattr(obj, 'oldprice', 0.0) or 0.0
        cur = getattr(obj, 'price', 0.0) or 0.0
        if old and old > cur and cur > 0:
            return int(((old - cur) / old) * 100)
        return 0

class ProductDetailSerializer(ProductListSerializer):
    description = serializers.CharField(default='')
    attributes = ProductAttributeSerializer(many=True, default=[])
    color_variants = serializers.ListField(default=[])
    sizes = serializers.ListField(default=[])
    similar_products = ProductListSerializer(many=True, default=[])
