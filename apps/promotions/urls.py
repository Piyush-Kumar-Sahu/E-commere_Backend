from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ValidateCouponView, CouponViewSet, BannerViewSet, StoreSettingView

router = DefaultRouter()
router.register(r'coupons', CouponViewSet, basename='coupon')
router.register(r'banners', BannerViewSet, basename='banner')

urlpatterns = [
    path('validate-coupon/', ValidateCouponView.as_view(), name='validate_coupon'),
    path('store-settings/', StoreSettingView.as_view(), name='store_settings'),
    path('', include(router.urls)),
]
