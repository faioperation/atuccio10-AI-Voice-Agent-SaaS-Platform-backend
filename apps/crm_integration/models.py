import uuid
from django.db import models
from cryptography.fernet import Fernet
from decouple import config
from apps.accounts.models import CustomUser, Business


class EncryptedField(models.TextField):
    """Custom field to store encrypted data"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cipher_suite = Fernet(config("ENCRYPTION_KEY").encode())

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, bytes):
            return self.cipher_suite.encrypt(value).decode()
        return self.cipher_suite.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression=None, connection=None):
        if value is None:
            return None
        try:
            return self.cipher_suite.decrypt(value.encode()).decode()
        except Exception:
            return value


class CRMConnection(models.Model):
    """Model to store user's CRM connection details"""

    CRM_CHOICES = (
        ("hubspot", "HubSpot"),
        ("salesforce", "Salesforce"),
        ("zoho", "Zoho CRM"),
        ("ghl", "GoHighLevel"),
        ("pipedrive", "Pipedrive"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="crm_connections"
    )
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="crm_connections"
    )

    crm_type = models.CharField(max_length=20, choices=CRM_CHOICES)

    # Encrypted tokens
    access_token = EncryptedField()
    refresh_token = EncryptedField(null=True, blank=True)

    # Token expiration
    access_token_expires_at = models.DateTimeField(null=True, blank=True)

    # Webhook configuration
    webhook_url = models.CharField(max_length=500, null=True, blank=True)
    webhook_secret = models.CharField(max_length=255, null=True, blank=True)
    webhook_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # CRM এর webhook ID

    # CRM-specific info
    crm_account_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # CRM এর account/location ID
    crm_user_email = models.EmailField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    synced_leads_count = models.IntegerField(default=0)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    interval_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Polling interval in minutes for non-webhook CRMs (1–120). Leave blank to use default (60 min).",
    )

    raw_config = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "crm_type")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["business", "crm_type"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.get_crm_type_display()}"

    def is_token_expired(self):
        """Check if access token is expired"""
        from django.utils import timezone

        if self.access_token_expires_at is None:
            return False
        return timezone.now() >= self.access_token_expires_at


class CRMWebhookLog(models.Model):
    """Model to log all webhook events from CRMs"""

    EVENT_TYPE_CHOICES = (
        ("new_lead", "New Lead"),
        ("update_lead", "Update Lead"),
        ("delete_lead", "Delete Lead"),
        ("new_contact", "New Contact"),
        ("update_contact", "Update Contact"),
        ("other", "Other Event"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crm_connection = models.ForeignKey(
        CRMConnection, on_delete=models.CASCADE, related_name="webhook_logs"
    )

    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    raw_data = models.JSONField()

    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    crm_event_id = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["crm_connection", "processed"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.crm_connection.get_crm_type_display()} - {self.event_type} - {self.created_at}"


class SyncedLead(models.Model):
    """Model to store leads synced from CRMs"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="synced_leads"
    )
    crm_connection = models.ForeignKey(
        CRMConnection, on_delete=models.CASCADE, related_name="synced_leads"
    )

    crm_lead_id = models.CharField(max_length=255)
    crm_object_type = models.CharField(max_length=50, default="lead")

    name = models.CharField(max_length=511, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    company = models.CharField(max_length=255, null=True, blank=True)

    source = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=100, null=True, blank=True)
    stage = models.CharField(max_length=100, null=True, blank=True)

    raw_data = models.JSONField(default=dict)

    last_synced_at = models.DateTimeField(auto_now=True)
    is_duplicate = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("crm_connection", "crm_lead_id")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "email"]),
            models.Index(fields=["crm_connection", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.name} ({self.email})" if self.name else f"Lead {self.crm_lead_id}"
        )


class CRMSyncState(models.Model):
    """Track sync state for each CRM connection"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crm_connection = models.OneToOneField(
        CRMConnection, on_delete=models.CASCADE, related_name="sync_state"
    )

    last_leads_sync = models.DateTimeField(null=True, blank=True)
    last_contacts_sync = models.DateTimeField(null=True, blank=True)

    total_leads_synced = models.IntegerField(default=0)
    total_contacts_synced = models.IntegerField(default=0)

    is_syncing = models.BooleanField(default=False)
    last_sync_error = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sync State - {self.crm_connection}"
