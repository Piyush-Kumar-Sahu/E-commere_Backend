from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductReviewListView, CheckReviewEligibilityView, SubmitReviewView, AdminReviewViewSet

router = DefaultRouter()
router.register(r'admin', AdminReviewViewSet, basename='admin-review')

urlpatterns = [
    path('product/<slug:slug>/', ProductReviewListView.as_view(), name='product_reviews'),
    path('eligibility/<int:product_id>/', CheckReviewEligibilityView.as_view(), name='review_eligibility'),
    path('submit/', SubmitReviewView.as_view(), name='submit_review'),
    path('', include(router.urls)),
]
