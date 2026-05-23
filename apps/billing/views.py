import logging
import stripe
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.billing.models import Plan, PlanPrice, Subscription, Invoice
from apps.billing.serializers import (
    PlanListSerializer,
    PlanWriteSerializer,
    SubscriptionSerializer,
    SubscribeSerializer,
    CancelSubscriptionSerializer,
    SwitchPlanSerializer,
    InvoiceSerializer,
)
from apps.billing.services.stripe_service import StripeService
from apps.billing.services.subscription_service import SubscriptionService
from apps.system_admin.permissions import IsSystemAdmin
from core.permissions import IsBusinessAdmin
from drf_yasg.utils import swagger_auto_schema
from apps.billing import schemas

logger = logging.getLogger(__name__)


class PlanListView(generics.ListAPIView):
    """
    GET /api/billing/plans/
    Public — list all active plans with prices & features.
    """

    @swagger_auto_schema(**schemas.plan_list_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    serializer_class = PlanListSerializer
    permission_classes = [AllowAny]
    queryset = Plan.objects.filter(is_active=True).prefetch_related(
        "prices", "features"
    )


class PlanDetailView(generics.RetrieveAPIView):
    """
    GET /api/billing/plans/{id}/
    Public — single plan detail.
    """

    @swagger_auto_schema(
        tags=[schemas.BILLING_PUBLIC_TAG], operation_summary="Get Plan Detail"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    serializer_class = PlanListSerializer
    permission_classes = [AllowAny]
    queryset = Plan.objects.filter(is_active=True).prefetch_related(
        "prices", "features"
    )


class AdminPlanCreateView(generics.CreateAPIView):
    """POST /api/billing/admin/plans/ — Create a new plan."""

    serializer_class = PlanWriteSerializer
    permission_classes = [IsSystemAdmin]

    @swagger_auto_schema(**schemas.admin_plan_create_schema)
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class AdminPlanUpdateView(generics.UpdateAPIView):
    """PUT/PATCH /api/billing/admin/plans/<id>/ — Update a plan."""

    queryset = Plan.objects.all().prefetch_related("prices", "features")
    serializer_class = PlanWriteSerializer
    permission_classes = [IsSystemAdmin]

    @swagger_auto_schema(**schemas.admin_plan_update_schema)
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.admin_plan_update_schema)
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class AdminPlanDeleteView(generics.DestroyAPIView):
    """DELETE /api/billing/admin/plans/<id>/ — Delete a plan."""

    queryset = Plan.objects.all()
    permission_classes = [IsSystemAdmin]

    @swagger_auto_schema(**schemas.admin_plan_delete_schema)
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class SubscribeView(APIView):
    """
    POST /api/billing/subscribe/
    Business admin initiates a Stripe Checkout Session.
    Returns { checkout_url } to redirect the user.
    """

    permission_classes = [IsBusinessAdmin]

    @swagger_auto_schema(**schemas.subscribe_schema)
    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_price = PlanPrice.objects.select_related("plan").get(
            id=serializer.validated_data["plan_price_id"]
        )
        from django.conf import settings as django_settings

        frontend_base = getattr(
            django_settings, "FRONTEND_BASE_URL", "http://localhost:3000"
        )
        success_url = (
            f"{frontend_base}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{frontend_base}/payment/failed"

        result = SubscriptionService.create_checkout(
            request.user.business, plan_price, success_url, cancel_url
        )

        if "error" in result:
            http_status = (
                status.HTTP_502_BAD_GATEWAY
                if result["error"] == "stripe_error"
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(
                {
                    "detail": result["detail"],
                    **{k: v for k, v in result.items() if k not in ("error", "detail")},
                },
                status=http_status,
            )

        return Response(result, status=status.HTTP_200_OK)


# ─── Success & Invoice Views ──────────────────────────────────────────────────


class PaymentSuccessView(APIView):
    """
    Returns payment success data as JSON for the frontend to render.
    URL: /api/billing/success/?session_id=<cs_...>
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(**schemas.payment_success_schema)
    def get(self, request):
        session_id = request.GET.get("session_id")
        invoice_obj, stripe_invoice_url = SubscriptionService.resolve_payment_success(
            session_id, request.user
        )

        if invoice_obj:
            invoice_data = InvoiceSerializer(invoice_obj).data
        else:
            invoice_data = None

        return Response(
            {
                "session_id": session_id,
                "invoice": invoice_data,
                "stripe_invoice_url": (
                    invoice_obj.stripe_invoice_url
                    if invoice_obj
                    else stripe_invoice_url
                ),
            },
            status=status.HTTP_200_OK,
        )


class VerifySessionView(APIView):
    """
    POST /api/billing/verify-session/
    Frontend calls this after Stripe redirect with { session_id }.
    Returns invoice + subscription data.
    """

    permission_classes = [AllowAny]

    def _resolve(self, request, session_id):
        if not session_id:
            return Response(
                {"detail": "session_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_obj, stripe_invoice_url = SubscriptionService.resolve_payment_success(
            session_id, request.user
        )
        invoice_data = InvoiceSerializer(invoice_obj).data if invoice_obj else None

        return Response(
            {
                "session_id": session_id,
                "invoice": invoice_data,
                "stripe_invoice_url": (
                    invoice_obj.stripe_invoice_url
                    if invoice_obj
                    else stripe_invoice_url
                ),
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        return self._resolve(request, request.GET.get("session_id"))

    def post(self, request):
        return self._resolve(request, request.data.get("session_id"))


class InvoiceDownloadView(APIView):
    """
    Returns full invoice data as JSON for frontend PDF generation.
    URL: /api/billing/invoices/<id>/download/
    """

    permission_classes = [IsBusinessAdmin]

    @swagger_auto_schema(**schemas.invoice_download_schema)
    def get(self, request, pk):
        from django.contrib.auth import get_user_model

        invoice = get_object_or_404(
            Invoice.objects.select_related(
                "business", "subscription__plan_price__plan"
            ),
            pk=pk,
            business=request.user.business,
        )

        owner = None
        if invoice.business.owner_id:
            owner = (
                get_user_model()
                .objects.filter(pk=invoice.business.owner_id)
                .values("name", "email")
                .first()
            )

        return Response(
            {
                "invoice": {
                    "id": invoice.id,
                    "stripe_invoice_id": invoice.stripe_invoice_id,
                    "stripe_invoice_url": invoice.stripe_invoice_url,
                    "amount": str(invoice.amount),
                    "currency": invoice.currency.upper(),
                    "status": invoice.status,
                    "paid_at": invoice.paid_at,
                    "plan_expiry_date": (
                        invoice.subscription.current_period_end
                        if invoice.subscription
                        else None
                    ),
                    "created_at": invoice.created_at,
                    "snapshot_plan_name": invoice.snapshot_plan_name,
                    "snapshot_billing_cycle": invoice.snapshot_billing_cycle,
                    "snapshot_price": str(invoice.snapshot_price),
                },
                "user": {
                    "name": owner["name"] if owner else None,
                    "email": owner["email"] if owner else None,
                    "business_name": invoice.snapshot_business_name,
                },
            },
            status=status.HTTP_200_OK,
        )


class SwitchPlanView(APIView):
    """
    POST /api/billing/subscription/switch/
    Business admin switches to a different plan (mid-cycle with proration).
    """

    permission_classes = [IsBusinessAdmin]

    @swagger_auto_schema(**schemas.switch_plan_schema)
    def post(self, request):
        serializer = SwitchPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_plan_price = PlanPrice.objects.select_related("plan").get(
            id=serializer.validated_data["plan_price_id"]
        )

        result = SubscriptionService.switch_plan(request.user.business, new_plan_price)

        if "error" in result:
            http_status = (
                status.HTTP_502_BAD_GATEWAY
                if result["error"] == "stripe_error"
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": result["detail"]}, status=http_status)

        return Response(
            {
                "detail": "Plan switched successfully. Changes will be reflected in your next invoice.",
                "subscription": SubscriptionSerializer(result["subscription"]).data,
            },
            status=status.HTTP_200_OK,
        )


class MySubscriptionView(generics.RetrieveAPIView):
    """
    GET /api/billing/subscription/
    Returns the active subscription of the logged-in business admin.
    """

    @swagger_auto_schema(**schemas.my_subscription_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    serializer_class = SubscriptionSerializer
    permission_classes = [IsBusinessAdmin]

    def get_object(self):
        sub = (
            Subscription.objects.filter(
                business=self.request.user.business, status="active"
            )
            .select_related("plan_price__plan")
            .first()
        )
        if not sub:
            from rest_framework.exceptions import NotFound

            raise NotFound("No active subscription found.")
        return sub


class CancelSubscriptionView(APIView):
    """
    POST /api/billing/subscription/cancel/
    Business admin cancels their current subscription.
    """

    permission_classes = [IsBusinessAdmin]

    @swagger_auto_schema(**schemas.cancel_sub_schema)
    def post(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = SubscriptionService.cancel(
            request.user.business, reason=serializer.validated_data.get("reason", "")
        )

        if "error" in result:
            http_status = (
                status.HTTP_502_BAD_GATEWAY
                if result["error"] == "stripe_error"
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": result["detail"]}, status=http_status)

        return Response(
            {"detail": "Subscription cancelled successfully."},
            status=status.HTTP_200_OK,
        )


class MyInvoiceListView(generics.ListAPIView):
    """
    GET /api/billing/invoices/
    Returns all invoices for the logged-in business.
    """

    @swagger_auto_schema(**schemas.invoice_list_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    serializer_class = InvoiceSerializer
    permission_classes = [IsBusinessAdmin]

    def get_queryset(self):
        return Invoice.objects.filter(
            business=self.request.user.business
        ).select_related("subscription__plan_price__plan")


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    POST /api/billing/stripe/webhook/
    Receives Stripe webhook events. No authentication — uses signature verification.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @swagger_auto_schema(**schemas.stripe_webhook_schema)
    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = StripeService.construct_webhook_event(payload, sig_header)
        except stripe.error.SignatureVerificationError:
            return Response(
                {"detail": "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_type = event["type"]
        data_obj = event["data"]["object"]

        logger.info("Received Stripe Webhook: %s", event_type)

        obj_id = data_obj["id"]

        if event_type == "customer.subscription.created":
            StripeService.handle_subscription_created_or_updated(data_obj)
            logger.info("Subscription Created: %s", obj_id)

        elif event_type == "customer.subscription.updated":
            StripeService.handle_subscription_created_or_updated(data_obj)
            logger.info("Subscription Updated: %s", obj_id)

        elif event_type == "customer.subscription.deleted":
            StripeService.handle_subscription_deleted(data_obj)
            logger.info("Subscription Deleted: %s", obj_id)

        elif event_type == "invoice.paid":
            StripeService.handle_invoice_paid(data_obj)
            logger.info("Invoice Paid: %s", obj_id)

        elif event_type == "invoice.payment_failed":
            StripeService.handle_invoice_payment_failed(data_obj)
            logger.info("Invoice Payment Failed: %s", obj_id)

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
