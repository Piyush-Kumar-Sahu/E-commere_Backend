import csv
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Sum, Avg, Count, Q
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import AuditLog
from apps.orders.models import Order, OrderItem
from apps.catalogue.models import Product, ProductVariant
from apps.accounts.models import User
from apps.core.permissions import IsAdminRoleUser

class DashboardStatsView(APIView):
    permission_classes = [IsAdminRoleUser]

    def get(self, request):
        now = timezone.now()
        active_orders = Order.objects.exclude(status=Order.Status.CANCELLED)

        # High-level KPIs
        total_revenue = active_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        total_orders_count = active_orders.count()
        avg_order_value = active_orders.aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0.00')
        pending_fulfillment = active_orders.filter(status__in=[Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PROCESSING, Order.Status.PACKED]).count()

        # Low stock variants (< 5 units)
        low_stock_variants = ProductVariant.objects.filter(stock_quantity__lte=5, is_active=True).select_related('product')
        low_stock_count = low_stock_variants.count()

        # Recent 6 orders
        recent_orders_qs = Order.objects.all().order_by('-created_at')[:6]
        recent_orders_data = [
            {
                'order_number': o.order_number,
                'customer_name': o.customer_name,
                'customer_email': o.customer_email,
                'total_amount': str(o.total_amount),
                'status': o.status,
                'status_display': o.get_status_display(),
                'payment_status': o.get_payment_status_display(),
                'created_at': o.created_at.strftime('%d %b %Y, %I:%M %p')
            }
            for o in recent_orders_qs
        ]

        # Top 5 products by quantity sold
        top_products_qs = OrderItem.objects.filter(order__in=active_orders).values(
            'product_name'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('subtotal')
        ).order_by('-total_sold')[:5]

        top_products = [
            {
                'name': p['product_name'],
                'units_sold': p['total_sold'],
                'revenue': str(p['total_revenue'])
            }
            for p in top_products_qs
        ]

        # 7-day revenue trend
        sales_chart = []
        for i in range(6, -1, -1):
            day_date = (now - timedelta(days=i)).date()
            day_start = timezone.make_aware(timezone.datetime.combine(day_date, timezone.datetime.min.time()))
            day_end = timezone.make_aware(timezone.datetime.combine(day_date, timezone.datetime.max.time()))

            day_orders = active_orders.filter(created_at__range=(day_start, day_end))
            day_rev = day_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            day_count = day_orders.count()

            sales_chart.append({
                'date': day_date.strftime('%b %d'),
                'revenue': float(day_rev),
                'orders': day_count
            })

        return Response({
            'success': True,
            'kpis': {
                'total_revenue': str(total_revenue),
                'total_orders': total_orders_count,
                'avg_order_value': str(round(avg_order_value, 2)),
                'pending_fulfillment': pending_fulfillment,
                'low_stock_count': low_stock_count,
                'total_customers': User.objects.filter(role=User.Role.CUSTOMER).count()
            },
            'sales_chart': sales_chart,
            'top_products': top_products,
            'recent_orders': recent_orders_data,
            'low_stock_items': [
                {
                    'id': v.id,
                    'product_name': v.product.name,
                    'variant_name': v.variant_name,
                    'sku': v.sku,
                    'stock': v.stock_quantity
                }
                for v in low_stock_variants[:8]
            ]
        })

class ExportOrdersCSVView(APIView):
    permission_classes = [IsAdminRoleUser]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="modiecommers_orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Date', 'Customer Name', 'Customer Email', 'Customer Phone',
            'City', 'State', 'Status', 'Payment Status', 'Subtotal', 'Discount', 'Shipping', 'Tax', 'Total Amount', 'Items Count'
        ])

        orders = Order.objects.all().prefetch_related('items').order_by('-created_at')
        for o in orders:
            writer.writerow([
                o.order_number,
                o.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                o.customer_name,
                o.customer_email,
                o.customer_phone,
                o.shipping_city,
                o.shipping_state,
                o.get_status_display(),
                o.get_payment_status_display(),
                str(o.subtotal_amount),
                str(o.discount_amount),
                str(o.shipping_amount),
                str(o.tax_amount),
                str(o.total_amount),
                o.items.count()
            ])

        return response

class ExportProductsCSVView(APIView):
    permission_classes = [IsAdminRoleUser]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="modiecommers_catalog_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'SKU', 'Name', 'Category', 'Metal Type', 'Metal Purity', 'Gemstone',
            'Base Price (INR)', 'Sale Price (INR)', 'Total Stock', 'Active', 'Created At'
        ])

        products = Product.objects.all().select_related('category').prefetch_related('variants')
        for p in products:
            writer.writerow([
                p.sku,
                p.name,
                p.category.name if p.category else '',
                p.get_metal_type_display(),
                p.get_metal_purity_display(),
                p.gemstone,
                str(p.base_price),
                str(p.sale_price) if p.sale_price else '',
                p.total_stock,
                'Yes' if p.is_active else 'No',
                p.created_at.strftime('%Y-%m-%d')
            ])

        return response

class AuditLogListView(generics.ListAPIView):
    permission_classes = [IsAdminRoleUser]

    def get_queryset(self):
        return AuditLog.objects.all().select_related('actor')

    def get(self, request):
        logs = self.get_queryset()[:50]
        data = [
            {
                'id': log.id,
                'actor': log.actor.email if log.actor else 'System',
                'action': log.action,
                'model_name': log.model_name,
                'object_id': log.object_id,
                'details': log.details,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            for log in logs
        ]
        return Response({'success': True, 'results': data})
