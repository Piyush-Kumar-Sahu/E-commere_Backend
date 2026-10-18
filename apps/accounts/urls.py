from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    VerifyEmailOTPView,
    ResendOTPView,
    ForgotPasswordView,
    VerifyResetOTPView,
    ResendResetOTPView,
    ValidateResetTokenView,
    ResetPasswordView,
    CustomTokenObtainPairView,
    UserProfileView,
    ChangePasswordView,
    AddressViewSet,
    AdminCustomerListView
)

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

urlpatterns = [
    # Authentication & Registration flow
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailOTPView.as_view(), name='verify_email'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Password Reset flow (OTP-based)
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('verify-reset-otp/', VerifyResetOTPView.as_view(), name='verify_reset_otp'),
    path('resend-reset-otp/', ResendResetOTPView.as_view(), name='resend_reset_otp'),
    path('validate-reset-token/', ValidateResetTokenView.as_view(), name='validate_reset_token'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),

    # Profile & Customer features
    path('me/', UserProfileView.as_view(), name='user_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('admin/customers/', AdminCustomerListView.as_view(), name='admin_customers'),
    path('', include(router.urls)),
]
