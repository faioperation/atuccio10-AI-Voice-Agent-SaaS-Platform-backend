from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.services import notify_business_admins, notify_system_admins


# ─── System Admin triggers ────────────────────────────────────────────────────

@receiver(post_save, sender="accounts.UserRole")
def on_business_admin_registered(sender, instance, created, **kwargs):
    """Fire when a business_admin role is assigned (i.e. new business registration)."""
    if not created or instance.role.name != "business_admin":
        return
    user = instance.user
    business_name = user.business.name if user.business else "N/A"
    notify_system_admins(
        notification_type=Notification.NotificationType.NEW_BUSINESS_REGISTERED,
        title="New Business Registered",
        message=f"'{user.name}' has registered with business '{business_name}'.",
        data={"user_id": str(user.id), "user_email": user.email, "business": business_name},
    )


@receiver(pre_save, sender="billing.Invoice")
def track_invoice_status(sender, instance, **kwargs):
    """Cache the previous invoice status before saving."""
    if instance.pk:
        try:
            from apps.billing.models import Invoice
            instance._prev_status = Invoice.objects.get(pk=instance.pk).status
        except Exception:
            instance._prev_status = None
    else:
        instance._prev_status = None


@receiver(post_save, sender="billing.Invoice")
def on_invoice_paid(sender, instance, created, **kwargs):
    """Notify system admins when an invoice transitions to paid."""
    prev = getattr(instance, "_prev_status", None)
    if instance.status != "paid" or prev == "paid":
        return
    notify_system_admins(
        notification_type=Notification.NotificationType.BUSINESS_PAYMENT,
        title="Payment Received",
        message=(
            f"Business '{instance.business.name}' paid "
            f"${instance.amount} {instance.currency.upper()} "
            f"for plan '{instance.snapshot_plan_name}'."
        ),
        data={
            "invoice_id": str(instance.id),
            "business_id": str(instance.business_id),
            "amount": str(instance.amount),
        },
    )


@receiver(pre_save, sender="support.SupportTicket")
def track_ticket_state(sender, instance, **kwargs):
    """Cache previous status and notes before saving."""
    if instance.pk:
        try:
            from apps.support.models import SupportTicket
            old = SupportTicket.objects.get(pk=instance.pk)
            instance._prev_status = old.status
            instance._prev_notes = old.notes
        except Exception:
            instance._prev_status = None
            instance._prev_notes = None
    else:
        instance._prev_status = None
        instance._prev_notes = None


@receiver(post_save, sender="support.SupportTicket")
def on_support_ticket_change(sender, instance, created, **kwargs):
    if created:
        notify_system_admins(
            notification_type=Notification.NotificationType.BUSINESS_SUPPORT_TICKET,
            title="New Support Ticket",
            message=(
                f"Business '{instance.business.name}' opened ticket "
                f"#{instance.ticket_number}: '{instance.subject}'."
            ),
            data={
                "ticket_id": str(instance.id),
                "ticket_number": instance.ticket_number,
                "business_id": str(instance.business_id),
            },
        )
    else:
        prev_status = getattr(instance, "_prev_status", instance.status)
        prev_notes = getattr(instance, "_prev_notes", instance.notes)
        if prev_status == instance.status and prev_notes == instance.notes:
            return
        notify_business_admins(
            business=instance.business,
            notification_type=Notification.NotificationType.SUPPORT_TICKET_UPDATED,
            title="Support Ticket Updated",
            message=(
                f"Your ticket #{instance.ticket_number} '{instance.subject}' "
                f"has been updated. Status: {instance.get_status_display()}."
            ),
            data={
                "ticket_id": str(instance.id),
                "ticket_number": instance.ticket_number,
                "status": instance.status,
            },
        )


# ─── Business Admin triggers ──────────────────────────────────────────────────

@receiver(post_save, sender="call_logs.CallLog")
def on_new_call_log(sender, instance, created, **kwargs):
    if not created:
        return
    notify_business_admins(
        business=instance.business,
        notification_type=Notification.NotificationType.NEW_CALL_LOG,
        title="New Call Log",
        message=f"Call recorded: {instance.name} ({instance.phone_number}).",
        data={"call_log_id": str(instance.id), "phone": instance.phone_number},
    )


@receiver(post_save, sender="bookings.Booking")
def on_new_appointment(sender, instance, created, **kwargs):
    if not created:
        return
    notify_business_admins(
        business=instance.business,
        notification_type=Notification.NotificationType.NEW_APPOINTMENT,
        title="New Appointment Booked",
        message=(
            f"{instance.customer_name} booked an appointment "
            f"on {instance.meeting_date} at {instance.meeting_time}."
        ),
        data={
            "booking_id": str(instance.id),
            "customer_name": instance.customer_name,
            "meeting_date": str(instance.meeting_date),
            "meeting_time": str(instance.meeting_time),
        },
    )


@receiver(post_save, sender="billing.Subscription")
def on_subscription_activated(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.billing.models import SubscriptionStatus
    if instance.status != SubscriptionStatus.ACTIVE:
        return
    notify_business_admins(
        business=instance.business,
        notification_type=Notification.NotificationType.SUBSCRIPTION_ACTIVATED,
        title="Subscription Activated!",
        message=(
            f"Congratulations! Your '{instance.plan_price.plan.name}' "
            f"({instance.plan_price.billing_cycle}) plan is now active."
        ),
        data={
            "subscription_id": str(instance.id),
            "plan": instance.plan_price.plan.name,
            "billing_cycle": instance.plan_price.billing_cycle,
        },
    )
    from apps.billing.services.email_service import send_plan_welcome_email
    send_plan_welcome_email(instance)


# ─── Lead signal (uncomment when crm_integration.Lead model is created) ───────
# @receiver(post_save, sender="crm_integration.Lead")
# def on_new_lead(sender, instance, created, **kwargs):
#     if not created:
#         return
#     notify_business_admins(
#         business=instance.business,
#         notification_type=Notification.NotificationType.NEW_LEAD,
#         title="New Lead",
#         message=f"A new lead has been added: {instance.name}.",
#         data={"lead_id": str(instance.id)},
#     )
