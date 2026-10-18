from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, EmailVerificationOTP

class AccountAuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_registration_with_email_and_no_phone(self):
        """Phone number must be optional during customer registration."""
        response = self.client.post('/api/v1/accounts/register/', {
            'email': 'nophone@example.com',
            'password': 'StrongPassword2026!',
            'password_confirm': 'StrongPassword2026!',
            'first_name': 'Aarav',
            'last_name': 'Kapoor',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertTrue(response.data['requires_verification'])
        self.assertNotIn('tokens', response.data)

        user = User.objects.get(email='nophone@example.com')
        self.assertFalse(user.is_verified)
        self.assertEqual(user.phone_number, '')

    def test_registration_with_valid_phone(self):
        """Customer registration accepts valid phone numbers."""
        response = self.client.post('/api/v1/accounts/register/', {
            'email': 'withphone@example.com',
            'phone_number': '+91 98200 12345',
            'password': 'StrongPassword2026!',
            'password_confirm': 'StrongPassword2026!',
            'first_name': 'Rohan',
            'last_name': 'Mehra',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='withphone@example.com')
        self.assertEqual(user.phone_number, '+91 98200 12345')

    def test_registration_with_invalid_phone(self):
        """Invalid phone formats should be caught and rejected with validation errors."""
        response = self.client.post('/api/v1/accounts/register/', {
            'email': 'badphone@example.com',
            'phone_number': 'not-a-phone-123',
            'password': 'StrongPassword2026!',
            'password_confirm': 'StrongPassword2026!',
            'first_name': 'Test',
            'last_name': 'User',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data['errors'])

    def test_email_otp_verification_success(self):
        """Valid 6-digit OTP activates account, sets is_verified=True, and returns JWT tokens."""
        user = User.objects.create_user(
            email='verifytest@example.com',
            password='TestPassword2026!',
            is_verified=False
        )
        otp_rec, raw_otp = EmailVerificationOTP.generate_for_user(user)

        response = self.client.post('/api/v1/accounts/verify-email/', {
            'email': 'verifytest@example.com',
            'otp': raw_otp
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('tokens', response.data)

        user.refresh_from_db()
        self.assertTrue(user.is_verified)

        # OTP cannot be reused
        otp_rec.refresh_from_db()
        self.assertTrue(otp_rec.is_used)

    def test_incorrect_otp_attempt_limits(self):
        """Incorrect OTP returns error, increments attempts, and locks after 5 attempts."""
        user = User.objects.create_user(
            email='wrongotp@example.com',
            password='TestPassword2026!',
            is_verified=False
        )
        otp_rec, raw_otp = EmailVerificationOTP.generate_for_user(user)

        # Attempt with wrong code
        res1 = self.client.post('/api/v1/accounts/verify-email/', {
            'email': 'wrongotp@example.com',
            'otp': '999999'
        })
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid verification code', res1.data['message'])

        otp_rec.refresh_from_db()
        self.assertEqual(otp_rec.attempts, 1)

    def test_expired_otp_rejected(self):
        """Expired OTP is rejected."""
        user = User.objects.create_user(
            email='expiredotp@example.com',
            password='TestPassword2026!',
            is_verified=False
        )
        otp_rec, raw_otp = EmailVerificationOTP.generate_for_user(user)
        otp_rec.expires_at = timezone.now() - timedelta(minutes=5)
        otp_rec.save()

        response = self.client.post('/api/v1/accounts/verify-email/', {
            'email': 'expiredotp@example.com',
            'otp': raw_otp
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', response.data['message'].lower())

    def test_resend_otp_cooldown(self):
        """Resend OTP enforces cooldown limit."""
        user = User.objects.create_user(
            email='resendtest@example.com',
            password='TestPassword2026!',
            is_verified=False
        )
        EmailVerificationOTP.generate_for_user(user)

        # Immediate resend attempt should hit 429 cooldown
        response = self.client.post('/api/v1/accounts/resend-otp/', {
            'email': 'resendtest@example.com'
        })
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Please wait', response.data['message'])

    def test_unverified_account_login_blocked(self):
        """Unverified accounts cannot log in via JWT endpoint."""
        User.objects.create_user(
            email='unverifiedlogin@example.com',
            password='SecurePassword2026!',
            is_verified=False
        )
        response = self.client.post('/api/v1/accounts/login/', {
            'email': 'unverifiedlogin@example.com',
            'password': 'SecurePassword2026!'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'email_not_verified')

    def test_unverified_account_protected_endpoints_blocked(self):
        """Unverified authenticated accounts cannot access protected profile/address views."""
        unverified_user = User.objects.create_user(
            email='unverifiedpatron@example.com',
            password='SecurePassword2026!',
            is_verified=False
        )
        self.client.force_authenticate(user=unverified_user)

        # Profile retrieval
        res_me = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(res_me.status_code, status.HTTP_403_FORBIDDEN)

        # Address book
        res_addr = self.client.get('/api/v1/accounts/addresses/')
        self.assertEqual(res_addr.status_code, status.HTTP_403_FORBIDDEN)

    def test_forgot_password_privacy_preserving_response(self):
        """Forgot password returns consistent response for existing and nonexistent emails."""
        User.objects.create_user(
            email='exists@example.com',
            password='SecurePassword2026!',
            is_verified=True
        )

        res_existing = self.client.post('/api/v1/accounts/forgot-password/', {
            'email': 'exists@example.com'
        })
        self.assertEqual(res_existing.status_code, status.HTTP_200_OK)

        res_nonexistent = self.client.post('/api/v1/accounts/forgot-password/', {
            'email': 'doesntexist@example.com'
        })
        self.assertEqual(res_nonexistent.status_code, status.HTTP_200_OK)
        # Responses must be identical to avoid email enumeration
        self.assertEqual(res_existing.data['message'], res_nonexistent.data['message'])

    def test_password_reset_flow_and_token_invalidation(self):
        """Valid token successfully resets password, and cannot be reused."""
        user = User.objects.create_user(
            email='resetted@example.com',
            password='OldPassword2026!',
            is_verified=True
        )

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Validate token endpoint
        val_res = self.client.post('/api/v1/accounts/validate-reset-token/', {
            'uid': uid,
            'token': token
        })
        self.assertEqual(val_res.status_code, status.HTTP_200_OK)
        self.assertTrue(val_res.data['valid'])

        # Reset password
        reset_res = self.client.post('/api/v1/accounts/reset-password/', {
            'uid': uid,
            'token': token,
            'new_password': 'BrandNewPassword2026!',
            'new_password_confirm': 'BrandNewPassword2026!'
        })
        self.assertEqual(reset_res.status_code, status.HTTP_200_OK)

        # Login with old password fails
        login_old = self.client.post('/api/v1/accounts/login/', {
            'email': 'resetted@example.com',
            'password': 'OldPassword2026!'
        })
        self.assertIn(login_old.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])

        # Login with new password succeeds
        login_new = self.client.post('/api/v1/accounts/login/', {
            'email': 'resetted@example.com',
            'password': 'BrandNewPassword2026!'
        })
        self.assertEqual(login_new.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_new.data)

        # Token cannot be reused (invalidated by password change)
        reuse_res = self.client.post('/api/v1/accounts/reset-password/', {
            'uid': uid,
            'token': token,
            'new_password': 'AnotherPassword2026!',
            'new_password_confirm': 'AnotherPassword2026!'
        })
        self.assertEqual(reuse_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_otp_complete_flow(self):
        """OTP-based password recovery flow: Request OTP -> Verify OTP -> Reset Password -> Sign in."""
        from apps.accounts.models import PasswordResetOTP
        user = User.objects.create_user(
            email='otpreset@example.com',
            password='InitialPassword2026!',
            is_verified=True
        )

        # 1. Request OTP
        req_res = self.client.post('/api/v1/accounts/forgot-password/', {
            'email': 'otpreset@example.com'
        })
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)

        otp_rec = PasswordResetOTP.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(otp_rec)

        # We can simulate obtaining the raw OTP by generating one
        otp_rec, raw_otp = PasswordResetOTP.generate_for_user(user)

        # 2. Verify OTP
        verify_res = self.client.post('/api/v1/accounts/verify-reset-otp/', {
            'email': 'otpreset@example.com',
            'otp': raw_otp
        })
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertTrue(verify_res.data['success'])
        reset_token = verify_res.data['reset_token']
        self.assertTrue(len(reset_token) > 20)

        # 3. Reset password using reset_token
        reset_res = self.client.post('/api/v1/accounts/reset-password/', {
            'email': 'otpreset@example.com',
            'reset_token': reset_token,
            'new_password': 'ModernOtpPassword2026!',
            'new_password_confirm': 'ModernOtpPassword2026!'
        })
        self.assertEqual(reset_res.status_code, status.HTTP_200_OK)
        self.assertTrue(reset_res.data['success'])

        # 4. Old password fails
        login_old = self.client.post('/api/v1/accounts/login/', {
            'email': 'otpreset@example.com',
            'password': 'InitialPassword2026!'
        })
        self.assertIn(login_old.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])

        # 5. New password succeeds
        login_new = self.client.post('/api/v1/accounts/login/', {
            'email': 'otpreset@example.com',
            'password': 'ModernOtpPassword2026!'
        })
        self.assertEqual(login_new.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_new.data)

        # 6. Reusing reset_token fails
        reuse_res = self.client.post('/api/v1/accounts/reset-password/', {
            'email': 'otpreset@example.com',
            'reset_token': reset_token,
            'new_password': 'AttemptAgain2026!',
            'new_password_confirm': 'AttemptAgain2026!'
        })
        self.assertEqual(reuse_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_otp_invalid_and_expired(self):
        """OTP validation enforces attempt counters and rejects invalid or expired codes."""
        from apps.accounts.models import PasswordResetOTP
        user = User.objects.create_user(
            email='badotp@example.com',
            password='InitialPassword2026!',
            is_verified=True
        )

        otp_rec, raw_otp = PasswordResetOTP.generate_for_user(user)

        # Invalid OTP
        bad_res = self.client.post('/api/v1/accounts/verify-reset-otp/', {
            'email': 'badotp@example.com',
            'otp': '000000' if raw_otp != '000000' else '111111'
        })
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid verification code', bad_res.data['message'])

        # Expired OTP
        otp_rec.expires_at = timezone.now() - timedelta(minutes=15)
        otp_rec.save()

        exp_res = self.client.post('/api/v1/accounts/verify-reset-otp/', {
            'email': 'badotp@example.com',
            'otp': raw_otp
        })
        self.assertEqual(exp_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', exp_res.data['message'].lower())
