from rest_framework import serializers
from apps.crm_integration.models import SyncedLead


# ── Leads ────────────────────────────────────────────────────────────────────

VALID_LEAD_STATUSES = {"done", "not_interested", "no_answer", "meeting_scheduled"}


class AILeadSerializer(serializers.ModelSerializer):
    crm_type = serializers.CharField(source="crm_connection.crm_type", read_only=True)

    class Meta:
        model = SyncedLead
        fields = ["id", "name", "email", "phone", "crm_type", "status", "last_synced_at"]


class LeadStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=sorted(VALID_LEAD_STATUSES))


# ── Call Log ─────────────────────────────────────────────────────────────────

class CallLogCreateSerializer(serializers.Serializer):
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    lead_status = serializers.ChoiceField(
        choices=["done", "not_interested", "no_answer", "meeting_scheduled"],
        required=False,
        allow_null=True,
    )

    name = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=30)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    duration = serializers.CharField(max_length=20)
    status = serializers.CharField(max_length=100)
    audio_url = serializers.URLField(required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)
    transcript = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
    )


# ── Booking ──────────────────────────────────────────────────────────────────

class AIBookingCreateSerializer(serializers.Serializer):
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    meeting_date = serializers.DateField()
    meeting_time = serializers.TimeField()
    meeting_link = serializers.URLField(required=False, allow_blank=True)
    status = serializers.CharField(max_length=50, default="scheduled")
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
