import uuid
import os
from django.db import models
from apps.accounts.models import Business
from core.encryption import encrypt_value, decrypt_value


class TwilioConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="twilio_config"
    )

    _twilio_sid = models.TextField(db_column="twilio_sid", blank=True, null=True)
    _twilio_token = models.TextField(db_column="twilio_token", blank=True, null=True)
    twilio_number = models.CharField(max_length=30, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def twilio_sid(self):
        return decrypt_value(self._twilio_sid) if self._twilio_sid else None

    @twilio_sid.setter
    def twilio_sid(self, value):
        self._twilio_sid = encrypt_value(value) if value else None

    @property
    def twilio_token(self):
        return decrypt_value(self._twilio_token) if self._twilio_token else None

    @twilio_token.setter
    def twilio_token(self, value):
        self._twilio_token = encrypt_value(value) if value else None

    class Meta:
        verbose_name = "Twilio Config"
        verbose_name_plural = "Twilio Configs"

    def __str__(self):
        return f"TwilioConfig – {self.business.name}"


class VoiceConfig(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class Tone(models.TextChoices):
        PROFESSIONAL = "professional", "Professional"
        FRIENDLY = "friendly", "Friendly"
        FORMAL = "formal", "Formal"
        CASUAL = "casual", "Casual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="voice_config"
    )
    gender = models.CharField(
        max_length=20, choices=Gender.choices, default=Gender.FEMALE
    )
    tone = models.CharField(
        max_length=20, choices=Tone.choices, default=Tone.PROFESSIONAL
    )
    voice_template = models.FileField(
        upload_to="voice_templates/",
        blank=True,
        null=True,
        help_text="Audio sample file (mp3/wav/ogg/m4a/aac/flac/webm, max 120 MB)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Voice Config"
        verbose_name_plural = "Voice Configs"

    def __str__(self):
        return f"VoiceConfig({self.gender}/{self.tone}) – {self.business.name}"


class KnowledgeFile(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="knowledge_files"
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="knowledge_files/")
    file_type = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPLOADED
    )
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Knowledge File"
        verbose_name_plural = "Knowledge Files"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.file_type:
            _, ext = os.path.splitext(self.file.name)
            self.file_type = ext.lstrip(".").lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.status}) – {self.business.name}"
