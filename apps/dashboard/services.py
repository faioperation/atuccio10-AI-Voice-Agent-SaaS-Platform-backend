from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from apps.crm_integration.models import SyncedLead
from apps.call_logs.models import CallLog
from apps.bookings.models import Booking
from apps.notifications.models import Notification


def _get_month_ranges():
    """Helper to get current and previous month ranges (avoids duplication)"""
    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = current_month_start - timedelta(seconds=1)
    previous_month_start = previous_month_end.replace(day=1)
    return {
        "current_start": current_month_start,
        "current_end": now,
        "previous_start": previous_month_start,
        "previous_end": previous_month_end,
    }


def get_month_over_month_percentage(current, previous):
    """Calculate percentage change from previous to current"""
    if previous == 0:
        return 0 if current == 0 else 100
    return round(((current - previous) / previous) * 100, 1)


def get_leads_stats(business=None):
    """Get total leads and month-over-month change"""
    ranges = _get_month_ranges()

    qs = SyncedLead.objects.filter(
        created_at__gte=ranges["previous_start"], created_at__lte=ranges["current_end"]
    )
    if business:
        qs = qs.filter(business=business)

    result = qs.aggregate(
        current_count=Count("id", filter=Q(created_at__gte=ranges["current_start"])),
        previous_count=Count("id", filter=Q(created_at__lt=ranges["current_start"])),
    )

    current_count = result["current_count"] or 0
    previous_count = result["previous_count"] or 0
    percentage = get_month_over_month_percentage(current_count, previous_count)

    return {
        "total": current_count,
        "percentage_change": percentage,
        "trend": "up" if percentage >= 0 else "down",
    }


def get_calls_stats(business=None):
    """Get total calls and month-over-month change"""
    ranges = _get_month_ranges()

    qs = CallLog.objects.filter(
        call_date_time__gte=ranges["previous_start"],
        call_date_time__lte=ranges["current_end"],
    )
    if business:
        qs = qs.filter(business=business)

    result = qs.aggregate(
        current_count=Count(
            "id", filter=Q(call_date_time__gte=ranges["current_start"])
        ),
        previous_count=Count(
            "id", filter=Q(call_date_time__lt=ranges["current_start"])
        ),
    )

    current_count = result["current_count"] or 0
    previous_count = result["previous_count"] or 0
    percentage = get_month_over_month_percentage(current_count, previous_count)

    return {
        "total": current_count,
        "percentage_change": percentage,
        "trend": "up" if percentage >= 0 else "down",
    }


def get_conversion_rate(business=None):
    """Calculate conversion rate: (bookings / leads) * 100"""
    ranges = _get_month_ranges()

    leads_qs = SyncedLead.objects.filter(
        created_at__gte=ranges["previous_start"], created_at__lte=ranges["current_end"]
    )
    bookings_qs = Booking.objects.filter(
        created_at__gte=ranges["previous_start"], created_at__lte=ranges["current_end"]
    )

    if business:
        leads_qs = leads_qs.filter(business=business)
        bookings_qs = bookings_qs.filter(business=business)

    lead_result = leads_qs.aggregate(
        current=Count("id", filter=Q(created_at__gte=ranges["current_start"])),
        previous=Count("id", filter=Q(created_at__lt=ranges["current_start"])),
    )
    current_leads = lead_result["current"] or 0
    previous_leads = lead_result["previous"] or 0

    booking_result = bookings_qs.aggregate(
        current=Count("id", filter=Q(created_at__gte=ranges["current_start"])),
        previous=Count("id", filter=Q(created_at__lt=ranges["current_start"])),
    )
    current_bookings = booking_result["current"] or 0
    previous_bookings = booking_result["previous"] or 0

    current_rate = (current_bookings / current_leads * 100) if current_leads > 0 else 0
    previous_rate = (
        (previous_bookings / previous_leads * 100) if previous_leads > 0 else 0
    )

    percentage = get_month_over_month_percentage(current_rate, previous_rate)

    return {
        "rate": round(current_rate, 1),
        "percentage_change": percentage,
        "trend": "up" if percentage >= 0 else "down",
    }


def get_appointments_stats(business=None):
    """Get total appointments/bookings and month-over-month change"""
    ranges = _get_month_ranges()

    qs = Booking.objects.filter(
        created_at__gte=ranges["previous_start"], created_at__lte=ranges["current_end"]
    )
    if business:
        qs = qs.filter(business=business)

    result = qs.aggregate(
        current_count=Count("id", filter=Q(created_at__gte=ranges["current_start"])),
        previous_count=Count("id", filter=Q(created_at__lt=ranges["current_start"])),
    )

    current_count = result["current_count"] or 0
    previous_count = result["previous_count"] or 0
    percentage = get_month_over_month_percentage(current_count, previous_count)

    return {
        "total": current_count,
        "percentage_change": percentage,
        "trend": "up" if percentage >= 0 else "down",
    }


def get_call_logs_graph(business=None):
    """Get call logs grouped by day for this week and last week (optimized single query)"""
    now = timezone.now()

    days_since_monday = now.weekday()
    this_week_start = now - timedelta(
        days=days_since_monday,
        hours=now.hour,
        minutes=now.minute,
        seconds=now.second,
        microseconds=now.microsecond,
    )

    last_week_end = this_week_start - timedelta(seconds=1)
    last_week_start = last_week_end - timedelta(days=6)

    qs = CallLog.objects.filter(
        call_date_time__gte=last_week_start, call_date_time__lte=now
    )
    if business:
        qs = qs.filter(business=business)

    daily_counts = dict(
        qs.annotate(date=TruncDate("call_date_time"))
        .values("date")
        .annotate(count=Count("id"))
        .values_list("date", "count")
    )

    def build_week_data(week_start, week_end):
        data = []
        for i in range((week_end - week_start).days):
            day = week_start + timedelta(days=i)
            day_name = day.strftime("%a")
            count = daily_counts.get(day.date(), 0)
            data.append(
                {"day": day_name, "date": day.date().isoformat(), "calls": count}
            )
        return data

    this_week_end = now + timedelta(days=1)
    return {
        "this_week": build_week_data(this_week_start, this_week_end),
        "last_week": build_week_data(
            last_week_start, last_week_end + timedelta(days=1)
        ),
    }


def get_recent_calls(business=None, limit=6):
    """Get recent call logs"""
    qs = CallLog.objects.select_related("business").order_by("-call_date_time")
    if business:
        qs = qs.filter(business=business)

    calls = qs[:limit]

    return [
        {
            "id": str(call.id) if hasattr(call, "id") else None,
            "name": call.name,
            "phone": call.phone_number,
            "status": call.status,
            "duration": call.duration,
            "date": call.call_date_time.isoformat(),
        }
        for call in calls
    ]


def get_recent_notifications(user=None, limit=6):
    """Get recent notifications"""
    qs = Notification.objects.order_by("-created_at")
    if user:
        qs = qs.filter(recipient=user)

    notifications = qs[:limit]

    return [
        {
            "id": str(notif.id),
            "type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat(),
        }
        for notif in notifications
    ]
