from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusEvent, PaymentRecord, ShipmentRecord

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            'id', 'product', 'variant', 'product_name', 'variant_name',
            'sku', 'unit_price', 'quantity', 'subtotal', 'image_url'
        )

class OrderStatusEventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.email', read_only=True, default='System')

    class Meta:
        model = OrderStatusEvent
        fields = ('id', 'status', 'note', 'created_by_name', 'created_at')

class PaymentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRecord
        fields = ('id', 'transaction_id', 'payment_gateway', 'payment_method_type', 'amount', 'status', 'is_demo', 'created_at')

class ShipmentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentRecord
        fields = (
            'id', 'carrier_name', 'tracking_number', 'tracking_url',
            'estimated_delivery_date', 'current_status', 'is_demo',
            'timeline_events', 'updated_at'
        )

class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    events = OrderStatusEventSerializer(many=True, read_only=True)
    payment_record = PaymentRecordSerializer(read_only=True)
    shipment_record = ShipmentRecordSerializer(read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer_email', 'customer_phone', 'customer_name',
            'shipping_full_name', 'shipping_phone', 'shipping_street', 'shipping_apartment',
            'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country',
            'status', 'status_display', 'payment_status', 'payment_status_display', 'payment_method',
            'subtotal_amount', 'discount_amount', 'shipping_amount', 'tax_amount', 'total_amount',
            'coupon_code', 'customer_note', 'admin_note', 'can_cancel', 'items', 'events',
            'payment_record', 'shipment_record', 'created_at', 'updated_at'
        )

class OrderListSerializer(serializers.ModelSerializer):
    total_items = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    first_item_image = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer_name', 'customer_email',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'total_amount', 'total_items', 'first_item_image', 'created_at'
        )

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_first_item_image(self, obj):
        item = obj.items.first()
        return item.image_url if item else None

class OrderCreateSerializer(serializers.Serializer):
    customer_email = serializers.EmailField(required=True)
    customer_phone = serializers.CharField(max_length=20, required=True)
    customer_name = serializers.CharField(max_length=150, required=True)

    shipping_full_name = serializers.CharField(max_length=150, required=True)
    shipping_phone = serializers.CharField(max_length=20, required=True)
    shipping_street = serializers.CharField(max_length=255, required=True)
    shipping_apartment = serializers.CharField(max_length=255, required=False, allow_blank=True)
    shipping_city = serializers.CharField(max_length=100, required=True)
    shipping_state = serializers.CharField(max_length=100, required=True)
    shipping_postal_code = serializers.CharField(max_length=20, required=True)
    shipping_country = serializers.CharField(max_length=100, default='India')

    payment_method = serializers.CharField(default='razorpay_demo')
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    customer_note = serializers.CharField(required=False, allow_blank=True)

class AdminOrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    tracking_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    carrier_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
