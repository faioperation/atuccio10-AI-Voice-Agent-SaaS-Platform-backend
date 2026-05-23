import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from apps.accounts.managers import CustomUserManager


class Business(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.UUIDField(
        null=True, blank=True, help_text="App-level reference to User ID"
    )

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)

    open_time = models.TimeField(null=True, blank=True, help_text="e.g. 09:00")
    close_time = models.TimeField(null=True, blank=True, help_text="e.g. 17:30")

    off_days = models.JSONField(
        default=list, help_text='JSON array: ["sunday", "friday"]'
    )

    human_agent_phone = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    api_key = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        unique=True,
        help_text="Per-business API key for AI agent (X-API-Key header).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Businesses"


class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    business = models.ForeignKey(
        Business, on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, unique=True)
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    otp_resend_count = models.IntegerField(default=0)
    last_otp_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone"]

    def __str__(self):
        return self.email


class RolePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(
        RolePermission, blank=True, related_name="roles"
    )

    def __str__(self):
        return self.name


class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role")


class OTPCode(models.Model):
    class OTPType(models.TextChoices):
        EMAIL_VERIFY = "email_verify", "Email Verification"
        PASSWORD_RESET = "password_reset", "Password Reset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="otps")

    code = models.CharField(max_length=10)
    type = models.CharField(max_length=20, choices=OTPType.choices)
    is_used = models.BooleanField(default=False)

    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

    @staticmethod
    def clean_expired():
        OTPCode.objects.filter(expires_at__lt=timezone.now()).delete()

    def __str__(self):
        return f"{self.user.email} - {self.type} - {self.code}"
