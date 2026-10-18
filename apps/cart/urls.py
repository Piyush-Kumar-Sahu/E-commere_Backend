from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartView, CartItemViewSet, WishlistView

router = DefaultRouter()
router.register(r'items', CartItemViewSet, basename='cart-item')

urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('wishlist/', WishlistView.as_view(), name='wishlist'),
    path('', include(router.urls)),
]
