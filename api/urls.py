from django.urls import path
from .views import (
    category_list_view,
    brand_list_view,
    slider_list_view,
    product_list_view,
    product_detail_view,
    search_suggest_view,
    quote_create_view,
)

urlpatterns = [
    path('categories/', category_list_view, name='api_categories'),
    path('brands/', brand_list_view, name='api_brands'),
    path('sliders/', slider_list_view, name='api_sliders'),
    path('products/', product_list_view, name='api_products'),
    path('products/<slug:slug>/', product_detail_view, name='api_product_detail'),
    path('search-suggest/', search_suggest_view, name='api_search_suggest'),
    path('quotes/', quote_create_view, name='api_quotes'),
]
