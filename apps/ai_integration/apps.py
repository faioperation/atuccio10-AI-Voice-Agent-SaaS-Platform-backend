from django.apps import AppConfig


class AiIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_integration"
    verbose_name = "AI Integration"

    def ready(self):
        import apps.ai_integration.signals  # noqa: F401
