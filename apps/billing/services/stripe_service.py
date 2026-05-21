"""
stripe_service.py
All Stripe API interaction lives here.
Never call stripe.* directly from views — always use this module.
"""

import stripe
from datetime import timezone as dt_timezone
from django.conf import settings
from django.utils import timezone

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:

    @staticmethod
    def create_checkout_session(business, plan_price, success_url, cancel_url):
        """
        Create a Stripe Checkout Session for a subscription.
        Returns the session object (use session.url to redirect the user).
        """
        customer_id = StripeService._get_or_create_customer(business)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price": plan_price.stripe_price_id,
                    "quantity": 1,
                }
            ],
            subscription_data={
                "metadata": {
                    "business_id": str(business.id),
                    "plan_price_id": str(plan_price.id),
                }
            },
            metadata={
                "business_id": str(business.id),
                "plan_price_id": str(plan_price.id),
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session

    @staticmethod
    def _get_or_create_customer(business):
        """
        Return existing Stripe customer ID or create a new one.
        Checks the business's active subscription for a saved customer ID.
        """
        from apps.billing.models import Subscription

        existing = (
            Subscription.objects.filter(business=business)
            .exclude(stripe_customer_id=None)
            .values_list("stripe_customer_id", flat=True)
            .first()
        )
        if existing:
            return existing

        customer = stripe.Customer.create(
            name=business.name,
            email=business.owner.email if hasattr(business, "owner") else None,
            metadata={"business_id": str(business.id)},
        )
        return customer.id

    # ── Cancel Subscription

    @staticmethod
    def cancel_subscription(stripe_subscription_id):
        """
        Cancel a Stripe subscription immediately.
        """
        return stripe.Subscription.cancel(stripe_subscription_id)

    # ── Switch Plan

    @staticmethod
    def switch_subscription_plan(stripe_subscription_id, new_stripe_price_id):
        """
        Switch an active subscription to a different plan with proration.
        Calls stripe.Subscription.modify with proration_behavior='create_prorations'.
        Returns the updated Stripe subscription object.
        """
        stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
        item_id = stripe_sub["items"]["data"][0]["id"]

        updated_sub = stripe.Subscription.modify(
            stripe_subscription_id,
            items=[{"id": item_id, "price": new_stripe_price_id}],
            proration_behavior="create_prorations",
        )
        return updated_sub

    # ── Sync Product + Price to Stripe

    @staticmethod
    def sync_plan_price_to_stripe(plan_price):
        """
        Create (or update) a Stripe Product + Price for a PlanPrice object.
        Call this whenever a system admin creates/edits a price.
        Sets plan_price.stripe_price_id and saves.
        """
        product = StripeService._get_or_create_stripe_product(plan_price.plan)

        interval = "month" if plan_price.billing_cycle == "monthly" else "year"

        stripe_price = stripe.Price.create(
            product=product.id,
            unit_amount=int(plan_price.price * 100),  # convert to cents
            currency=plan_price.currency,
            recurring={"interval": interval},
            metadata={
                "plan_price_id": str(plan_price.id),
                "plan_name": plan_price.plan.name,
                "billing_cycle": plan_price.billing_cycle,
            },
        )

        plan_price.stripe_price_id = stripe_price.id
        plan_price.save(update_fields=["stripe_price_id"])
        return stripe_price

    @staticmethod
    def _get_or_create_stripe_product(plan):
        """
        Get or create a Stripe Product for a Plan.
        Uses plan metadata to find existing products.
        """
        products = stripe.Product.search(
            query=f'metadata["plan_id"]:"{plan.id}"',
            limit=1,
        )
        if products.data:
            product = products.data[0]
            if product.name != plan.name:
                stripe.Product.modify(product.id, name=plan.name)
            return product

        product = stripe.Product.create(
            name=plan.name,
            description=plan.description or plan.name,
            metadata={"plan_id": str(plan.id)},
        )
        return product

    # ── Webhook Signature Verification
    @staticmethod
    def construct_webhook_event(payload, sig_header):
        """
        Verify and parse incoming Stripe webhook.
        Raises stripe.error.SignatureVerificationError on failure.
        """
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

    # ── Handle Webhook Events
    @staticmethod
    def handle_subscription_created_or_updated(stripe_sub):
        """
        Called on customer.subscription.created and customer.subscription.updated.
        Creates or updates local Subscription record.
        Handles renewal detection: if same plan_price, carry forward period_start from previous sub.
        """
        from apps.billing.models import Subscription, SubscriptionStatus, PlanPrice
        from apps.accounts.models import Business

        metadata = stripe_sub["metadata"] if "metadata" in stripe_sub else {}
        try:
            business_id = metadata["business_id"]
        except (KeyError, TypeError):
            business_id = None
        try:
            plan_price_id = metadata["plan_price_id"]
        except (KeyError, TypeError):
            plan_price_id = None

        if not business_id or not plan_price_id:
            return

        try:
            business = Business.objects.get(id=business_id)
            plan_price = PlanPrice.objects.get(id=plan_price_id)
        except (Business.DoesNotExist, PlanPrice.DoesNotExist):
            return

        stripe_status = stripe_sub["status"]

        if stripe_status not in ("active", "past_due", "canceled", "cancelled"):
            return

        local_status = (
            SubscriptionStatus.ACTIVE
            if stripe_status == "active"
            else SubscriptionStatus.EXPIRED
        )

        _get = StripeService._stripe_get

        raw_start = _get(stripe_sub, "current_period_start")
        raw_end = _get(stripe_sub, "current_period_end")

        if not raw_start or not raw_end:
            try:
                item = stripe_sub["items"]["data"][0]
                raw_start = _get(item, "current_period_start")
                raw_end = _get(item, "current_period_end")
            except (KeyError, IndexError, TypeError):
                pass

        if not raw_start or not raw_end:
            return

        current_period_start = timezone.datetime.fromtimestamp(
            raw_start, tz=dt_timezone.utc
        )
        current_period_end = timezone.datetime.fromtimestamp(
            raw_end, tz=dt_timezone.utc
        )

        existing_active = (
            Subscription.objects.filter(
                business=business,
                plan_price=plan_price,
                status=SubscriptionStatus.ACTIVE,
            )
            .exclude(stripe_subscription_id=stripe_sub["id"])
            .first()
        )

        if existing_active and existing_active.current_period_end:
            current_period_start = existing_active.current_period_end
            existing_active.cancel(reason="Replaced by renewal subscription")

        sub, _ = Subscription.objects.update_or_create(
            stripe_subscription_id=stripe_sub["id"],
            defaults={
                "business": business,
                "plan_price": plan_price,
                "status": local_status,
                "stripe_customer_id": stripe_sub["customer"],
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
            },
        )
        return sub

    @staticmethod
    def handle_subscription_deleted(stripe_sub):
        """
        Called on customer.subscription.deleted.
        Marks local subscription as cancelled and disconnects all CRM connections.
        """
        from apps.billing.models import Subscription

        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub["id"])
            sub.cancel(reason="Cancelled via Stripe")
            _disconnect_crm_connections(sub.business_id)
        except Subscription.DoesNotExist:
            pass

    @staticmethod
    def _stripe_get(obj, key, default=None):
        """Unified getter for both Stripe objects and plain dicts."""
        try:
            val = obj[key]
            return val if val is not None else default
        except (KeyError, TypeError):
            return default

    @staticmethod
    def _invoice_subscription_id(stripe_invoice):
        """
        Extract the subscription ID from a Stripe invoice.
        Older API: invoice['subscription']
        Newer API: invoice['parent']['subscription_details']['subscription']
        """
        _get = StripeService._stripe_get
        sub_id = _get(stripe_invoice, "subscription")
        if sub_id:
            return sub_id
        try:
            parent = stripe_invoice["parent"]
            if parent:
                sub_details = parent["subscription_details"]
                if sub_details:
                    return sub_details["subscription"]
        except (KeyError, TypeError):
            pass
        return None

    @staticmethod
    def handle_invoice_paid(stripe_invoice):
        """
        Called on invoice.paid.
        Creates a local Invoice record with snapshot data.
        Handles race condition: if subscription doesn't exist locally yet, fetch from Stripe and create it.
        """
        from apps.billing.models import Subscription, Invoice, InvoiceStatus

        _get = StripeService._stripe_get
        stripe_sub_id = StripeService._invoice_subscription_id(stripe_invoice)
        if not stripe_sub_id:
            return

        amount_paid = _get(stripe_invoice, "amount_paid", 0)
        if not amount_paid:
            amount_paid = _get(stripe_invoice, "amount_due", 0)

        try:
            sub = Subscription.objects.select_related(
                "business", "plan_price__plan"
            ).get(stripe_subscription_id=stripe_sub_id)
        except Subscription.DoesNotExist:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                sub = StripeService.handle_subscription_created_or_updated(stripe_sub)
                if not sub:
                    return
            except stripe.error.StripeError:
                return

        Invoice.objects.update_or_create(
            stripe_invoice_id=_get(stripe_invoice, "id"),
            defaults={
                "subscription": sub,
                "business": sub.business,
                "amount": amount_paid / 100,
                "currency": _get(stripe_invoice, "currency", "usd"),
                "status": InvoiceStatus.PAID,
                "paid_at": timezone.now(),
                "stripe_invoice_url": _get(stripe_invoice, "hosted_invoice_url"),
                "snapshot_business_name": sub.business.name,
                "snapshot_plan_name": sub.plan_price.plan.name,
                "snapshot_billing_cycle": sub.plan_price.billing_cycle,
                "snapshot_price": sub.plan_price.price,
            },
        )

    @staticmethod
    def handle_invoice_payment_failed(stripe_invoice):
        """
        Called on invoice.payment_failed.
        Creates/updates Invoice as unpaid.
        """
        from apps.billing.models import Subscription, Invoice, InvoiceStatus

        _get = StripeService._stripe_get
        stripe_sub_id = StripeService._invoice_subscription_id(stripe_invoice)
        if not stripe_sub_id:
            return

        try:
            sub = Subscription.objects.select_related(
                "business", "plan_price__plan"
            ).get(stripe_subscription_id=stripe_sub_id)
        except Subscription.DoesNotExist:
            return

        Invoice.objects.update_or_create(
            stripe_invoice_id=_get(stripe_invoice, "id"),
            defaults={
                "subscription": sub,
                "business": sub.business,
                "amount": _get(stripe_invoice, "amount_due", 0) / 100,
                "currency": _get(stripe_invoice, "currency", "usd"),
                "status": InvoiceStatus.UNPAID,
                "snapshot_business_name": sub.business.name,
                "snapshot_plan_name": sub.plan_price.plan.name,
                "snapshot_billing_cycle": sub.plan_price.billing_cycle,
                "snapshot_price": sub.plan_price.price,
            },
        )


def _disconnect_crm_connections(business_id):
    """Deactivate all CRM connections for a business when subscription ends."""
    try:
        from apps.crm_integration.models import CRMConnection
        CRMConnection.objects.filter(business_id=business_id, is_active=True).update(is_active=False)
    except Exception:
        pass
