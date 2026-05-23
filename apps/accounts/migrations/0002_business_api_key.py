import secrets
from django.db import migrations, models


def generate_api_keys(apps, schema_editor):
    """Backfill existing businesses with a unique api_key."""
    Business = apps.get_model("accounts", "Business")
    for biz in Business.objects.filter(api_key__isnull=True):
        biz.api_key = "fai_op_" + secrets.token_hex(24)
        biz.save(update_fields=["api_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="api_key",
            field=models.CharField(
                max_length=80,
                null=True,
                blank=True,
                unique=True,
                help_text="Per-business API key for AI agent authentication (X-API-Key header).",
            ),
        ),
        migrations.RunPython(generate_api_keys, migrations.RunPython.noop),
    ]
