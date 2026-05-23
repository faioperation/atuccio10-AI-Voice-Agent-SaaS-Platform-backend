import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        # System Admin
        NEW_BUSINESS_REGISTERED = "new_business_registered", "New Business Registered"
        BUSINESS_PAYMENT = "business_payment", "Business Payment Received"
        BUSINESS_SUPPORT_TICKET = (
            "business_support_ticket",
            "Business Support Ticket Created",
        )

        # Business Admin
        NEW_CALL_LOG = "new_call_log", "New Call Log"
        NEW_LEAD = "new_lead", "New Lead"
        NEW_APPOINTMENT = "new_appointment", "New Appointment"
        MEETING_REMINDER = "meeting_reminder", "Meeting Reminder"
        SUBSCRIPTION_ACTIVATED = "subscription_activated", "Subscription Activated"
        SUBSCRIPTION_EXPIRY = "subscription_expiry", "Subscription Expiry Warning"
        SUPPORT_TICKET_UPDATED = "support_ticket_updated", "Support Ticket Updated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=50, choices=NotificationType.choices
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "notifications"

    def __str__(self):
        state = "read" if self.is_read else "unread"
        return f"{self.recipient} — {self.notification_type} ({state})"
