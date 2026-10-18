from django.urls import path
from .views import DashboardStatsView, ExportOrdersCSVView, ExportProductsCSVView, AuditLogListView

urlpatterns = [
    path('dashboard/stats/', DashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('export/orders-csv/', ExportOrdersCSVView.as_view(), name='export_orders_csv'),
    path('export/products-csv/', ExportProductsCSVView.as_view(), name='export_products_csv'),
    path('audit-logs/', AuditLogListView.as_view(), name='admin_audit_logs'),
]
