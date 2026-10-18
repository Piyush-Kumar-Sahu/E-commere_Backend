import uuid
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Cart, CartItem, WishlistItem
from .serializers import CartSerializer, CartItemSerializer, WishlistItemSerializer
from apps.catalogue.models import Product, ProductVariant

def get_or_create_cart(request):
    """
    Retrieves or creates a cart. Handles user authentication and guest sessions seamlessly.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)

        # Check if guest session cart exists to merge
        session_key = request.headers.get('X-Cart-Session')
        if session_key:
            guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
            if guest_cart:
                for item in guest_cart.items.all():
                    existing = cart.items.filter(product=item.product, variant=item.variant).first()
                    if existing:
                        existing.quantity += item.quantity
                        existing.save()
                    else:
                        item.cart = cart
                        item.save()
                guest_cart.delete()
        return cart

    # Guest user
    session_key = request.headers.get('X-Cart-Session')
    if not session_key:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

    cart, _ = Cart.objects.get_or_create(session_key=session_key, user__isnull=True)
    return cart

class CartView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cart = get_or_create_cart(request)
        serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'cart': serializer.data
        })

    def post(self, request):
        # Clear cart
        cart = get_or_create_cart(request)
        cart.items.all().delete()
        serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': 'Cart cleared successfully.',
            'cart': serializer.data
        })

class CartItemViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        cart = get_or_create_cart(self.request)
        return cart.items.all()

    def create(self, request, *args, **kwargs):
        cart = get_or_create_cart(request)
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        quantity = int(request.data.get('quantity', 1))

        if quantity < 1:
            return Response({'success': False, 'message': 'Quantity must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'success': False, 'message': 'Product not found or inactive.'}, status=status.HTTP_404_NOT_FOUND)

        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product, is_active=True)
            except ProductVariant.DoesNotExist:
                return Response({'success': False, 'message': 'Selected variant does not exist for this product.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check existing item in cart
        cart_item = cart.items.filter(product=product, variant=variant).first()
        total_requested = (cart_item.quantity + quantity) if cart_item else quantity

        # Stock check
        available = variant.stock_quantity if variant else product.total_stock
        if total_requested > available:
            return Response({
                'success': False,
                'message': f'Cannot add item. Only {available} units available in stock.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if cart_item:
            cart_item.quantity = total_requested
            cart_item.save()
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=quantity
            )

        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': f'Added "{product.name}" to cart.',
            'cart': cart_serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        new_quantity = int(request.data.get('quantity', instance.quantity))

        if new_quantity < 1:
            return Response({'success': False, 'message': 'Quantity must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify stock availability
        available = instance.variant.stock_quantity if instance.variant else instance.product.total_stock
        if new_quantity > available:
            return Response({
                'success': False,
                'message': f'Only {available} units available in stock.'
            }, status=status.HTTP_400_BAD_REQUEST)

        instance.quantity = new_quantity
        instance.save()

        cart = instance.cart
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': 'Cart updated.',
            'cart': cart_serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        cart = instance.cart
        instance.delete()
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': 'Item removed from cart.',
            'cart': cart_serializer.data
        })

class WishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = WishlistItem.objects.filter(user=request.user)
        serializer = WishlistItemSerializer(items, many=True, context={'request': request})
        return Response({
            'success': True,
            'results': serializer.data
        })

    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'success': False, 'message': 'Product ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'success': False, 'message': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        item = WishlistItem.objects.filter(user=request.user, product=product).first()
        if item:
            item.delete()
            in_wishlist = False
            msg = f'Removed "{product.name}" from your wishlist.'
        else:
            WishlistItem.objects.create(user=request.user, product=product)
            in_wishlist = True
            msg = f'Added "{product.name}" to your wishlist.'

        return Response({
            'success': True,
            'in_wishlist': in_wishlist,
            'message': msg
        })
