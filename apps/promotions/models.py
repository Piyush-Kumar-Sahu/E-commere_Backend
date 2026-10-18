from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', _('Percentage Discount')
        FIXED = 'fixed', _('Fixed Amount Discount')

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage (e.g. 10.00) or Flat Amount (e.g. 2000.00)")
    minimum_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    maximum_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total times this coupon can be used")
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.discount_value}{'%' if self.discount_type == self.DiscountType.PERCENTAGE else ' INR'})"

    def is_valid_for_amount(self, amount):
        now = timezone.now()
        if not self.is_active:
            return False, "This coupon is no longer active."
        if self.start_date and now < self.start_date:
            return False, "This coupon is not valid yet."
        if self.end_date and now > self.end_date:
            return False, "This coupon has expired."
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "This coupon usage limit has been reached."
        if amount < self.minimum_order_amount:
            return False, f"Minimum order amount for this coupon is ₹{self.minimum_order_amount:,.2f}."
        return True, "Valid coupon"

    def calculate_discount(self, amount):
        if self.discount_type == self.DiscountType.PERCENTAGE:
            disc = (amount * self.discount_value) / 100
            if self.maximum_discount_amount and disc > self.maximum_discount_amount:
                disc = self.maximum_discount_amount
            return min(disc, amount)
        else:
            return min(self.discount_value, amount)

class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=50)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} applied to {self.order_number} (-₹{self.discount_amount})"

class Banner(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    cta_text = models.CharField(max_length=50, default='Explore Collection')
    cta_link = models.CharField(max_length=200, default='/shop')
    badge_text = models.CharField(max_length=50, blank=True, help_text="e.g. New Season, Limited Edition")
    image = models.ImageField(upload_to='banners/', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return self.title

class StoreSetting(models.Model):
    store_name = models.CharField(max_length=150, default='Modiecommers Fine Jewellery')
    support_email = models.EmailField(default='care@modiecommers.com')
    support_phone = models.CharField(max_length=30, default='+91 98765 43210')
    store_address = models.TextField(default='102, Heritage Diamond Tower, Zaveri Bazaar, Mumbai, Maharashtra 400002')
    gst_number = models.CharField(max_length=30, default='27AAACM1234F1Z8')
    announcement_bar_text = models.CharField(max_length=255, default='Complimentary insured shipping on all orders over ₹5,000 | 100% Certified Natural Diamonds & Hallmarked Gold')
    is_announcement_active = models.BooleanField(default=True)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    currency_symbol = models.CharField(max_length=10, default='₹')
    currency_code = models.CharField(max_length=10, default='INR')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.store_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
