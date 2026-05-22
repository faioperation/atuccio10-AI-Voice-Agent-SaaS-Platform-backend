from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm_integration", "0002_replace_name_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="crmconnection",
            name="interval_minutes",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Polling interval in minutes for non-webhook CRMs (1–120). Leave blank to use default (60 min).",
            ),
        ),
    ]
