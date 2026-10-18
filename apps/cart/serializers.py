from rest_framework import serializers
from .models import Cart, CartItem, WishlistItem
from apps.catalogue.serializers import ProductListSerializer, ProductVariantSerializer
from apps.catalogue.models import Product, ProductVariant

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), source='product', write_only=True
    )
    variant = ProductVariantSerializer(read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.filter(is_active=True),
        source='variant',
        write_only=True,
        required=False,
        allow_null=True
    )
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = CartItem
        fields = (
            'id', 'product', 'product_id', 'variant', 'variant_id',
            'quantity', 'unit_price', 'subtotal', 'is_available'
        )

    def validate(self, attrs):
        product = attrs.get('product')
        variant = attrs.get('variant')
        quantity = attrs.get('quantity', 1)

        if quantity < 1:
            raise serializers.ValidationError({"quantity": "Quantity must be at least 1."})

        # Validate variant belongs to product if provided
        if variant and variant.product != product:
            raise serializers.ValidationError({"variant_id": "Selected variant does not belong to this product."})

        # Validate available stock on backend
        available_stock = variant.stock_quantity if variant else product.total_stock
        if quantity > available_stock:
            raise serializers.ValidationError({
                "quantity": f"Only {available_stock} units available in stock."
            })

        return attrs

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    estimated_shipping = serializers.SerializerMethodField()
    estimated_tax = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = (
            'id', 'items', 'total_items', 'subtotal',
            'estimated_shipping', 'estimated_tax', 'total_price', 'updated_at'
        )

    def get_estimated_shipping(self, obj):
        # Free shipping over INR 5,000 as per jewellery style guide
        return 0.00 if obj.subtotal >= 5000 else 250.00

    def get_estimated_tax(self, obj):
        # 3% GST on fine jewellery in India (included/calculated transparently)
        return round(float(obj.subtotal) * 0.03, 2)

    def get_total_price(self, obj):
        shipping = self.get_estimated_shipping(obj)
        return float(obj.subtotal) + shipping

class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), source='product', write_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ('id', 'product', 'product_id', 'created_at')
        read_only_fields = ('id', 'created_at')
