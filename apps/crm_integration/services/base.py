import os
import base64
import hashlib
import hmac
import requests
from datetime import timedelta
from urllib.parse import urlencode
from django.utils import timezone


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(64)).rstrip(b'=').decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return code_verifier, code_challenge


class BaseOAuthService:
    def __init__(self, crm_connection=None):
        self.crm_connection = crm_connection
        self.access_token = crm_connection.access_token if crm_connection else None
        self.refresh_token = crm_connection.refresh_token if crm_connection else None

    def _ensure_valid_token(self) -> bool:
        """Refresh token if expired or missing"""
        if not self.access_token or (
            self.crm_connection and self.crm_connection.is_token_expired()
        ):
            return self.refresh_access_token()
        return True

    def _save_lead(self, crm_lead_id, defaults):
        from apps.crm_integration.models import SyncedLead

        create_defaults = {
            "business": self.crm_connection.business,
            "status": "pending",  # new leads start as pending for AI to pick up
            **defaults,
        }
        obj, created = SyncedLead.objects.get_or_create(
            crm_connection=self.crm_connection,
            crm_lead_id=str(crm_lead_id),
            defaults=create_defaults,
        )
        if not created:
            # Update non-status fields only — never overwrite AI-set statuses
            update_fields = {k: v for k, v in defaults.items() if k != "status"}
            update_fields["business"] = self.crm_connection.business
            for attr, val in update_fields.items():
                setattr(obj, attr, val)
            obj.save(update_fields=list(update_fields.keys()) + ["updated_at"])
        else:
            self._notify_new_lead(defaults)
        return created

    def _notify_new_lead(self, lead_data):
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services import notify_business_admins
            name = lead_data.get("name") or "Unknown"
            crm_name = self.crm_connection.get_crm_type_display()
            notify_business_admins(
                business=self.crm_connection.business,
                notification_type=Notification.NotificationType.NEW_LEAD,
                title="New Lead",
                message=f"New lead '{name}' synced from {crm_name}.",
                data={
                    "crm_type": self.crm_connection.crm_type,
                    "name": name,
                    "email": lead_data.get("email"),
                    "phone": lead_data.get("phone"),
                },
            )
        except Exception:
            pass

    def _finish_sync(self, saved, updated):
        from apps.crm_integration.models import SyncedLead
        self.crm_connection.synced_leads_count = SyncedLead.objects.filter(
            crm_connection=self.crm_connection
        ).count()
        self.crm_connection.last_sync_at = timezone.now()
        self.crm_connection.save(update_fields=["synced_leads_count", "last_sync_at"])
        return {"success": True, "saved": saved, "updated": updated}

    def get_oauth_url(self, state):
        raise NotImplementedError

    def exchange_code_for_token(self, code, **_):
        raise NotImplementedError

    def refresh_access_token(self) -> bool:
        raise NotImplementedError

    def verify_webhook_signature(self, body, signature) -> bool:
        raise NotImplementedError

    def configure_webhook(self, webhook_url) -> dict:
        raise NotImplementedError

    def fetch_leads(self):
        raise NotImplementedError

    def sync_leads_to_db(self) -> dict:
        raise NotImplementedError
