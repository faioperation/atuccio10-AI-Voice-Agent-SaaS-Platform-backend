import uuid
import json
from django.http import HttpResponse
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

from core.permissions import IsBusinessAdmin, HasActiveSubscription
from apps.crm_integration.services import get_oauth_service
from apps.crm_integration.services.webhook_handlers import (
    dispatch,
    parse_salesforce_soap,
)
from apps.crm_integration.services.connection_service import process_oauth_callback
from apps.crm_integration.models import CRMConnection, CRMWebhookLog, SyncedLead
from apps.crm_integration.serializers import (
    CRMConnectionSerializer,
    SyncedLeadSerializer,
)
from apps.crm_integration import schemas
from core.pagination import DynamicPageNumberPagination

SUPPORTED_CRMS = ["hubspot", "salesforce", "zoho", "pipedrive", "ghl"]

SALESFORCE_ACK = (
    '<?xml version="1.0"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soapenv:Body>"
    '<notificationsResponse xmlns="http://soap.sforce.com/2005/09/outbound">'
    "<Ack>true</Ack>"
    "</notificationsResponse>"
    "</soapenv:Body>"
    "</soapenv:Envelope>"
)


class CRMOAuthURLView(APIView):
    permission_classes = [IsBusinessAdmin, HasActiveSubscription]

    @swagger_auto_schema(**schemas.crm_oauth_url_schema)
    def get(self, request, crm_type):
        if crm_type not in SUPPORTED_CRMS:
            return Response(
                {"success": False, "error": f"Unsupported CRM: {crm_type}"}, status=400
            )
        try:
            state = str(uuid.uuid4())
            request.session[f"oauth_state_{crm_type}"] = state

            service = get_oauth_service(crm_type)
            result = service.get_oauth_url(state)

            if isinstance(result, tuple):
                oauth_url, code_verifier = result
                request.session[f"pkce_verifier_{crm_type}"] = code_verifier
            else:
                oauth_url = result

            return Response(
                {"success": True, "authorization_url": oauth_url, "state": state}
            )
        except NotImplementedError as e:
            return Response({"success": False, "error": str(e)}, status=501)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)


class CRMOAuthCallbackView(APIView):
    permission_classes = [IsBusinessAdmin, HasActiveSubscription]

    @swagger_auto_schema(auto_schema=None)
    @transaction.atomic
    def get(self, request, crm_type):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            return Response(
                {"success": False, "error": f"OAuth error: {error}"}, status=400
            )
        if not code or not state:
            return Response(
                {"success": False, "error": "Missing code or state"}, status=400
            )

        stored_state = request.session.get(f"oauth_state_{crm_type}")

        try:

            def build_webhook_url(ct):
                return f"{request.build_absolute_uri('/api/crm/webhook/')}{ct}/"

            code_verifier = request.session.get(f"pkce_verifier_{crm_type}")
            result, err, http_status = process_oauth_callback(
                crm_type,
                code,
                state,
                stored_state,
                request.user,
                build_webhook_url,
                code_verifier=code_verifier,
            )
            if err:
                return Response({"success": False, "error": err}, status=http_status)

            request.session.pop(f"oauth_state_{crm_type}", None)
            request.session.pop(f"pkce_verifier_{crm_type}", None)
            return Response(result)
        except NotImplementedError as e:
            return Response({"success": False, "error": str(e)}, status=501)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)


class CRMConnectionListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(**schemas.crm_connections_list_schema)
    def get(self, request):
        business = request.user.business
        if not business:
            return Response(
                {"success": False, "error": "No business found"}, status=400
            )
        connections = CRMConnection.objects.filter(business=business, is_active=True)
        return Response(
            {
                "success": True,
                "data": CRMConnectionSerializer(connections, many=True).data,
            }
        )


class CRMDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(**schemas.crm_disconnect_schema)
    def delete(self, request, connection_id):
        try:
            conn = CRMConnection.objects.get(id=connection_id, user=request.user)
            conn.is_active = False
            conn.save(update_fields=["is_active"])
            return Response(
                {
                    "success": True,
                    "message": f"{conn.get_crm_type_display()} disconnected",
                }
            )
        except CRMConnection.DoesNotExist:
            return Response(
                {"success": False, "error": "Connection not found"}, status=404
            )


class CRMSyncView(APIView):
    permission_classes = [IsBusinessAdmin, HasActiveSubscription]

    @swagger_auto_schema(**schemas.crm_sync_schema)
    def post(self, request, connection_id):
        try:
            business = request.user.business
            conn = CRMConnection.objects.get(
                id=connection_id, business=business, is_active=True
            )
            result = get_oauth_service(conn.crm_type, conn).sync_leads_to_db()
            return Response(result)
        except CRMConnection.DoesNotExist:
            return Response(
                {"success": False, "error": "Connection not found"}, status=404
            )
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)


class CRMSyncAllView(APIView):
    permission_classes = [IsBusinessAdmin, HasActiveSubscription]

    @swagger_auto_schema(**schemas.crm_sync_all_schema)
    def post(self, request):
        try:
            business = request.user.business
            if not business:
                return Response(
                    {"success": False, "error": "No business found"}, status=400
                )

            connections = CRMConnection.objects.filter(
                business=business, is_active=True
            )
            if not connections.exists():
                return Response(
                    {"success": False, "error": "No active CRM connections found"},
                    status=404,
                )

            results = {}
            for conn in connections:
                try:
                    result = get_oauth_service(conn.crm_type, conn).sync_leads_to_db()
                    results[str(conn.id)] = {
                        "crm_type": conn.crm_type,
                        "result": result,
                    }
                except Exception as e:
                    results[str(conn.id)] = {
                        "crm_type": conn.crm_type,
                        "result": {"success": False, "error": str(e)},
                    }

            total_saved = sum(
                r["result"].get("saved", 0)
                for r in results.values()
                if r["result"].get("success")
            )
            total_updated = sum(
                r["result"].get("updated", 0)
                for r in results.values()
                if r["result"].get("success")
            )
            total_errors = sum(
                1 for r in results.values() if not r["result"].get("success")
            )

            return Response(
                {
                    "success": True,
                    "total_connections": len(results),
                    "total_saved": total_saved,
                    "total_updated": total_updated,
                    "total_errors": total_errors,
                    "details": results,
                }
            )
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)


class CRMWebhookView(APIView):

    @swagger_auto_schema(**schemas.crm_webhook_schema)
    def post(self, request, crm_type):
        try:
            conn = CRMConnection.objects.filter(
                crm_type=crm_type, is_active=True
            ).first()
            if not conn:
                return Response(
                    {"success": False, "error": "No active connection"}, status=404
                )

            body = (
                request.body.decode()
                if isinstance(request.body, bytes)
                else request.body
            )
            content_type = request.content_type or ""

            if crm_type == "salesforce" and (
                "xml" in content_type or body.strip().startswith("<")
            ):
                data = parse_salesforce_soap(body)
            else:
                data = request.data if hasattr(request, "data") else json.loads(body)

            import logging

            logger = logging.getLogger(__name__)
            logger.info("[WEBHOOK] CRM: %s | DATA: %s", crm_type, data)

            CRMWebhookLog.objects.create(
                crm_connection=conn,
                event_type="new_lead",
                raw_data=data if isinstance(data, dict) else {"events": data},
            )

            dispatch(crm_type, conn, data)

            if crm_type == "salesforce":
                return HttpResponse(SALESFORCE_ACK, content_type="text/xml")

            return Response(
                {"success": True, "message": f"Webhook from {crm_type} processed"}
            )
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)


class CRMSyncIntervalView(APIView):
    """
    PATCH /api/crm/connections/<connection_id>/sync-interval/
    Business admin sets polling interval (minutes) for non-webhook CRMs
    (Pipedrive, Salesforce). Allowed range: 1–120 minutes.
    """

    permission_classes = [IsBusinessAdmin]

    POLLING_CRMS = {"pipedrive", "salesforce"}
    MIN_INTERVAL = 60
    MAX_INTERVAL = 1440

    @swagger_auto_schema(**schemas.crm_sync_interval_schema)
    def patch(self, request, connection_id):
        try:
            conn = CRMConnection.objects.get(
                id=connection_id,
                business=request.user.business,
                is_active=True,
            )
        except CRMConnection.DoesNotExist:
            return Response({"detail": "Connection not found."}, status=404)

        if conn.crm_type not in self.POLLING_CRMS:
            return Response(
                {
                    "detail": f"Sync interval is only configurable for polling-based CRMs: {', '.join(sorted(self.POLLING_CRMS))}."
                },
                status=400,
            )

        interval = request.data.get("interval_minutes")
        if interval is None:
            return Response({"detail": "interval_minutes is required."}, status=400)

        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return Response(
                {"detail": "interval_minutes must be an integer."}, status=400
            )

        if interval < self.MIN_INTERVAL:
            return Response(
                {
                    "detail": f"interval_minutes must be at least {self.MIN_INTERVAL} minutes."
                },
                status=400,
            )

        if interval > self.MAX_INTERVAL:
            return Response(
                {
                    "detail": f"interval_minutes cannot exceed {self.MAX_INTERVAL} minutes."
                },
                status=400,
            )

        conn.interval_minutes = interval
        conn.save(update_fields=["interval_minutes", "updated_at"])

        return Response(
            {
                "detail": f"Sync interval updated to {interval} minute(s).",
                "crm_type": conn.crm_type,
                "interval_minutes": interval,
            }
        )


class SyncedLeadsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(**schemas.crm_leads_list_schema)
    def get(self, request):
        business = request.user.business
        crm_type = request.query_params.get("crm_type")

        qs = (
            SyncedLead.objects.filter(business=business)
            .select_related("crm_connection")
            .order_by("-created_at")
        )
        if crm_type:
            qs = qs.filter(crm_connection__crm_type=crm_type)

        paginator = DynamicPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            SyncedLeadSerializer(page, many=True).data
        )
