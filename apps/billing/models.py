from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """
    Top-level pricing plan (e.g. Starter, Pro, Enterprise).
    System admins can update name / description / active status.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plans"
        ordering = ["id"]

    def __str__(self):
        return self.name


class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


class PlanPrice(models.Model):
    """
    Monthly/yearly price tier for a plan.
    Stores the Stripe Price ID after being synced to Stripe.
    6 total rows per plan-set: Starter/Pro/Enterprise × monthly/yearly.
    """

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="prices")
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    stripe_price_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plan_prices"
        unique_together = ("plan", "billing_cycle")
        ordering = ["plan", "billing_cycle"]

    def __str__(self):
        return f"{self.plan.name} — {self.billing_cycle} — ${self.price}"


class PlanFeature(models.Model):
    """
    Key-value feature limits attached to a plan.
    feature_value can be: "500", "unlimited", "true", "false"
    """

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    feature_key = models.CharField(max_length=100)
    feature_value = models.CharField(max_length=100)

    class Meta:
        db_table = "plan_features"
        unique_together = ("plan", "feature_key")

    def __str__(self):
        return f"{self.plan.name} | {self.feature_key}: {self.feature_value}"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"


class Subscription(models.Model):
    """
    One subscription per business at a time.
    Linked to a PlanPrice (which is monthly or yearly).
    """

    business = models.ForeignKey(
        "accounts.Business",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan_price = models.ForeignKey(
        PlanPrice, on_delete=models.PROTECT, related_name="subscriptions"
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
    )
    stripe_subscription_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business} — {self.plan_price} — {self.status}"

    @property
    def is_active(self):
        return self.status == SubscriptionStatus.ACTIVE

    def cancel(self, reason=""):
        self.status = SubscriptionStatus.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancel_reason = reason
        self.save(
            update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"]
        )


class InvoiceStatus(models.TextChoices):
    PAID = "paid", "Paid"
    UNPAID = "unpaid", "Unpaid"
    VOID = "void", "Void"


class Invoice(models.Model):
    """
    Invoice record created after every successful Stripe payment.
    Stores snapshot data so it remains accurate even if plan changes.
    """

    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, related_name="invoices"
    )
    business = models.ForeignKey(
        "accounts.Business",
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    stripe_invoice_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    stripe_invoice_url = models.URLField(max_length=1024, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.UNPAID
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    snapshot_business_name = models.CharField(max_length=255)
    snapshot_plan_name = models.CharField(max_length=100)
    snapshot_billing_cycle = models.CharField(max_length=10)
    snapshot_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "invoices"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice #{self.id} — {self.business} — {self.status}"
