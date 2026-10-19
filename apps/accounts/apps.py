import os
from django.apps import AppConfig
from django.db.models.signals import post_migrate

def auto_bootstrap_admin_callback(sender, **kwargs):
    import sys
    if 'test' in sys.argv:
        return
    email = os.getenv('ADMIN_BOOTSTRAP_EMAIL')
    password = os.getenv('ADMIN_BOOTSTRAP_PASSWORD')
    if email and password and sender.name == 'apps.accounts':
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User.objects.create_superuser(
                    email=email,
                    password=password,
                    username=os.getenv('ADMIN_BOOTSTRAP_USERNAME', 'admin'),
                    role=User.Role.ADMIN,
                    is_verified=True,
                    is_active=True,
                )
                if hasattr(user, 'profile'):
                    user.profile.first_name = 'Modiecommers'
                    user.profile.last_name = 'Admin'
                    user.profile.save()
        except Exception:
            pass

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        import apps.accounts.signals  # noqa
        post_migrate.connect(auto_bootstrap_admin_callback, sender=self)

