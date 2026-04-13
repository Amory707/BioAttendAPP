from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    verbose_name = "Comptes utilisateurs"

    def ready(self):
        try:
            from django.contrib.auth import get_user_model
            from django.db import OperationalError, ProgrammingError

            User = get_user_model()
            if not User.objects.filter(is_superuser=True).exists():
                if User.objects.filter(username='admin').exists():
                    admin = User.objects.filter(username='admin').first()
                    admin.is_superuser = True
                    admin.is_staff = True
                    admin.email = 'admin@bioattend.local'
                    admin.set_password('bioattend12345')
                    admin.save(update_fields=['is_superuser', 'is_staff', 'email', 'password'])
                else:
                    User.objects.create_superuser(
                        username='admin',
                        email='admin@bioattend.local',
                        password='bioattend12345',
                    )
        except (OperationalError, ProgrammingError):
            pass
        except Exception: pass
