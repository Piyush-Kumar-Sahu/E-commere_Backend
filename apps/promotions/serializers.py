from rest_framework import serializers
from .models import Coupon, Banner, StoreSetting

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = '__all__'

class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40, required=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ('id', 'title', 'subtitle', 'cta_text', 'cta_link', 'badge_text', 'image', 'display_order', 'is_active')

class StoreSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSetting
        fields = '__all__'
