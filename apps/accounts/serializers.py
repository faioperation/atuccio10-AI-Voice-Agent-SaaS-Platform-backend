from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import Business, Role, UserRole

User = get_user_model()
MAX_PROFILE_IMAGE_SIZE_MB = 5


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "description",
            "address",
            "open_time",
            "close_time",
            "off_days",
            "human_agent_phone",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    active_subscription = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "profile_image",
            "business",
            "is_verified",
            "roles",
            "active_subscription",
        ]
        read_only_fields = [
            "id",
            "email",
            "business",
            "is_verified",
            "roles",
            "active_subscription",
        ]

    def validate_profile_image(self, value):
        if value and value.size > MAX_PROFILE_IMAGE_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"Profile image too large ({value.size // (1024 * 1024)} MB). Max: {MAX_PROFILE_IMAGE_SIZE_MB} MB."
            )
        return value

    def get_roles(self, obj):
        return [ur.role.name for ur in obj.user_roles.all()]

    def _get_active_sub(self, obj):
        if hasattr(obj, "_cached_active_sub"):
            return obj._cached_active_sub
        sub = None
        if getattr(obj, "business", None):
            from apps.billing.models import SubscriptionStatus

            business = obj.business
            prefetch_cache = getattr(business, "_prefetched_objects_cache", {})
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
                    business.subscriptions.filter(status=SubscriptionStatus.ACTIVE)
                    .select_related("plan_price__plan")
                    .first()
                )
        obj._cached_active_sub = sub
        return sub

    def get_active_subscription(self, obj):
        sub = self._get_active_sub(obj)
        if not sub:
            return None
        return {
            "plan_name": sub.plan_price.plan.name,
            "billing_cycle": sub.plan_price.billing_cycle,
            "price": str(sub.plan_price.price),
            "currency": sub.plan_price.currency,
            "status": sub.status,
            "plan_start_date": sub.current_period_start,
            "plan_end_date": sub.current_period_end,
        }


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)
    business_name = serializers.CharField(max_length=255)

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
        business = Business.objects.create(name=validated_data["business_name"])

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            phone=validated_data["phone"],
            business=business,
        )

        business.owner_id = user.id
        business.save()

        role, _ = Role.objects.get_or_create(name="business_admin")
        UserRole.objects.create(user=user, role=role)

        return user


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)
    new_password = serializers.CharField(write_only=True, min_length=8)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data
