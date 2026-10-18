from rest_framework import generics, viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Review, ReviewModerationLog
from .serializers import ReviewSerializer, ReviewCreateSerializer, AdminReviewModerationSerializer
from apps.catalogue.models import Product
from apps.orders.models import Order
from apps.core.permissions import IsAdminRoleUser, IsVerifiedUser

class ProductReviewListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        slug = self.kwargs.get('slug')
        return Review.objects.filter(
            product__slug=slug,
            moderation_status=Review.ModerationStatus.APPROVED
        ).select_related('user__profile', 'product')

class CheckReviewEligibilityView(APIView):
    permission_classes = [IsVerifiedUser]

    def get(self, request, product_id):
        user = request.user
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'success': False, 'message': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        already_reviewed = Review.objects.filter(user=user, product=product).exists()
        has_purchased = Order.objects.filter(
            user=user,
            items__product=product,
            status__in=[
                Order.Status.CONFIRMED,
                Order.Status.PROCESSING,
                Order.Status.PACKED,
                Order.Status.SHIPPED,
                Order.Status.OUT_FOR_DELIVERY,
                Order.Status.DELIVERED
            ]
        ).exists()

        can_review = has_purchased and not already_reviewed

        return Response({
            'success': True,
            'can_review': can_review,
            'already_reviewed': already_reviewed,
            'has_purchased': has_purchased
        })

class SubmitReviewView(generics.CreateAPIView):
    permission_classes = [IsVerifiedUser]
    serializer_class = ReviewCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response({
            'success': True,
            'message': 'Thank you! Your verified purchase review has been submitted.',
            'review': ReviewSerializer(review).data
        }, status=status.HTTP_201_CREATED)

class AdminReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAdminRoleUser]

    def get_queryset(self):
        qs = Review.objects.all().select_related('product', 'user__profile')
        mod_status = self.request.query_params.get('status')
        if mod_status:
            qs = qs.filter(moderation_status=mod_status)
        return qs

    @action(detail=True, methods=['post'])
    def moderate(self, request, pk=None):
        review = self.get_object()
        serializer = AdminReviewModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['moderation_status']
        reason = serializer.validated_data.get('reason', '')

        review.moderation_status = new_status
        review.save()

        ReviewModerationLog.objects.create(
            review=review,
            moderator=request.user,
            action=new_status,
            reason=reason
        )

        return Response({
            'success': True,
            'message': f'Review #{review.id} status updated to {new_status}.',
            'review': ReviewSerializer(review).data
        })
