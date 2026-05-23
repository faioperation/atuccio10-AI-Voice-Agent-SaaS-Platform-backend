from django.db import models
from apps.accounts.models import Business


class Booking(models.Model):

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="bookings"
    )

    meeting_date = models.DateField()
    meeting_time = models.TimeField()
    meeting_link = models.URLField(max_length=500, blank=True, null=True)
    status = models.CharField(
        max_length=100, blank=True, null=True, help_text="Status decided by AI"
    )

    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking for {self.customer_name} on {self.meeting_date} at {self.meeting_time}"

    class Meta:
        ordering = ["-meeting_date", "-meeting_time"]
