from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import connection

class RootHealthCheckView(APIView):
    """
    Minimal health-check endpoint at '/' returning a simple JSON status response.
    Ensures that GET / returns HTTP 200 without database overhead or changing existing API behavior.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            'status': 'ok',
            'service': 'Modiecommers E-commerce API',
            'version': '1.0.0',
        }, status=200)


class HealthCheckView(APIView):
    """
    Safe, configurable health check endpoint.
    Supports liveness and readiness monitoring for platforms like Render.
    Does not perform any active keep-alive or self-pinging.

    Query Parameters:
      - check_db: "true" | "false" (defaults to settings.HEALTH_CHECK_INCLUDE_DB)
        Setting check_db=false performs a fast liveness check without querying PostgreSQL.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        check_db_param = request.query_params.get('check_db')
        if check_db_param is not None:
            should_check_db = check_db_param.lower() in ('true', '1', 'yes')
        else:
            should_check_db = getattr(settings, 'HEALTH_CHECK_INCLUDE_DB', True)

        db_status = 'skipped'
        db_healthy = True

        if should_check_db:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                db_status = 'connected (PostgreSQL)'
            except Exception:
                db_healthy = False
                db_status = 'unhealthy'

        status_code = 200 if db_healthy else 503
        return Response({
            'status': 'ok' if db_healthy else 'degraded',
            'service': 'Modiecommers E-commerce API',
            'version': '1.0.0',
            'environment': 'production' if getattr(settings, 'IS_PRODUCTION', False) else 'development',
            'database': db_status
        }, status=status_code)

urlpatterns = [
    # Minimal root health check
    path('', RootHealthCheckView.as_view(), name='root_health'),

    # Health checks (aliases for Render health check path, Kubernetes, or uptime monitoring)
    path('health/', HealthCheckView.as_view(), name='health_root'),
    path('healthz/', HealthCheckView.as_view(), name='healthz'),
    path('api/v1/health/', HealthCheckView.as_view(), name='api_health'),

    path('admin/', admin.site.urls),
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
