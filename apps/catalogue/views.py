from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Collection, Product, ProductImage, ProductVariant
from .serializers import (
    CategorySerializer,
    CollectionSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductAdminManageSerializer,
    ProductImageSerializer,
    ProductVariantSerializer
)
from .filters import ProductFilter
from apps.core.permissions import IsAdminUserOrReadOnly, IsAdminRoleUser

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUserOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        if self.request.user and (self.request.user.is_staff or self.request.user.is_superuser):
            return Category.objects.all()
        return Category.objects.filter(is_active=True)

class CollectionViewSet(viewsets.ModelViewSet):
    queryset = Collection.objects.filter(is_active=True)
    serializer_class = CollectionSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        if self.request.user and (self.request.user.is_staff or self.request.user.is_superuser):
            return Collection.objects.all()
        return Collection.objects.filter(is_active=True)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().select_related('category', 'collection').prefetch_related('images', 'variants', 'reviews')
    permission_classes = [IsAdminUserOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku', 'description', 'short_description', 'gemstone']
    ordering_fields = ['base_price', 'sale_price', 'created_at', 'name']
    lookup_field = 'slug'

    def get_queryset(self):
        qs = Product.objects.all().select_related('category', 'collection').prefetch_related('images', 'variants', 'reviews')
        if not (self.request.user and (self.request.user.is_staff or self.request.user.is_superuser)):
            qs = qs.filter(is_active=True)

        # Handle custom ordering
        ordering = self.request.query_params.get('ordering', None)
        if ordering == 'price_asc':
            qs = qs.order_by('sale_price', 'base_price')
        elif ordering == 'price_desc':
            qs = qs.order_by('-sale_price', '-base_price')
        elif ordering == 'newest':
            qs = qs.order_by('-created_at')
        elif ordering == 'bestseller':
            qs = qs.order_by('-is_bestseller', '-created_at')

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        elif self.action == 'retrieve':
            return ProductDetailSerializer
        elif self.request.user and (self.request.user.is_staff or self.request.user.is_superuser):
            return ProductAdminManageSerializer
        return ProductDetailSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRoleUser])
    def upload_image(self, request, slug=None):
        product = self.get_object()
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'success': False, 'message': 'No image file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # File validation: check extension and size (< 5MB)
        ext = image_file.name.split('.')[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png', 'webp']:
            return Response({'success': False, 'message': 'Only JPEG, PNG and WebP images are permitted.'}, status=status.HTTP_400_BAD_REQUEST)
        if image_file.size > 5 * 1024 * 1024:
            return Response({'success': False, 'message': 'Image file size must be under 5MB.'}, status=status.HTTP_400_BAD_REQUEST)

        is_primary = request.data.get('is_primary', 'false').lower() in ('true', '1')
        alt_text = request.data.get('alt_text', product.name)
        display_order = int(request.data.get('display_order', 0))

        image_obj = ProductImage.objects.create(
            product=product,
            image=image_file,
            alt_text=alt_text,
            is_primary=is_primary,
            display_order=display_order
        )

        serializer = ProductImageSerializer(image_obj, context={'request': request})
        return Response({'success': True, 'message': 'Image uploaded successfully.', 'image': serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='delete-image/(?P<image_id>[0-9]+)', permission_classes=[IsAdminRoleUser])
    def delete_image(self, request, slug=None, image_id=None):
        product = self.get_object()
        try:
            image_obj = product.images.get(id=image_id)
            image_obj.delete()
            return Response({'success': True, 'message': 'Image deleted successfully.'}, status=status.HTTP_200_OK)
        except ProductImage.DoesNotExist:
            return Response({'success': False, 'message': 'Image not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRoleUser])
    def add_variant(self, request, slug=None):
        product = self.get_object()
        serializer = ProductVariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product)
        return Response({'success': True, 'message': 'Variant created successfully.', 'variant': serializer.data}, status=status.HTTP_201_CREATED)

class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAdminRoleUser]
