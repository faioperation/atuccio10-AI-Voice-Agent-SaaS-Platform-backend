import logging
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from apps.ai_integration.authentication import BusinessApiKeyAuthentication
from apps.ai_integration.permissions import IsAIAgent
from apps.ai_integration.serializers import (
    AILeadSerializer,
    LeadStatusUpdateSerializer,
    CallLogCreateSerializer,
    AIBookingCreateSerializer,
)
from apps.ai_integration import schemas

logger = logging.getLogger(__name__)

MAX_LEADS_PER_FETCH = 50


def _business(request):
    """request.auth is the Business instance (set by BusinessApiKeyAuthentication)."""
    return request.auth


# ── Phase 2: Leads Fetch ──────────────────────────────────────────────────────

class AILeadListView(APIView):
    """
    GET /api/ai/leads/
    Returns up to 50 pending leads for the business.
    No query params needed — business resolved from X-API-Key.
    """

    authentication_classes = [BusinessApiKeyAuthentication]
    permission_classes = [IsAIAgent]

    @swagger_auto_schema(**schemas.ai_leads_list_schema)
    def get(self, request):
        from apps.crm_integration.models import SyncedLead

        business = _business(request)
        leads = (
            SyncedLead.objects.filter(business=business, status="pending")
            .select_related("crm_connection")
            .order_by("created_at")[:MAX_LEADS_PER_FETCH]
        )
        data = AILeadSerializer(leads, many=True).data
        return Response({"count": len(data), "results": data})


# ── Phase 3 Step 1: Lock lead ─────────────────────────────────────────────────

class AILeadStatusUpdateView(APIView):
    """
    PATCH /api/ai/leads/{lead_id}/
    AI updates lead status. Call with "calling" to lock before dialing,
    then call again with final status after the call.
    """

    authentication_classes = [BusinessApiKeyAuthentication]
    permission_classes = [IsAIAgent]

    @swagger_auto_schema(**schemas.ai_lead_status_update_schema)
    def patch(self, request, lead_id):
        from apps.crm_integration.models import SyncedLead

        business = _business(request)
        try:
            lead = SyncedLead.objects.get(id=lead_id, business=business)
        except SyncedLead.DoesNotExist:
            return Response({"detail": "Lead not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeadStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lead.status = serializer.validated_data["status"]
        lead.save(update_fields=["status", "updated_at"])

        print(f"[AI] lead {lead_id} → {lead.status} (biz={business.id})")
        return Response({"id": str(lead.id), "status": lead.status})


# ── Phase 3 Step 3: Call Log + Lead Status (atomic) ───────────────────────────

class AICallLogCreateView(APIView):
    """
    POST /api/ai/call-logs/
    Creates a call log. If lead_id + lead_status provided, updates the lead
    status in the same DB transaction (atomic).
    """

    authentication_classes = [BusinessApiKeyAuthentication]
    permission_classes = [IsAIAgent]

    @swagger_auto_schema(**schemas.ai_call_log_create_schema)
    def post(self, request):
        from apps.call_logs.models import CallLog
        from apps.crm_integration.models import SyncedLead

        serializer = CallLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        business = _business(request)
        lead_id = data.get("lead_id")
        lead_status = data.get("lead_status")

        try:
            with transaction.atomic():
                call_log = CallLog.objects.create(
                    business=business,
                    name=data["name"],
                    phone_number=data["phone_number"],
                    location=data.get("location", ""),
                    duration=data["duration"],
                    status=data["status"],
                    audio_url=data.get("audio_url", ""),
                    summary=data.get("summary", ""),
                    transcript=data.get("transcript", []),
                )

                if lead_id and lead_status:
                    updated = SyncedLead.objects.filter(
                        id=lead_id, business=business
                    ).update(status=lead_status)
                    if not updated:
                        raise ValueError(f"Lead {lead_id} not found.")

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"[AI] call-log error: {e}")
            return Response({"detail": "Failed to save call log."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        print(f"[AI] call-log {call_log.id} saved (biz={business.id} lead={lead_id} → {lead_status})")
        return Response(
            {"success": True, "call_log_id": str(call_log.id), "lead_status": lead_status},
            status=status.HTTP_201_CREATED,
        )


# ── Phase 4: Booking ──────────────────────────────────────────────────────────

class AIBookingCreateView(APIView):
    """
    POST /api/ai/bookings/
    Creates a booking. If lead_id provided, atomically sets lead → meeting_scheduled.
    """

    authentication_classes = [BusinessApiKeyAuthentication]
    permission_classes = [IsAIAgent]

    @swagger_auto_schema(**schemas.ai_booking_create_schema)
    def post(self, request):
        from apps.bookings.models import Booking
        from apps.crm_integration.models import SyncedLead

        serializer = AIBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        business = _business(request)
        lead_id = data.get("lead_id")

        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    business=business,
                    meeting_date=data["meeting_date"],
                    meeting_time=data["meeting_time"],
                    meeting_link=data.get("meeting_link", ""),
                    status=data.get("status", "scheduled"),
                    customer_name=data["customer_name"],
                    customer_email=data.get("customer_email", ""),
                    customer_phone=data.get("customer_phone", ""),
                )
                if lead_id:
                    SyncedLead.objects.filter(id=lead_id, business=business).update(
                        status="meeting_scheduled"
                    )

        except Exception as e:
            print(f"[AI] booking error: {e}")
            return Response({"detail": "Failed to save booking."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        print(f"[AI] booking {booking.id} saved (biz={business.id} lead={lead_id})")
        return Response(
            {"success": True, "booking_id": str(booking.id)},
            status=status.HTTP_201_CREATED,
        )
