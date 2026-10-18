import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.catalogue.models import Product, ProductVariant

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        PROCESSING = 'processing', _('Processing')
        PACKED = 'packed', _('Packed')
        SHIPPED = 'shipped', _('Shipped')
        OUT_FOR_DELIVERY = 'out_for_delivery', _('Out for Delivery')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')
        RETURN_REQUESTED = 'return_requested', _('Return Requested')
        REFUNDED = 'refunded', _('Refunded')

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID_DEMO = 'paid_demo', _('Paid (Demo)')
        FAILED_DEMO = 'failed_demo', _('Failed (Demo)')
        REFUNDED_DEMO = 'refunded_demo', _('Refunded (Demo)')

    order_number = models.CharField(max_length=40, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')

    # Customer snapshot
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=150)

    # Shipping Address snapshot
    shipping_full_name = models.CharField(max_length=150)
    shipping_phone = models.CharField(max_length=20)
    shipping_street = models.CharField(max_length=255)
    shipping_apartment = models.CharField(max_length=255, blank=True, null=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100, default='India')

    # Statuses
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.CONFIRMED)
    payment_status = models.CharField(max_length=30, choices=PaymentStatus.choices, default=PaymentStatus.PAID_DEMO)
    payment_method = models.CharField(max_length=50, default='razorpay_demo')

    # Financials (Computed strictly on backend)
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    coupon_code = models.CharField(max_length=50, blank=True, null=True)
    customer_note = models.TextField(blank=True, null=True)
    admin_note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_number} - {self.customer_name} (₹{self.total_amount})"

    @property
    def can_cancel(self):
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]

    @property
    def is_delivered(self):
        return self.status == self.Status.DELIVERED

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)

    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=80)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    image_url = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.quantity}x {self.product_name} in {self.order.order_number}"

class OrderStatusEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=30)
    note = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.order.order_number}: {self.status} - {self.note}"

class PaymentRecord(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_record')
    transaction_id = models.CharField(max_length=100, unique=True)
    payment_gateway = models.CharField(max_length=50, default='Razorpay Demo')
    payment_method_type = models.CharField(max_length=50, default='UPI / Card (Simulation)')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, default='captured_demo')
    is_demo = models.BooleanField(default=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.transaction_id} for Order {self.order.order_number} ({'DEMO' if self.is_demo else 'LIVE'})"

class ShipmentRecord(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment_record')
    carrier_name = models.CharField(max_length=100, default='Shiprocket Express (Demo Partner)')
    tracking_number = models.CharField(max_length=100, unique=True)
    tracking_url = models.URLField(blank=True, null=True)
    estimated_delivery_date = models.DateField(null=True, blank=True)
    current_status = models.CharField(max_length=100, default='Dispatched from Jewellery Vault')
    is_demo = models.BooleanField(default=True)
    timeline_events = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shipment #{self.tracking_number} for Order {self.order.order_number} ({'DEMO' if self.is_demo else 'LIVE'})"
