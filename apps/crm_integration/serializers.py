from rest_framework import serializers
from apps.crm_integration.models import CRMConnection, SyncedLead, CRMWebhookLog


class CRMConnectionSerializer(serializers.ModelSerializer):
    crm_name = serializers.CharField(source="get_crm_type_display", read_only=True)

    class Meta:
        model = CRMConnection
        fields = [
            "id",
            "crm_type",
            "crm_name",
            "is_active",
            "synced_leads_count",
            "last_sync_at",
            "interval_minutes",
            "created_at",
        ]


class SyncedLeadSerializer(serializers.ModelSerializer):
    crm_type = serializers.CharField(source="crm_connection.crm_type", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = SyncedLead
        fields = [
            "id",
            "crm_type",
            "crm_lead_id",
            "name",
            "email",
            "phone",
            "last_synced_at",
            "created_at",
            "status",
        ]

    def get_status(self, obj):
        return obj.status or "pending"


class CRMWebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMWebhookLog
        fields = [
            "id",
            "event_type",
            "processed",
            "processed_at",
            "error_message",
            "created_at",
        ]
