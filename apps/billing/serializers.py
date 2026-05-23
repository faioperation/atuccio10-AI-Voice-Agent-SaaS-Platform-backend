from rest_framework import serializers
from apps.billing.models import Plan, PlanPrice, PlanFeature, Subscription, Invoice


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = ["id", "feature_key", "feature_value"]


class PlanPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPrice
        fields = [
            "id",
            "billing_cycle",
            "price",
            "currency",
            "is_active",
        ]


class PlanPriceWriteSerializer(serializers.ModelSerializer):
    """Used by system admin to create/update plan prices."""

    class Meta:
        model = PlanPrice
        fields = ["billing_cycle", "price", "currency", "is_active"]

    def validate(self, attrs):
        plan = self.context.get("plan")
        cycle = attrs.get(
            "billing_cycle", getattr(self.instance, "billing_cycle", None)
        )
        # On create, check uniqueness
        if not self.instance:
            if PlanPrice.objects.filter(plan=plan, billing_cycle=cycle).exists():
                raise serializers.ValidationError(
                    f"A {cycle} price already exists for this plan."
                )
        return attrs


class PlanListSerializer(serializers.ModelSerializer):
    """Public plan listing with prices and features."""

    prices = PlanPriceSerializer(many=True, read_only=True)
    features = PlanFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "name", "description", "is_active", "prices", "features"]


class PlanWriteSerializer(serializers.ModelSerializer):
    """System admin: create or update a plan with nested prices and features."""

    prices = PlanPriceWriteSerializer(many=True, required=False)
    features = PlanFeatureSerializer(many=True, required=False)

    class Meta:
        model = Plan
        fields = ["name", "description", "is_active", "prices", "features"]

    def create(self, validated_data):
        prices_data = validated_data.pop("prices", [])
        features_data = validated_data.pop("features", [])

        plan = Plan.objects.create(**validated_data)

        from apps.billing.services.stripe_service import StripeService

        for price_data in prices_data:
            pp = PlanPrice.objects.create(plan=plan, **price_data)
            try:
                StripeService.sync_plan_price_to_stripe(pp)
            except Exception:
                pass

        for feature_data in features_data:
            PlanFeature.objects.create(plan=plan, **feature_data)

        return plan

    def update(self, instance, validated_data):
        prices_data = validated_data.pop("prices", None)
        features_data = validated_data.pop("features", None)

        old_name = instance.name
        # Update plan basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        from apps.billing.services.stripe_service import StripeService

        # If plan name changed, sync to Stripe
        if old_name != instance.name:
            try:
                StripeService._get_or_create_stripe_product(instance)
            except Exception:
                pass

        # Update prices if provided
        if prices_data is not None:
            for p_data in prices_data:
                cycle = p_data.get("billing_cycle")
                pp, created = PlanPrice.objects.update_or_create(
                    plan=instance, billing_cycle=cycle, defaults=p_data
                )
                try:
                    StripeService.sync_plan_price_to_stripe(pp)
                except Exception:
                    pass

        # Update features if provided
        if features_data is not None:
            for f_data in features_data:
                key = f_data.get("feature_key")
                PlanFeature.objects.update_or_create(
                    plan=instance, feature_key=key, defaults=f_data
                )

        return instance


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan_price.plan.name", read_only=True)
    billing_cycle = serializers.CharField(
        source="plan_price.billing_cycle", read_only=True
    )
    price = serializers.DecimalField(
        source="plan_price.price", max_digits=10, decimal_places=2, read_only=True
    )
    plan_start_date = serializers.DateTimeField(
        source="current_period_start", read_only=True
    )
    plan_end_date = serializers.DateTimeField(
        source="current_period_end", read_only=True
    )

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan_name",
            "billing_cycle",
            "price",
            "status",
            "plan_start_date",
            "plan_end_date",
            "current_period_start",
            "current_period_end",
            "cancelled_at",
            "cancel_reason",
            "created_at",
        ]


class SubscribeSerializer(serializers.Serializer):
    """Payload to initiate a Stripe checkout session."""

    plan_price_id = serializers.IntegerField()
    success_url = serializers.URLField(
        default="https://yourdomain.com/dashboard/billing?success=true"
    )
    cancel_url = serializers.URLField(
        default="https://yourdomain.com/dashboard/billing?cancelled=true"
    )

    def validate_plan_price_id(self, value):
        try:
            pp = PlanPrice.objects.select_related("plan").get(id=value, is_active=True)
        except PlanPrice.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive plan price.")
        if not pp.stripe_price_id:
            raise serializers.ValidationError(
                "This plan price is not yet synced to Stripe. Contact admin."
            )
        return value


class CancelSubscriptionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class SwitchPlanSerializer(serializers.Serializer):
    """Payload to switch to a different plan."""

    plan_price_id = serializers.IntegerField()

    def validate_plan_price_id(self, value):
        try:
            pp = PlanPrice.objects.select_related("plan").get(id=value, is_active=True)
        except PlanPrice.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive plan price.")
        if not pp.stripe_price_id:
            raise serializers.ValidationError(
                "This plan price is not yet synced to Stripe. Contact admin."
            )
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    subscription_status = serializers.CharField(
        source="subscription.status", read_only=True, default=None
    )
    plan_start_date = serializers.DateTimeField(
        source="subscription.current_period_start", read_only=True, default=None
    )
    plan_end_date = serializers.DateTimeField(
        source="subscription.current_period_end", read_only=True, default=None
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "stripe_invoice_id",
            "stripe_invoice_url",
            "amount",
            "currency",
            "status",
            "subscription_status",
            "plan_start_date",
            "plan_end_date",
            "paid_at",
            "snapshot_business_name",
            "snapshot_plan_name",
            "snapshot_billing_cycle",
            "snapshot_price",
            "created_at",
        ]
