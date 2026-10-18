from rest_framework import serializers
from .models import Category, Collection, Product, ProductImage, ProductVariant

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'alt_text', 'is_primary', 'display_order')

class ProductVariantSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            'id', 'variant_type', 'variant_name', 'sku', 'price_adjustment',
            'stock_quantity', 'is_active', 'final_price', 'is_in_stock'
        )

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'image', 'display_order', 'is_active', 'product_count')

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

class CollectionSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ('id', 'name', 'slug', 'tagline', 'description', 'banner_image', 'is_featured', 'is_active', 'product_count')

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    collection_name = serializers.CharField(source='collection.name', read_only=True, default='')
    primary_image = serializers.SerializerMethodField()
    secondary_image = serializers.SerializerMethodField()
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_stock = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    metal_type_display = serializers.CharField(source='get_metal_type_display', read_only=True)
    metal_purity_display = serializers.CharField(source='get_metal_purity_display', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'sku', 'short_description', 'base_price', 'sale_price',
            'current_price', 'category_name', 'category_slug', 'collection_name',
            'primary_image', 'secondary_image', 'total_stock', 'is_in_stock',
            'metal_type', 'metal_type_display', 'metal_purity', 'metal_purity_display',
            'gemstone', 'weight_grams', 'is_featured', 'is_new_arrival', 'is_bestseller',
            'average_rating', 'review_count'
        )

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        if img and img.image:
            request = self.context.get('request')
            return request.build_absolute_uri(img.image.url) if request else img.image.url
        return None

    def get_secondary_image(self, obj):
        imgs = obj.images.all()
        if len(imgs) > 1:
            img = imgs[1]
            if img and img.image:
                request = self.context.get('request')
                return request.build_absolute_uri(img.image.url) if request else img.image.url
        return None

    def get_average_rating(self, obj):
        # Calculate from approved reviews
        approved = obj.reviews.filter(moderation_status='approved')
        if approved.exists():
            return round(sum(r.rating for r in approved) / approved.count(), 1)
        return 5.0  # default showcase rating

    def get_review_count(self, obj):
        return obj.reviews.filter(moderation_status='approved').count()

class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    collection = CollectionSerializer(read_only=True)
    collection_id = serializers.PrimaryKeyRelatedField(
        queryset=Collection.objects.all(), source='collection', write_only=True, required=False, allow_null=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_stock = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    metal_type_display = serializers.CharField(source='get_metal_type_display', read_only=True)
    metal_purity_display = serializers.CharField(source='get_metal_purity_display', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'sku', 'short_description', 'description',
            'base_price', 'sale_price', 'current_price', 'category', 'category_id',
            'collection', 'collection_id', 'metal_type', 'metal_type_display',
            'metal_purity', 'metal_purity_display', 'gemstone', 'weight_grams',
            'dimensions', 'packaging_info', 'care_instructions', 'is_featured',
            'is_new_arrival', 'is_bestseller', 'is_active', 'total_stock', 'is_in_stock',
            'images', 'variants', 'average_rating', 'review_count', 'created_at', 'updated_at'
        )

    def get_average_rating(self, obj):
        approved = obj.reviews.filter(moderation_status='approved')
        if approved.exists():
            return round(sum(r.rating for r in approved) / approved.count(), 1)
        return 5.0

    def get_review_count(self, obj):
        return obj.reviews.filter(moderation_status='approved').count()

class ProductAdminManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
