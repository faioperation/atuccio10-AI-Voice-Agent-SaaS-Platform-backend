import secrets
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ── 1. Auto-generate api_key for new businesses ───────────────────────────────


@receiver(post_save, sender="accounts.Business")
def generate_api_key(sender, instance, created, **kwargs):
    """Auto-generate a unique api_key for every new Business."""
    if created and not instance.api_key:
        instance.api_key = "fai_op_" + secrets.token_hex(24)
        instance.save(update_fields=["api_key"])
        print(f"[AI] api_key generated for business {instance.id}")


# ── 2. Provision trigger — fires when each config piece is saved ──────────────
#
# We try to provision after every config save.
# provision_service._check_provision_ready() checks all 6 conditions
# and silently returns None if not all done yet.


def _try_provision(business):
    """Fire-and-forget provision attempt. Runs synchronously (no Celery needed)."""
    from apps.ai_integration.provision_service import provision_business

    result = provision_business(business)
    if not result.get("success"):
        errors = result.get("errors", [])
        if errors and errors != ["Business setup incomplete."]:
            _notify_provision_failed(business, errors)


def _notify_provision_failed(business, errors):
    """Send dashboard notification to business admins on AI provision failure."""
    try:
        from apps.notifications.services import notify_business_admins
        from apps.notifications.models import Notification

        notify_business_admins(
            business=business,
            notification_type=Notification.NotificationType.SYSTEM_ALERT,
            title="AI Setup Failed",
            message=f"AI agent could not be provisioned: {'; '.join(errors)}",
            data={"errors": errors},
        )
    except Exception as e:
        print(f"[AI] failed to send provision-failed notification: {e}")


@receiver(post_save, sender="configuration.TwilioConfig")
def on_twilio_saved(sender, instance, **kwargs):
    _try_provision(instance.business)

    from apps.ai_integration.provision_service import push_config_update

    push_config_update(
        instance.business,
        {
            "twilio": {
                "twilio_sid": instance.twilio_sid,
                "twilio_token": instance.twilio_token,
                "twilio_number": instance.twilio_number,
            }
        },
    )


@receiver(post_save, sender="configuration.VoiceConfig")
def on_voice_saved(sender, instance, **kwargs):
    _try_provision(instance.business)

    from apps.ai_integration.provision_service import push_config_update
    from django.conf import settings as s

    def _file_url(f):
        if not f:
            return None
        base = getattr(s, "BACKEND_BASE_URL", "").rstrip("/")
        return f"{base}{s.MEDIA_URL.rstrip('/')}/{f.name}" if base else f.url

    push_config_update(
        instance.business,
        {
            "voice": {
                "gender": instance.gender,
                "tone": instance.tone,
                "voice_template_url": _file_url(instance.voice_template),
            }
        },
    )


@receiver(post_save, sender="configuration.KnowledgeFile")
def on_knowledge_file_saved(sender, instance, created, **kwargs):
    _try_provision(instance.business)

    from apps.ai_integration.provision_service import push_config_update
    from django.conf import settings as s

    def _file_url(f):
        if not f:
            return None
        base = getattr(s, "BACKEND_BASE_URL", "").rstrip("/")
        return f"{base}{s.MEDIA_URL.rstrip('/')}/{f.name}" if base else f.url

    push_config_update(
        instance.business,
        {
            "knowledge_files": [
                {
                    "id": str(instance.id),
                    "file_url": _file_url(instance.file),
                    "file_type": instance.file_type,
                    "action": "add",
                }
            ]
        },
    )
