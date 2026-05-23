from rest_framework import generics, filters, permissions, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from apps.call_logs.models import CallLog
from apps.call_logs.serializers import CallLogListSerializer, CallLogDetailSerializer
from apps.call_logs import schemas
from core.permissions import IsBusinessAdmin
from core.pagination import DynamicPageNumberPagination


class CallLogListCreateView(generics.ListCreateAPIView):
    pagination_class = DynamicPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = {
        "location": ["exact", "icontains"],
        "status": ["exact", "icontains"],
        "call_date_time": ["exact", "date", "gte", "lte"],
    }
    search_fields = ["name", "phone_number", "location", "status"]

    ordering_fields = ["call_date_time", "duration"]
    ordering = ["-call_date_time"]

    def get_permissions(self):
        """
        GET: Only Business Admins can see the list.
        POST: Allowed for anyone (AI/Service) to create logs.
        """
        if self.request.method == "POST":
            return [permissions.AllowAny()]
        return [IsBusinessAdmin()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CallLogDetailSerializer
        return CallLogListSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.business:
            return CallLog.objects.select_related("business").filter(
                business=user.business
            )
        return CallLog.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated and self.request.user.business:
            serializer.save(business=self.request.user.business)
        else:
            serializer.save()

    @swagger_auto_schema(**schemas.call_log_list_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.call_log_create_schema)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CallLogDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = CallLogDetailSerializer
    permission_classes = [IsBusinessAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CallLog.objects.none()
        user = self.request.user
        return CallLog.objects.select_related("business").filter(business=user.business)

    @swagger_auto_schema(**schemas.call_log_detail_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.call_log_delete_schema)
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "Call log deleted successfully."}, status=status.HTTP_200_OK
        )
