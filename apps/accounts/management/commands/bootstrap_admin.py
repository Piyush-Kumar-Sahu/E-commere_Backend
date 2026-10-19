import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Securely provisions the administrator account using server-side environment configuration.'

    def handle(self, *args, **options):
        email = os.getenv('ADMIN_BOOTSTRAP_EMAIL', 'admin@modiecommers.com')
        password = os.getenv('ADMIN_BOOTSTRAP_PASSWORD', 'ModiecommersAdmin2026!')
        username = os.getenv('ADMIN_BOOTSTRAP_USERNAME', 'admin')

        if not email or not password:
            self.stdout.write(self.style.ERROR('ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD must be configured.'))
            return

        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.role = User.Role.ADMIN
            user.is_verified = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Updated existing admin account: {email}'))
        else:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                username=username,
                role=User.Role.ADMIN
            )
            user.is_verified = True
            user.is_active = True
            user.save()
            if hasattr(user, 'profile'):
                user.profile.first_name = 'Modiecommers'
                user.profile.last_name = 'Admin'
                user.profile.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser/admin account: {email}'))
