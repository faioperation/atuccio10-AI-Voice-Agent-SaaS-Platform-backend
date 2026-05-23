from django.urls import path
from apps.ai_integration.views import (
    AILeadListView,
    AILeadStatusUpdateView,
    AICallLogCreateView,
    AIBookingCreateView,
)

urlpatterns = [
    path("leads/", AILeadListView.as_view(), name="ai-leads-list"),
    path(
        "leads/<uuid:lead_id>/",
        AILeadStatusUpdateView.as_view(),
        name="ai-lead-status-update",
    ),
    path("call-logs/", AICallLogCreateView.as_view(), name="ai-call-log-create"),
    path("bookings/", AIBookingCreateView.as_view(), name="ai-booking-create"),
]
