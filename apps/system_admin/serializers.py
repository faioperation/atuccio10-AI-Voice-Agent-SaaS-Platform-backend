from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import Role, UserRole
from apps.accounts.serializers import UserSerializer

User = get_user_model()


class SystemAdminCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            phone=validated_data["phone"],
        )
        user.is_staff = True
        user.is_verified = False
        user.save()

        role, _ = Role.objects.get_or_create(name="system_admin")
        UserRole.objects.create(user=user, role=role)

        return user


class BusinessAdminListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view - minimal data"""

    plan_start_date = serializers.SerializerMethodField()
    plan_end_date = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "plan",
            "plan_start_date",
            "plan_end_date",
        ]

    def _active_sub(self, obj):
        """Use prefetch cache to avoid extra queries"""
        if hasattr(obj, "_cached_active_sub"):
            return obj._cached_active_sub
        sub = None
        if obj.business:
            from apps.billing.models import SubscriptionStatus

            prefetch_cache = getattr(obj.business, "_prefetched_objects_cache", {})
            if "subscriptions" in prefetch_cache:
                sub = next(
                    (
                        s
                        for s in prefetch_cache["subscriptions"]
                        if s.status == SubscriptionStatus.ACTIVE
                    ),
                    None,
                )
            else:
                sub = (
                    obj.business.subscriptions.filter(status=SubscriptionStatus.ACTIVE)
                    .select_related("plan_price__plan")
                    .first()
                )
        obj._cached_active_sub = sub
        return sub

    def get_plan(self, obj):
        sub = self._active_sub(obj)
        if sub:
            return f"{sub.plan_price.plan.name}"
        return "Free"

    def get_plan_start_date(self, obj):
        sub = self._active_sub(obj)
        if sub and sub.current_period_start:
            return sub.current_period_start.strftime("%Y-%m-%d")
        return None

    def get_plan_end_date(self, obj):
        sub = self._active_sub(obj)
        if sub and sub.current_period_end:
            return sub.current_period_end.strftime("%Y-%m-%d")
        return None


class BusinessAdminDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view"""

    plan_start_date = serializers.SerializerMethodField()
    plan_end_date = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    total_leads = serializers.SerializerMethodField()
    total_calls = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    total_appointments = serializers.SerializerMethodField()
    business_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "business_name",
            "plan",
            "plan_start_date",
            "plan_end_date",
            "total_leads",
            "total_calls",
            "conversion_rate",
            "total_appointments",
        ]

    def _get_stats(self, business):
        """Batch calculate stats to avoid N+1"""
        if not business:
            return {"leads": 0, "calls": 0, "bookings": 0}

        from django.db.models import Count
        from apps.crm_integration.models import SyncedLead
        from apps.call_logs.models import CallLog
        from apps.bookings.models import Booking

        leads = (
            SyncedLead.objects.filter(business=business).aggregate(c=Count("id"))["c"]
            or 0
        )
        calls = (
            CallLog.objects.filter(business=business).aggregate(c=Count("id"))["c"] or 0
        )
        bookings = (
            Booking.objects.filter(business=business).aggregate(c=Count("id"))["c"] or 0
        )

        return {"leads": leads, "calls": calls, "bookings": bookings}

    def _active_sub(self, obj):
        if hasattr(obj, "_cached_active_sub"):
            return obj._cached_active_sub
        sub = None
        if obj.business:
            from apps.billing.models import SubscriptionStatus

            prefetch_cache = getattr(obj.business, "_prefetched_objects_cache", {})
            if "subscriptions" in prefetch_cache:
                subs = prefetch_cache["subscriptions"]
                sub = next(
                    (s for s in subs if s.status == SubscriptionStatus.ACTIVE), None
                )
            else:
                sub = (
                    obj.business.subscriptions.filter(status=SubscriptionStatus.ACTIVE)
                    .select_related("plan_price__plan")
                    .first()
                )
        obj._cached_active_sub = sub
        return sub

    def get_plan(self, obj):
        sub = self._active_sub(obj)
        if sub:
            return f"{sub.plan_price.plan.name} ({sub.plan_price.billing_cycle})"
        return "Free"

    def get_plan_start_date(self, obj):
        sub = self._active_sub(obj)
        if sub and sub.current_period_start:
            return sub.current_period_start.strftime("%Y-%m-%d")
        return None

    def get_plan_end_date(self, obj):
        sub = self._active_sub(obj)
        if sub and sub.current_period_end:
            return sub.current_period_end.strftime("%Y-%m-%d")
        return None

    def get_business_name(self, obj):
        return obj.business.name if obj.business else None

    def get_total_leads(self, obj):
        if obj.business and hasattr(self, "_stats_cache"):
            return self._stats_cache.get("leads", 0)
        return 0

    def get_total_calls(self, obj):
        if obj.business and hasattr(self, "_stats_cache"):
            return self._stats_cache.get("calls", 0)
        return 0

    def get_conversion_rate(self, obj):
        if obj.business and hasattr(self, "_stats_cache"):
            leads = self._stats_cache.get("leads", 0)
            bookings = self._stats_cache.get("bookings", 0)
            if leads > 0:
                return round((bookings / leads) * 100, 1)
        return 0.0

    def get_total_appointments(self, obj):
        if obj.business and hasattr(self, "_stats_cache"):
            return self._stats_cache.get("bookings", 0)
        return 0

    def to_representation(self, instance):
        if instance.business:
            self._stats_cache = self._get_stats(instance.business)
        return super().to_representation(instance)
