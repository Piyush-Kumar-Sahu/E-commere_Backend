import django_filters
from django.db.models import Q
from .models import Product

class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name='category__slug')
    collection = django_filters.CharFilter(field_name='collection__slug')
    min_price = django_filters.NumberFilter(method='filter_min_price')
    max_price = django_filters.NumberFilter(method='filter_max_price')
    metal_type = django_filters.CharFilter(field_name='metal_type')
    metal_purity = django_filters.CharFilter(field_name='metal_purity')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')
    is_featured = django_filters.BooleanFilter(field_name='is_featured')
    is_new_arrival = django_filters.BooleanFilter(field_name='is_new_arrival')
    is_bestseller = django_filters.BooleanFilter(field_name='is_bestseller')

    class Meta:
        model = Product
        fields = ['category', 'collection', 'metal_type', 'metal_purity', 'is_featured', 'is_new_arrival', 'is_bestseller']

    def filter_min_price(self, queryset, name, value):
        return queryset.filter(
            Q(sale_price__gte=value, sale_price__isnull=False) |
            Q(base_price__gte=value, sale_price__isnull=True)
        )

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(
            Q(sale_price__lte=value, sale_price__isnull=False) |
            Q(base_price__lte=value, sale_price__isnull=True)
        )

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(variants__stock_quantity__gt=0, variants__is_active=True).distinct()
        return queryset
