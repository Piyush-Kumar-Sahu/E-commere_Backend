import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.password_validation import validate_password
from rest_framework import generics, status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Address, EmailVerificationOTP, PasswordResetRateLimit, PasswordResetOTP
from .serializers import (
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    AddressSerializer,
    VerifyEmailOTPSerializer,
    ResendOTPSerializer,
    ForgotPasswordSerializer,
    VerifyPasswordResetOTPSerializer,
    ResetPasswordWithOTPSerializer,
    ValidateResetTokenSerializer,
    ResetPasswordSerializer
)
from .emails import send_verification_otp_email, send_password_reset_email, send_password_reset_otp_email
from apps.core.permissions import IsOwnerOrAdmin, IsAdminRoleUser, IsVerifiedUser

logger = logging.getLogger(__name__)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({
                'success': False,
                'message': 'Email address is required.',
                'errors': {'email': ['This field is required.']}
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if account with this email already exists
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            if existing_user.is_verified:
                return Response({
                    'success': False,
                    'message': 'An account with this email address already exists. Please sign in or use forgot password.',
                    'errors': {'email': ['An account with this email already exists.']}
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Existing unverified account: update credentials and send fresh OTP
                serializer = UserRegistrationSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                val_data = serializer.validated_data
                existing_user.set_password(val_data['password'])
                if val_data.get('phone_number') is not None:
                    existing_user.phone_number = val_data['phone_number']
                existing_user.save()

                if hasattr(existing_user, 'profile'):
                    existing_user.profile.first_name = val_data.get('first_name', '')
                    existing_user.profile.last_name = val_data.get('last_name', '')
                    existing_user.profile.save()

                otp_instance, raw_otp = EmailVerificationOTP.generate_for_user(existing_user)
                email_sent, err_msg = send_verification_otp_email(existing_user, raw_otp)

                return Response({
                    'success': True,
                    'requires_verification': True,
                    'email': existing_user.email,
                    'email_sent': email_sent,
                    'message': 'A verification code has been sent to your email. Please verify to activate your account.' if email_sent else 'Account updated, but email delivery encountered an issue. Please try Resend OTP.'
                }, status=status.HTTP_200_OK)

        # New user registration
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate secure OTP & dispatch email
        otp_instance, raw_otp = EmailVerificationOTP.generate_for_user(user)
        email_sent, err_msg = send_verification_otp_email(user, raw_otp)

        return Response({
            'success': True,
            'requires_verification': True,
            'email': user.email,
            'email_sent': email_sent,
            'message': 'Account created successfully! Please enter the 6-digit verification code sent to your email.' if email_sent else 'Account created! Could not deliver verification email immediately. Please use Resend OTP.'
        }, status=status.HTTP_201_CREATED)


class VerifyEmailOTPView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = VerifyEmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        otp_candidate = serializer.validated_data['otp'].strip()

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({
                'success': False,
                'message': 'No account associated with this email address was found.'
            }, status=status.HTTP_404_NOT_FOUND)

        if user.is_verified:
            # Already verified, generate tokens if credentials match or instruct to login
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Your email is already verified. You are signed in.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'is_verified': True,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'is_admin': user.is_admin_user,
                    'display_name': user.profile.display_name if hasattr(user, 'profile') else user.email.split('@')[0],
                },
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            }, status=status.HTTP_200_OK)

        # Retrieve latest OTP
        latest_otp = EmailVerificationOTP.objects.filter(user=user, is_used=False).first()
        if not latest_otp:
            return Response({
                'success': False,
                'message': 'No active verification code found for this account. Please click Resend Code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        is_valid, error_msg = latest_otp.verify(otp_candidate)
        if not is_valid:
            return Response({
                'success': False,
                'message': error_msg
            }, status=status.HTTP_400_BAD_REQUEST)

        # Successful verification: activate account
        user.is_verified = True
        user.is_active = True
        user.save(update_fields=['is_verified', 'is_active', 'updated_at'])

        # Invalidate any other active OTPs
        EmailVerificationOTP.objects.filter(user=user).update(is_used=True)

        # Issue JWT tokens for verified patron
        refresh = RefreshToken.for_user(user)
        user_data = {
            'id': user.id,
            'email': user.email,
            'role': user.role,
            'is_verified': user.is_verified,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'is_admin': user.is_admin_user,
            'display_name': user.profile.display_name if hasattr(user, 'profile') else user.email.split('@')[0],
            'first_name': user.profile.first_name if hasattr(user, 'profile') else '',
            'last_name': user.profile.last_name if hasattr(user, 'profile') else '',
        }

        return Response({
            'success': True,
            'message': 'Your email address has been verified successfully. Welcome to Modiecommers!',
            'user': user_data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            # Generic response to avoid email enumeration
            return Response({
                'success': True,
                'message': 'If this email is registered and unverified, a new verification code has been dispatched.'
            }, status=status.HTTP_200_OK)

        if user.is_verified:
            return Response({
                'success': False,
                'message': 'This account is already verified. Please sign in directly.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Cooldown check (default 60 seconds)
        cooldown_seconds = getattr(settings, 'EMAIL_OTP_COOLDOWN_SECONDS', 60)
        recent_otp = EmailVerificationOTP.objects.filter(user=user).order_by('-created_at').first()
        if recent_otp:
            time_since_creation = (timezone.now() - recent_otp.created_at).total_seconds()
            if time_since_creation < cooldown_seconds:
                remaining_cooldown = int(cooldown_seconds - time_since_creation)
                return Response({
                    'success': False,
                    'message': f'Please wait {remaining_cooldown} seconds before requesting a new code.',
                    'retry_after': remaining_cooldown
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Hourly rate limit (max 5 OTPs per hour)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        hourly_count = EmailVerificationOTP.objects.filter(user=user, created_at__gte=one_hour_ago).count()
        if hourly_count >= 5:
            return Response({
                'success': False,
                'message': 'Hourly OTP request limit exceeded. Please wait a few minutes before trying again.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Generate fresh OTP and send email
        otp_instance, raw_otp = EmailVerificationOTP.generate_for_user(user)
        email_sent, err_msg = send_verification_otp_email(user, raw_otp)

        if not email_sent:
            return Response({
                'success': False,
                'message': f'Failed to deliver email. Please check configuration or try again shortly.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'message': 'A fresh verification code has been dispatched to your email.'
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        # Consistent response to protect patron privacy
        success_message = "If an account with that email address exists, a 6-digit password recovery code has been sent."

        if not user or not user.is_active:
            return Response({'success': True, 'message': success_message}, status=status.HTTP_200_OK)

        # Rate limiting per email
        now = timezone.now()
        rate_record, created = PasswordResetRateLimit.objects.get_or_create(
            email=email,
            defaults={'last_requested_at': now, 'request_count_hourly': 1}
        )
        if not created:
            time_diff = (now - rate_record.last_requested_at).total_seconds()
            if time_diff < 60:
                # Within 60s cooldown; return success without sending duplicate
                return Response({'success': True, 'message': success_message}, status=status.HTTP_200_OK)

            if time_diff < 3600:
                if rate_record.request_count_hourly >= 5:
                    return Response({
                        'success': False,
                        'message': 'Too many password reset requests. Please try again after an hour.'
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)
                rate_record.request_count_hourly += 1
            else:
                rate_record.request_count_hourly = 1

            rate_record.last_requested_at = now
            rate_record.save()

        # Generate 6-digit OTP and send via official email credentials
        otp_instance, raw_otp = PasswordResetOTP.generate_for_user(user)
        email_sent, err_msg = send_password_reset_otp_email(user, raw_otp)

        if not email_sent:
            logger.error("Failed to deliver password reset OTP to %s: %s", email, err_msg)
            return Response({
                'success': False,
                'message': 'Failed to deliver password recovery email. Please check configuration or try again shortly.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'message': success_message
        }, status=status.HTTP_200_OK)


class VerifyResetOTPView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        candidate_otp = serializer.validated_data['otp'].strip()

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.is_active:
            return Response({
                'success': False,
                'message': 'Invalid verification code or email.'
            }, status=status.HTTP_400_BAD_REQUEST)

        otp_record = PasswordResetOTP.objects.filter(user=user, is_used=False).first()
        if not otp_record:
            return Response({
                'success': False,
                'message': 'No pending password recovery code found. Please request a new code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        is_valid, reset_token, err_msg = otp_record.verify(candidate_otp)
        if not is_valid:
            return Response({
                'success': False,
                'message': err_msg
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': 'Password recovery code verified successfully.',
            'reset_token': reset_token
        }, status=status.HTTP_200_OK)


class ResendResetOTPView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if not user or not user.is_active:
            return Response({
                'success': True,
                'message': 'If this email is registered, a new recovery code has been dispatched.'
            }, status=status.HTTP_200_OK)

        # Cooldown check (60s)
        cooldown_seconds = getattr(settings, 'EMAIL_OTP_COOLDOWN_SECONDS', 60)
        recent_otp = PasswordResetOTP.objects.filter(user=user).order_by('-created_at').first()
        if recent_otp:
            time_since_creation = (timezone.now() - recent_otp.created_at).total_seconds()
            if time_since_creation < cooldown_seconds:
                remaining_cooldown = int(cooldown_seconds - time_since_creation)
                return Response({
                    'success': False,
                    'message': f'Please wait {remaining_cooldown} seconds before requesting a new code.',
                    'retry_after': remaining_cooldown
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Hourly limit
        one_hour_ago = timezone.now() - timedelta(hours=1)
        hourly_count = PasswordResetOTP.objects.filter(user=user, created_at__gte=one_hour_ago).count()
        if hourly_count >= 5:
            return Response({
                'success': False,
                'message': 'Hourly recovery code limit reached. Please wait a few minutes before trying again.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp_instance, raw_otp = PasswordResetOTP.generate_for_user(user)
        email_sent, err_msg = send_password_reset_otp_email(user, raw_otp)

        if not email_sent:
            return Response({
                'success': False,
                'message': 'Failed to deliver email. Please check configuration or try again shortly.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'message': 'A fresh password recovery code has been dispatched to your email.'
        }, status=status.HTTP_200_OK)


class ValidateResetTokenView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = ValidateResetTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'success': False, 'valid': False, 'message': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        is_valid = default_token_generator.check_token(user, token)
        if not is_valid:
            return Response({'success': False, 'valid': False, 'message': 'This password reset link is invalid or has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'valid': True, 'email': user.email}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['new_password']
        reset_token = serializer.validated_data.get('reset_token')
        email = serializer.validated_data.get('email')
        uid = serializer.validated_data.get('uid')
        token = serializer.validated_data.get('token')

        user = None

        # Flow A: Verified OTP session token flow
        if reset_token and email:
            user = User.objects.filter(email__iexact=email.strip().lower()).first()
            if not user or not user.is_active:
                return Response({'success': False, 'message': 'Invalid password reset request.'}, status=status.HTTP_400_BAD_REQUEST)

            otp_record = PasswordResetOTP.objects.filter(
                user=user,
                reset_session_token=reset_token,
                is_verified=True,
                is_used=False
            ).first()

            if not otp_record:
                return Response({
                    'success': False,
                    'message': 'Invalid or expired password reset session. Please request a new verification code.'
                }, status=status.HTTP_400_BAD_REQUEST)

            if timezone.now() > otp_record.expires_at:
                return Response({
                    'success': False,
                    'message': 'Password recovery session has expired. Please restart the recovery process.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate password constraints
            try:
                validate_password(new_password, user)
            except Exception as e:
                return Response({
                    'success': False,
                    'message': 'Password does not meet security requirements.',
                    'errors': {'new_password': list(e)}
                }, status=status.HTTP_400_BAD_REQUEST)

            # Securely hash and update password
            user.set_password(new_password)
            user.save()

            # Invalidate all recovery OTPs for this user
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            PasswordResetOTP.objects.filter(user=user).update(is_used=True)

            return Response({
                'success': True,
                'message': 'Your password has been reset successfully. You may now sign in with your new password.'
            }, status=status.HTTP_200_OK)

        # Flow B: Legacy link-based UID/token flow
        elif uid and token:
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response({'success': False, 'message': 'Invalid reset token.'}, status=status.HTTP_400_BAD_REQUEST)

            if not default_token_generator.check_token(user, token):
                return Response({
                    'success': False,
                    'message': 'This password reset token has expired or has already been used. Please request a new one.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate password constraints
            try:
                validate_password(new_password, user)
            except Exception as e:
                return Response({
                    'success': False,
                    'message': 'Password does not meet security requirements.',
                    'errors': {'new_password': list(e)}
                }, status=status.HTTP_400_BAD_REQUEST)

            # Securely update password (invalidates the token immediately)
            user.set_password(new_password)
            user.save()

            return Response({
                'success': True,
                'message': 'Your password has been reset successfully. You may now sign in with your new password.'
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                'success': False,
                'message': 'Missing reset verification token or credentials.'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = (IsVerifiedUser,)

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'success': True,
            'message': 'Profile updated successfully.',
            'data': serializer.data
        })


class ChangePasswordView(APIView):
    permission_classes = (IsVerifiedUser,)

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                'success': False,
                'message': 'Your current password was entered incorrectly.',
                'errors': {'old_password': ['Incorrect current password.']}
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({
            'success': True,
            'message': 'Your password has been changed successfully.'
        }, status=status.HTTP_200_OK)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = (IsVerifiedUser, IsOwnerOrAdmin)

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        is_first = not Address.objects.filter(user=self.request.user).exists()
        if is_first:
            serializer.save(user=self.request.user, is_default=True)
        else:
            serializer.save(user=self.request.user)


class AdminCustomerListView(generics.ListAPIView):
    permission_classes = (IsAdminRoleUser,)
    serializer_class = UserProfileSerializer

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CUSTOMER).order_by('-created_at')
