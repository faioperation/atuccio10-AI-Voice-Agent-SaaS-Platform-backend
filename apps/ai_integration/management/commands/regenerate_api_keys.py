"""
Management command to regenerate api_keys for all businesses
(or only those with old prefix).

Usage:
    python manage.py regenerate_api_keys             # only businesses with no key
    python manage.py regenerate_api_keys --all       # regenerate ALL keys (new prefix)
"""
import secrets
from django.core.management.base import BaseCommand
from apps.accounts.models import Business

PREFIX = "fai_op_"


class Command(BaseCommand):
    help = "Generate / regenerate Business api_keys with the correct prefix."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            dest="regenerate_all",
            help="Regenerate keys for ALL businesses, not just missing ones.",
        )

    def handle(self, *args, **options):
        regenerate_all = options["regenerate_all"]

        if regenerate_all:
            qs = Business.objects.all()
            self.stdout.write("Regenerating api_keys for ALL businesses…")
        else:
            qs = Business.objects.filter(api_key__isnull=True)
            self.stdout.write("Generating api_keys for businesses with missing keys…")

        count = 0
        for biz in qs:
            biz.api_key = PREFIX + secrets.token_hex(24)
            biz.save(update_fields=["api_key"])
            self.stdout.write(f"  [{biz.id}] {biz.name} → {biz.api_key}")
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Done. {count} business(es) updated."))
