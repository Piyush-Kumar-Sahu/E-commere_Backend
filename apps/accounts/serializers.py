import re
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .models import User, Profile, Address

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        # Check if customer account is verified
        if not self.user.is_verified and not self.user.is_admin_user:
            raise serializers.ValidationError({
                "detail": "Email verification is required before accessing your account.",
                "code": "email_not_verified",
                "email": self.user.email
            })

        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'role': self.user.role,
            'is_verified': self.user.is_verified,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
            'is_admin': self.user.is_admin_user,
            'display_name': self.user.profile.display_name if hasattr(self.user, 'profile') else self.user.email.split('@')[0],
            'first_name': self.user.profile.first_name if hasattr(self.user, 'profile') else '',
            'last_name': self.user.profile.last_name if hasattr(self.user, 'profile') else '',
        }
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'phone_number', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate_phone_number(self, value):
        if not value:
            return ''
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if not re.match(r'^\+?[0-9]{10,15}$', cleaned):
            raise serializers.ValidationError("Please provide a valid phone number with 10-15 digits, or leave it blank.")
        return value.strip()

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')

        # Unverified account created upon registration
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            phone_number=validated_data.get('phone_number', '') or '',
            is_verified=False
        )
        if hasattr(user, 'profile'):
            user.profile.first_name = first_name
            user.profile.last_name = last_name
            user.profile.save()
        return user

class VerifyEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_otp(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Verification code must be exactly 6 numeric digits.")
        return value

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_otp(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Password recovery code must be exactly 6 numeric digits.")
        return value

class ResetPasswordWithOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    reset_token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "The password confirmation does not match."})
        return attrs

class ValidateResetTokenSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)

class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    reset_token = serializers.CharField(required=False, allow_blank=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "The password confirmation does not match."})
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='profile.first_name', allow_blank=True, required=False)
    last_name = serializers.CharField(source='profile.last_name', allow_blank=True, required=False)
    display_name = serializers.ReadOnlyField(source='profile.display_name')
    avatar = serializers.ImageField(source='profile.avatar', required=False, allow_null=True)
    receive_marketing_emails = serializers.BooleanField(source='profile.receive_marketing_emails', required=False)
    receive_sms_updates = serializers.BooleanField(source='profile.receive_sms_updates', required=False)
    is_admin = serializers.ReadOnlyField(source='is_admin_user')

    class Meta:
        model = User
        fields = (
            'id', 'email', 'phone_number', 'role', 'is_verified', 'is_staff', 'is_superuser',
            'is_admin', 'first_name', 'last_name', 'display_name', 'avatar',
            'receive_marketing_emails', 'receive_sms_updates', 'created_at'
        )
        read_only_fields = ('id', 'email', 'role', 'is_verified', 'is_staff', 'is_superuser', 'is_admin', 'created_at')

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)
        instance.save()

        profile = instance.profile
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "The new password confirmation does not match."})
        return attrs

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            'id', 'full_name', 'phone', 'street_address', 'apartment_suite',
            'city', 'state', 'postal_code', 'country', 'address_type',
            'is_default', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
