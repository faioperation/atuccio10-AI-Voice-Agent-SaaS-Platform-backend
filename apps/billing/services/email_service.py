import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)


def send_plan_welcome_email(subscription):
    """Send a welcome/congratulations email after a subscription is activated."""
    business = subscription.business
    plan_price = subscription.plan_price

    try:
        from apps.accounts.models import UserRole

        user_role = UserRole.objects.select_related("user").get(
            user__business=business, role__name="business_admin"
        )
        user = user_role.user
    except Exception:
        logger.warning(
            "send_plan_welcome_email: no business_admin found for business %s",
            business.id,
        )
        return False

    billing_cycle_display = (
        "Monthly" if plan_price.billing_cycle == "monthly" else "Yearly"
    )
    expiry_date = (
        subscription.current_period_end.strftime("%B %d, %Y")
        if subscription.current_period_end
        else "N/A"
    )

    context = {
        "user_name": user.name,
        "plan_name": plan_price.plan.name,
        "billing_cycle_display": billing_cycle_display,
        "expiry_date": expiry_date,
        "dashboard_url": getattr(settings, "FRONTEND_DASHBOARD_URL", "#"),
    }

    html_content = render_to_string("billing/emails/plan_welcome.html", context)
    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=f"Welcome to {plan_price.plan.name} — Your Clinch plan is active!",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        logger.error(
            "send_plan_welcome_email failed for business %s: %s", business.id, e
        )
        return False
