from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer
from apps.notifications import schemas


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(**schemas.notification_list_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(is_read=False)
        return qs


@swagger_auto_schema(method="post", **schemas.mark_read_schema)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, pk):
    """POST /api/notifications/{id}/read/"""
    updated = Notification.objects.filter(id=pk, recipient=request.user).update(
        is_read=True
    )
    if not updated:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"detail": "Marked as read."})


@swagger_auto_schema(method="post", **schemas.mark_all_read_schema)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """POST /api/notifications/read-all/"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    return Response({"detail": "All notifications marked as read."})


@swagger_auto_schema(method="get", **schemas.unread_count_schema)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """GET /api/notifications/unread-count/"""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({"unread_count": count})
