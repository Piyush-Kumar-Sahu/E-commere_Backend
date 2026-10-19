import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction, models
from rest_framework import viewsets, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from .models import Order, OrderItem, OrderStatusEvent, PaymentRecord, ShipmentRecord
from .serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    AdminOrderStatusUpdateSerializer,
    ShipmentRecordSerializer
)
from apps.cart.views import get_or_create_cart
from apps.promotions.models import Coupon, CouponRedemption
from apps.core.permissions import IsAdminRoleUser, IsOwnerOrAdmin

class CheckoutOrderView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if request.user.is_authenticated and not getattr(request.user, 'is_verified', False) and not getattr(request.user, 'is_admin_user', False):
            return Response({
                'success': False,
                'message': 'Email verification is mandatory before completing an order. Please verify your account.'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_or_create_cart(request)
        cart_items = list(cart.items.select_related('product', 'variant').all())

        if not cart_items:
            return Response({
                'success': False,
                'message': 'Your shopping cart is currently empty.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Atomic checkout transaction with stock reservation
        with transaction.atomic():
            subtotal = Decimal('0.00')
            order_items_data = []

            for item in cart_items:
                product = item.product
                variant = item.variant
                qty = item.quantity

                if variant:
                    # Lock variant row for stock check and decrement
                    var_locked = product.variants.select_for_update().get(id=variant.id)
                    if not var_locked.is_active or var_locked.stock_quantity < qty:
                        return Response({
                            'success': False,
                            'message': f'Insufficient stock for "{product.name} ({var_locked.variant_name})". Available: {var_locked.stock_quantity}'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    unit_price = var_locked.final_price
                    var_locked.stock_quantity -= qty
                    var_locked.save()
                else:
                    # Generic product stock check
                    unit_price = product.current_price
                    if product.total_stock < qty:
                        return Response({
                            'success': False,
                            'message': f'Insufficient stock for "{product.name}".'
                        }, status=status.HTTP_400_BAD_REQUEST)

                item_subtotal = unit_price * qty
                subtotal += item_subtotal

                # Get product primary image
                primary_img = product.images.filter(is_primary=True).first() or product.images.first()
                img_url = primary_img.image.url if primary_img and primary_img.image else ''

                order_items_data.append({
                    'product': product,
                    'variant': variant,
                    'product_name': product.name,
                    'variant_name': variant.variant_name if variant else '',
                    'sku': variant.sku if variant else product.sku,
                    'unit_price': unit_price,
                    'quantity': qty,
                    'subtotal': item_subtotal,
                    'image_url': img_url
                })

            # Coupon validation & discount
            discount = Decimal('0.00')
            coupon_code = data.get('coupon_code', '').strip().upper()
            applied_coupon = None

            if coupon_code:
                coupon = Coupon.objects.filter(code__iexact=coupon_code).first()
                if coupon:
                    is_valid, msg = coupon.is_valid_for_amount(subtotal)
                    if is_valid:
                        discount = coupon.calculate_discount(subtotal)
                        applied_coupon = coupon
                        coupon.used_count += 1
                        coupon.save()

            # Shipping (Free above ₹5,000)
            shipping = Decimal('0.00') if subtotal >= 5000 else Decimal('250.00')

            # 3% GST on jewellery
            taxable_amount = max(Decimal('0.00'), subtotal - discount)
            tax = (taxable_amount * Decimal('0.03')).quantize(Decimal('0.01'))
            total = taxable_amount + shipping + tax

            # Generate unique Order Number
            date_prefix = timezone.now().strftime('%Y%m%d')
            random_suffix = uuid.uuid4().hex[:6].upper()
            order_number = f"MOD-{date_prefix}-{random_suffix}"

            # Create Order
            order = Order.objects.create(
                order_number=order_number,
                user=request.user if request.user.is_authenticated else None,
                customer_email=data['customer_email'],
                customer_phone=data['customer_phone'],
                customer_name=data['customer_name'],
                shipping_full_name=data['shipping_full_name'],
                shipping_phone=data['shipping_phone'],
                shipping_street=data['shipping_street'],
                shipping_apartment=data.get('shipping_apartment', ''),
                shipping_city=data['shipping_city'],
                shipping_state=data['shipping_state'],
                shipping_postal_code=data['shipping_postal_code'],
                shipping_country=data.get('shipping_country', 'India'),
                status=Order.Status.CONFIRMED,
                payment_status=Order.PaymentStatus.PAID_DEMO,
                payment_method=data.get('payment_method', 'razorpay_demo'),
                subtotal_amount=subtotal,
                discount_amount=discount,
                shipping_amount=shipping,
                tax_amount=tax,
                total_amount=total,
                coupon_code=coupon_code if applied_coupon else '',
                customer_note=data.get('customer_note', '')
            )

            # Create line items
            for item_info in order_items_data:
                OrderItem.objects.create(order=order, **item_info)

            # Record initial order event
            OrderStatusEvent.objects.create(
                order=order,
                status=Order.Status.CONFIRMED,
                note="Order confirmed. Payment simulation verified successfully (Demo Mode)."
            )

            # Record demo payment
            demo_txn_id = f"PAY_DEMO_{uuid.uuid4().hex[:12].upper()}"
            PaymentRecord.objects.create(
                order=order,
                transaction_id=demo_txn_id,
                payment_gateway='Razorpay (Demo Gateway)',
                payment_method_type=data.get('payment_method', 'Razorpay UPI / Netbanking'),
                amount=total,
                status='captured_demo',
                is_demo=True,
                gateway_response={
                    'demo_note': 'Simulated transaction - no live funds deducted.',
                    'gateway_timestamp': timezone.now().isoformat()
                }
            )

            # Record demo shipment
            demo_tracking_num = f"SR-EXP-{uuid.uuid4().hex[:8].upper()}"
            est_delivery = timezone.now().date() + timedelta(days=4)
            initial_timeline = [
                {
                    'timestamp': timezone.now().strftime('%d %b %Y, %I:%M %p'),
                    'location': 'Mumbai Central Hub',
                    'status': 'Order Verified & Ready for Vault Packing',
                    'note': 'Order booked via Shiprocket partner network.'
                }
            ]
            ShipmentRecord.objects.create(
                order=order,
                carrier_name='Shiprocket Express (BlueDart Air)',
                tracking_number=demo_tracking_num,
                tracking_url=f"/orders/track/{order.order_number}",
                estimated_delivery_date=est_delivery,
                current_status='Ready for Vault Packing',
                is_demo=True,
                timeline_events=initial_timeline
            )

            # Record coupon redemption if applicable
            if applied_coupon:
                CouponRedemption.objects.create(
                    coupon=applied_coupon,
                    user=request.user if request.user.is_authenticated else None,
                    order_number=order.order_number,
                    discount_amount=discount
                )

            # Clear cart
            cart.items.all().delete()

        serializer = OrderDetailSerializer(order)
        return Response({
            'success': True,
            'message': 'Your order has been placed successfully! (Demo mode - no actual money charged).',
            'order': serializer.data
        }, status=status.HTTP_201_CREATED)

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'order_number'

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        return OrderDetailSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or (not user.is_verified and not user.is_admin_user):
            # Allow retrieving specific order detail by order_number (e.g. for guest checkout confirmation)
            if self.action == 'retrieve':
                return Order.objects.all().prefetch_related('items', 'events', 'payment_record', 'shipment_record')
            return Order.objects.none()

        if user.is_staff or user.is_superuser or user.is_admin_user:
            qs = Order.objects.all().prefetch_related('items', 'events', 'payment_record', 'shipment_record')
            # Admin filters
            status_param = self.request.query_params.get('status')
            if status_param:
                qs = qs.filter(status=status_param)
            search = self.request.query_params.get('search')
            if search:
                qs = qs.filter(
                    models.Q(order_number__icontains=search) |
                    models.Q(customer_name__icontains=search) |
                    models.Q(customer_email__icontains=search)
                )
            return qs

        return Order.objects.filter(user=user).prefetch_related('items', 'events', 'payment_record', 'shipment_record')

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, order_number=None):
        order = self.get_object()
        if not order.can_cancel:
            return Response({
                'success': False,
                'message': f'Order cannot be cancelled in its current state ({order.get_status_display()}).'
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order.status = Order.Status.CANCELLED
            order.save()

            # Restore stock
            for item in order.items.all():
                if item.variant:
                    item.variant.stock_quantity += item.quantity
                    item.variant.save()

            OrderStatusEvent.objects.create(
                order=order,
                status=Order.Status.CANCELLED,
                note=f"Cancelled by customer. Reason: {request.data.get('reason', 'Customer request')}",
                created_by=request.user
            )

        serializer = OrderDetailSerializer(order)
        return Response({
            'success': True,
            'message': 'Order has been cancelled successfully. Any demo authorization has been reversed.',
            'order': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRoleUser])
    def admin_update_status(self, request, order_number=None):
        order = self.get_object()
        serializer = AdminOrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        note = serializer.validated_data.get('note', f"Status updated to {new_status}")
        tracking_num = serializer.validated_data.get('tracking_number')
        carrier_name = serializer.validated_data.get('carrier_name')

        with transaction.atomic():
            order.status = new_status
            order.save()

            OrderStatusEvent.objects.create(
                order=order,
                status=new_status,
                note=note,
                created_by=request.user
            )

            # Update shipment if provided
            if hasattr(order, 'shipment_record'):
                shipment = order.shipment_record
                if tracking_num:
                    shipment.tracking_number = tracking_num
                if carrier_name:
                    shipment.carrier_name = carrier_name

                # Add event to timeline
                current_events = list(shipment.timeline_events)
                current_events.append({
                    'timestamp': timezone.now().strftime('%d %b %Y, %I:%M %p'),
                    'location': 'Distribution Center',
                    'status': order.get_status_display(),
                    'note': note
                })
                shipment.timeline_events = current_events
                shipment.current_status = order.get_status_display()
                shipment.save()

        return Response({
            'success': True,
            'message': f'Order status updated to {new_status}.',
            'order': OrderDetailSerializer(order).data
        })

class PublicTrackingView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, order_number):
        try:
            order = Order.objects.select_related('shipment_record').get(order_number__iexact=order_number)
        except Order.DoesNotExist:
            return Response({
                'success': False,
                'message': 'No order found with the provided order number.'
            }, status=status.HTTP_404_NOT_FOUND)

        if not hasattr(order, 'shipment_record'):
            return Response({
                'success': False,
                'message': 'Shipment tracking information is being prepared.'
            }, status=status.HTTP_404_NOT_FOUND)

        shipment_serializer = ShipmentRecordSerializer(order.shipment_record)
        return Response({
            'success': True,
            'order_number': order.order_number,
            'status': order.get_status_display(),
            'customer_name': order.customer_name,
            'shipping_city': order.shipping_city,
            'shipment': shipment_serializer.data
        })
