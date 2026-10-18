from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', _('Customer')
        STAFF = 'staff', _('Staff')
        ADMIN = 'admin', _('Administrator')

    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    @property
    def is_admin_user(self):
        return self.is_superuser or self.is_staff or self.role == self.Role.ADMIN

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    receive_marketing_emails = models.BooleanField(default=True)
    receive_sms_updates = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.email}"

    @property
    def display_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.user.email.split('@')[0].capitalize()

class Address(models.Model):
    class AddressType(models.TextChoices):
        SHIPPING = 'shipping', _('Shipping')
        BILLING = 'billing', _('Billing')
        BOTH = 'both', _('Both')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    street_address = models.CharField(max_length=255)
    apartment_suite = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    address_type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.SHIPPING)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.street_address}, {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Clear any other default address for this user
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class EmailVerificationOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_otps')
    otp_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} (expires: {self.expires_at})"

    @classmethod
    def generate_for_user(cls, user):
        """
        Generates a cryptographically random 6-digit OTP, securely hashes it,
        stores the record, and returns (otp_instance, raw_otp).
        """
        import secrets
        # Mark previous active OTPs as used/superseded
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        raw_otp = f"{secrets.randbelow(900000) + 100000}"
        from django.contrib.auth.hashers import make_password
        from django.utils import timezone
        from django.conf import settings
        
        expiry_seconds = getattr(settings, 'EMAIL_OTP_EXPIRY_SECONDS', 600)
        expires_at = timezone.now() + timezone.timedelta(seconds=expiry_seconds)

        otp_instance = cls.objects.create(
            user=user,
            otp_hash=make_password(raw_otp),
            expires_at=expires_at,
            attempts=0,
            is_used=False
        )
        return otp_instance, raw_otp

    def verify(self, candidate_otp):
        """
        Verifies the given candidate OTP.
        Returns (is_valid: bool, error_message: str | None).
        """
        from django.contrib.auth.hashers import check_password
        from django.utils import timezone

        if self.is_used:
            return False, "This verification code has already been used. Please request a new one."

        if timezone.now() > self.expires_at:
            return False, "This verification code has expired. Please request a new one."

        if self.attempts >= 5:
            self.is_used = True
            self.save(update_fields=['is_used'])
            return False, "Too many incorrect attempts. Please request a new verification code."

        self.attempts += 1
        self.save(update_fields=['attempts'])

        if check_password(candidate_otp, self.otp_hash):
            self.is_used = True
            self.save(update_fields=['is_used'])
            return True, None

        remaining = 5 - self.attempts
        return False, f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."


class PasswordResetRateLimit(models.Model):
    email = models.EmailField(unique=True)
    last_requested_at = models.DateTimeField(auto_now=True)
    request_count_hourly = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-last_requested_at']

    def __str__(self):
        return f"RateLimit: {self.email} ({self.request_count_hourly}/hr)"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
    otp_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    reset_session_token = models.CharField(max_length=64, blank=True, null=True, unique=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['reset_session_token']),
        ]

    def __str__(self):
        return f"PasswordResetOTP for {self.user.email} (verified={self.is_verified}, used={self.is_used})"

    @classmethod
    def generate_for_user(cls, user):
        """
        Generates a cryptographically random 6-digit OTP for password recovery,
        hashes it, stores the record, and returns (otp_instance, raw_otp).
        """
        import secrets
        from django.contrib.auth.hashers import make_password
        from django.utils import timezone
        from django.conf import settings

        # Invalidate previous unused OTPs for this user
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        raw_otp = f"{secrets.randbelow(900000) + 100000}"
        expiry_seconds = getattr(settings, 'EMAIL_OTP_EXPIRY_SECONDS', 600)
        expires_at = timezone.now() + timezone.timedelta(seconds=expiry_seconds)

        otp_instance = cls.objects.create(
            user=user,
            otp_hash=make_password(raw_otp),
            expires_at=expires_at,
            attempts=0,
            is_verified=False,
            is_used=False
        )
        return otp_instance, raw_otp

    def verify(self, candidate_otp):
        """
        Verifies the given candidate OTP.
        Returns (is_valid: bool, reset_token: str | None, error_message: str | None).
        """
        from django.contrib.auth.hashers import check_password
        from django.utils import timezone
        import secrets

        if self.is_used:
            return False, None, "This password reset code has already been used. Please request a new one."

        if timezone.now() > self.expires_at:
            return False, None, "This password reset code has expired. Please request a new one."

        if self.attempts >= 5:
            self.is_used = True
            self.save(update_fields=['is_used'])
            return False, None, "Too many incorrect attempts. Please request a new password recovery code."

        self.attempts += 1
        self.save(update_fields=['attempts'])

        if check_password(candidate_otp, self.otp_hash):
            reset_token = secrets.token_urlsafe(32)
            self.is_verified = True
            self.reset_session_token = reset_token
            self.save(update_fields=['is_verified', 'reset_session_token'])
            return True, reset_token, None

        remaining = 5 - self.attempts
        return False, None, f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."


