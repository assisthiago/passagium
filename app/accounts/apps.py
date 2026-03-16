from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "app.accounts"
    verbose_name = "Gerenciamento da conta"

    def ready(self):
        # Import signal handlers to ensure they're registered
        import app.accounts.signals  # noqa: F401
