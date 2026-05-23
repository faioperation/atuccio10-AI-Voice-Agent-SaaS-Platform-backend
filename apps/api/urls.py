from django.urls import path, include

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("api/system-admin/", include("apps.system_admin.urls")),
    path("api/config/", include("apps.configuration.urls")),
    path("api/support/", include("apps.support.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/crm/", include("apps.crm_integration.urls")),
    path("api/call-logs/", include("apps.call_logs.urls")),
    path("api/bookings/", include("apps.bookings.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/ai/", include("apps.ai_integration.urls")),
]
