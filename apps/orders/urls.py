from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CheckoutOrderView, OrderViewSet, PublicTrackingView

router = DefaultRouter()
router.register(r'', OrderViewSet, basename='order')

urlpatterns = [
    path('checkout/', CheckoutOrderView.as_view(), name='checkout_order'),
    path('track/<str:order_number>/', PublicTrackingView.as_view(), name='public_tracking'),
    path('', include(router.urls)),
]
