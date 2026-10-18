from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Coupon, Banner, StoreSetting
from .serializers import CouponSerializer, CouponValidateSerializer, BannerSerializer, StoreSettingSerializer
from apps.core.permissions import IsAdminUserOrReadOnly, IsAdminRoleUser

class ValidateCouponView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code'].strip().upper()
        subtotal = serializer.validated_data['subtotal']

        coupon = Coupon.objects.filter(code__iexact=code).first()
        if not coupon:
            return Response({
                'success': False,
                'message': 'Invalid coupon code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        is_valid, msg = coupon.is_valid_for_amount(subtotal)
        if not is_valid:
            return Response({
                'success': False,
                'message': msg
            }, status=status.HTTP_400_BAD_REQUEST)

        discount_amount = coupon.calculate_discount(subtotal)
        return Response({
            'success': True,
            'message': f'Coupon "{coupon.code}" applied successfully!',
            'data': {
                'code': coupon.code,
                'discount_type': coupon.discount_type,
                'discount_value': str(coupon.discount_value),
                'discount_amount': str(discount_amount),
                'new_subtotal': str(subtotal - discount_amount)
            }
        })

class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminRoleUser]

class BannerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUserOrReadOnly]
    serializer_class = BannerSerializer

    def get_queryset(self):
        if self.request.user and (self.request.user.is_staff or self.request.user.is_superuser):
            return Banner.objects.all()
        return Banner.objects.filter(is_active=True)

class StoreSettingView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [IsAdminRoleUser()]

    def get(self, request):
        settings_obj = StoreSetting.get_settings()
        serializer = StoreSettingSerializer(settings_obj)
        return Response({
            'success': True,
            'settings': serializer.data
        })

    def patch(self, request):
        settings_obj = StoreSetting.get_settings()
        serializer = StoreSettingSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'success': True,
            'message': 'Store settings updated successfully.',
            'settings': serializer.data
        })
