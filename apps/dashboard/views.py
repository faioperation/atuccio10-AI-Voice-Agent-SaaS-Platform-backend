from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from core.permissions import IsBusinessAdmin
from apps.dashboard.services import (
    get_leads_stats,
    get_calls_stats,
    get_conversion_rate,
    get_appointments_stats,
    get_call_logs_graph,
    get_recent_calls,
    get_recent_notifications,
)
from apps.dashboard import schemas


class BusinessAdminDashboardView(APIView):
    """Business admin dashboard with business-specific stats"""

    permission_classes = [IsBusinessAdmin]

    @swagger_auto_schema(**schemas.business_admin_dashboard_schema)
    def get(self, request):
        try:
            business = request.user.business
            if not business:
                return Response(
                    {"success": False, "error": "No business found"}, status=400
                )

            return Response(
                {
                    "success": True,
                    "business_id": str(business.id),
                    "stats": {
                        "total_leads": get_leads_stats(business),
                        "total_calls": get_calls_stats(business),
                        "conversion_rate": get_conversion_rate(business),
                        "total_appointments": get_appointments_stats(business),
                    },
                    "graphs": {
                        "call_logs": get_call_logs_graph(business),
                    },
                    "recent": {
                        "calls": get_recent_calls(business),
                        "notifications": get_recent_notifications(request.user),
                    },
                }
            )
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)
