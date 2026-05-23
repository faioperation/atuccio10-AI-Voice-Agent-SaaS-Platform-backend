import uuid
from django.db import models
from django.conf import settings
from apps.accounts.models import Business


class SupportTicket(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        DISCUSSED = "discussed", "Discussed"
        SOLVED = "solved", "Solved"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="support_tickets"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tickets",
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING
    )
    ticket_number = models.PositiveIntegerField(unique=True, editable=False, null=True)
    message = models.TextField()
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            from django.db import transaction

            with transaction.atomic():
                last = (
                    SupportTicket.objects.select_for_update()
                    .order_by("ticket_number")
                    .values_list("ticket_number", flat=True)
                    .last()
                )
                self.ticket_number = (last or 0) + 1
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]
        db_table = "support_tickets"

    def __str__(self):
        return f"{self.subject} ({self.status})"
