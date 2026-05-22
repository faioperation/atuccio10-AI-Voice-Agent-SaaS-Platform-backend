import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.utils import timezone
from django.db import close_old_connections

logger = logging.getLogger(__name__)

EXPIRY_WARNING_DAYS = [10, 7, 3, 2, 1]
NOTIFICATION_RETENTION_DAYS = 30


def _acquire_lock(key, timeout):
    """
    Single-execution guard for multi-worker deployments.
    Requires a shared cache (Redis/Memcached) in production.
    With Django's default LocMemCache (dev), always returns True.
    """
    from django.core.cache import cache

    return cache.add(key, 1, timeout=timeout)


def send_meeting_reminders():
    """
    Runs every minute. Finds bookings starting in 9–11 minutes and
    sends a one-time reminder. Handles midnight window crossover correctly.
    """
    close_old_connections()
    if not _acquire_lock("notif:lock:meeting_reminders", timeout=55):
        return

    try:
        from apps.notifications.models import Notification
        from apps.notifications.services import notify_business_admins

        now = timezone.now()
        window_start_dt = now + timedelta(minutes=9)
        window_end_dt = now + timedelta(minutes=11)

        # Use datetime comparison instead of date+time split
        # This correctly handles midnight crossover (e.g. 23:55 + 11 min = 00:06 next day)
        bookings = _bookings_in_window(window_start_dt, window_end_dt)

        for booking in bookings:
            already_sent = Notification.objects.filter(
                notification_type=Notification.NotificationType.MEETING_REMINDER,
                data__contains={"booking_id": str(booking.id)},
            ).exists()
            if already_sent:
                continue

            notify_business_admins(
                business=booking.business,
                notification_type=Notification.NotificationType.MEETING_REMINDER,
                title="Meeting in 10 Minutes",
                message=(
                    f"Reminder: {booking.customer_name} has a meeting at "
                    f"{booking.meeting_time} on {booking.meeting_date}."
                ),
                data={
                    "booking_id": str(booking.id),
                    "customer_name": booking.customer_name,
                    "meeting_date": str(booking.meeting_date),
                    "meeting_time": str(booking.meeting_time),
                },
            )
            logger.info(
                "Meeting reminder sent for booking %s (%s at %s)",
                booking.id,
                booking.customer_name,
                booking.meeting_time,
            )
    except Exception:
        logger.exception("Error in send_meeting_reminders")


def _bookings_in_window(window_start_dt, window_end_dt):
    """
    Returns bookings whose combined (meeting_date + meeting_time) falls between
    window_start_dt and window_end_dt. Works across midnight boundaries.
    """
    from apps.bookings.models import Booking

    # If window stays within the same day, filter by date+time range directly
    if window_start_dt.date() == window_end_dt.date():
        return Booking.objects.filter(
            meeting_date=window_start_dt.date(),
            meeting_time__range=(window_start_dt.time(), window_end_dt.time()),
        ).select_related("business")

    # Window crosses midnight: check both days separately
    # Part 1: end of window_start_dt's day  (e.g. 23:54 → 23:59:59)
    # Part 2: start of window_end_dt's day (e.g. 00:00 → 00:06)
    from django.db.models import Q

    return Booking.objects.filter(
        Q(
            meeting_date=window_start_dt.date(),
            meeting_time__gte=window_start_dt.time(),
        )
        | Q(
            meeting_date=window_end_dt.date(),
            meeting_time__lte=window_end_dt.time(),
        )
    ).select_related("business")


def send_subscription_expiry_warnings():
    """
    Runs every 6 hours. Sends expiry warnings at 10, 7, 3, 2, 1 day(s) before
    the subscription ends. Each day-level warning fires only once per subscription.
    """
    close_old_connections()
    if not _acquire_lock("notif:lock:subscription_expiry", timeout=3600 * 5):
        return

    try:
        from apps.billing.models import Subscription, SubscriptionStatus
        from apps.notifications.models import Notification
        from apps.notifications.services import notify_business_admins

        now = timezone.now()
        active_subs = Subscription.objects.filter(
            status=SubscriptionStatus.ACTIVE,
            current_period_end__isnull=False,
        ).select_related("business", "plan_price__plan")

        for sub in active_subs:
            days_left = (sub.current_period_end - now).days

            # Auto-expire and disconnect CRM when period has ended
            if days_left < 0:
                sub.status = "expired"
                sub.save(update_fields=["status", "updated_at"])
                from apps.crm_integration.models import CRMConnection
                CRMConnection.objects.filter(business=sub.business, is_active=True).update(is_active=False)
                continue

            if days_left not in EXPIRY_WARNING_DAYS:
                continue

            already_sent = Notification.objects.filter(
                notification_type=Notification.NotificationType.SUBSCRIPTION_EXPIRY,
                data__contains={"subscription_id": str(sub.id), "days_left": days_left},
            ).exists()
            if already_sent:
                continue

            plan_name = sub.plan_price.plan.name
            msg = (
                f"Your '{plan_name}' subscription expires tomorrow! Renew now to avoid interruption."
                if days_left == 1
                else f"Your '{plan_name}' subscription expires in {days_left} days. Consider renewing soon."
            )

            notify_business_admins(
                business=sub.business,
                notification_type=Notification.NotificationType.SUBSCRIPTION_EXPIRY,
                title=f"Subscription Expiring in {days_left} Day{'s' if days_left > 1 else ''}",
                message=msg,
                data={
                    "subscription_id": str(sub.id),
                    "plan": plan_name,
                    "days_left": days_left,
                },
            )
    except Exception:
        logger.exception("Error in send_subscription_expiry_warnings")


def cleanup_old_notifications():
    """
    Runs once per day. Deletes notifications older than NOTIFICATION_RETENTION_DAYS.
    """
    close_old_connections()
    if not _acquire_lock("notif:lock:cleanup", timeout=3600 * 23):
        return

    try:
        from apps.notifications.models import Notification

        cutoff = timezone.now() - timedelta(days=NOTIFICATION_RETENTION_DAYS)
        deleted, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
        if deleted:
            logger.info(
                "Cleaned up %d notifications older than %d days.",
                deleted,
                NOTIFICATION_RETENTION_DAYS,
            )
    except Exception:
        logger.exception("Error in cleanup_old_notifications")


def sync_crm_connections():
    """
    Runs every 5 minutes. Polls all active CRM connections and syncs new/updated leads.
    Salesforce uses incremental sync (LastModifiedDate >= last_sync_at).
    Other CRMs rely on webhooks but this acts as a fallback safety net.
    """
    close_old_connections()
    if not _acquire_lock("crm:lock:sync", timeout=270):
        return
    try:
        from apps.crm_integration.models import CRMConnection
        from apps.crm_integration.services import get_oauth_service

        connections = CRMConnection.objects.filter(is_active=True).select_related(
            "business"
        )
        for conn in connections:
            try:
                service = get_oauth_service(conn.crm_type, conn)
                result = service.sync_leads_to_db()
                if result.get("success") and (
                    result.get("saved", 0) or result.get("updated", 0)
                ):
                    logger.info(
                        "CRM poll sync [%s] saved=%s updated=%s",
                        conn.crm_type,
                        result.get("saved"),
                        result.get("updated"),
                    )
            except NotImplementedError:
                pass
            except Exception:
                logger.exception(
                    "CRM poll sync failed for connection %s (%s)",
                    conn.id,
                    conn.crm_type,
                )
    except Exception:
        logger.exception("Error in sync_crm_connections")


def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        send_meeting_reminders,
        trigger=IntervalTrigger(minutes=1),
        id="meeting_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_subscription_expiry_warnings,
        trigger=IntervalTrigger(hours=6),
        id="subscription_expiry_warnings",
        replace_existing=True,
    )
    scheduler.add_job(
        cleanup_old_notifications,
        trigger=IntervalTrigger(hours=24),
        id="cleanup_old_notifications",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_crm_connections,
        trigger=IntervalTrigger(minutes=60),
        id="crm_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Notification scheduler started.")
