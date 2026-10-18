from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import connection

class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        db_healthy = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            db_healthy = False

        status_code = 200 if db_healthy else 503
        return Response({
            'status': 'ok' if db_healthy else 'degraded',
            'service': 'Modiecommers E-commerce API',
            'version': '1.0.0',
            'database': 'connected (PostgreSQL)' if db_healthy else 'unhealthy'
        }, status=status_code)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', HealthCheckView.as_view(), name='api_health'),
    path('api/v1/accounts/', include('apps.accounts.urls')),
    path('api/v1/catalogue/', include('apps.catalogue.urls')),
    path('api/v1/cart/', include('apps.cart.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/reviews/', include('apps.reviews.urls')),
    path('api/v1/promotions/', include('apps.promotions.urls')),
    path('api/v1/admin-ops/', include('apps.admin_ops.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
