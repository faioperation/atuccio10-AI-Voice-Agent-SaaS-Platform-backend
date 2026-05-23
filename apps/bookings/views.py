from rest_framework import generics, filters, permissions, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.bookings import schemas
from core.permissions import IsBusinessAdmin
from core.pagination import DynamicPageNumberPagination


class BookingListCreateView(generics.ListCreateAPIView):
    serializer_class = BookingSerializer
    pagination_class = DynamicPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = {
        "status": ["exact"],
        "meeting_date": ["exact", "gte", "lte"],
    }

    search_fields = ["customer_name", "customer_email", "customer_phone"]

    ordering_fields = ["meeting_date", "meeting_time", "created_at"]
    ordering = ["-meeting_date", "-meeting_time"]

    def get_permissions(self):
        """
        GET: Only Business Admins can see the list.
        POST: Allowed for anyone (AI/Service) to create bookings.
        """
        if self.request.method == "POST":
            return [permissions.AllowAny()]
        return [IsBusinessAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.business:
            return Booking.objects.select_related("business").filter(
                business=user.business
            )
        return Booking.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated and self.request.user.business:
            serializer.save(business=self.request.user.business)
        else:
            serializer.save()

    @swagger_auto_schema(**schemas.booking_list_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.booking_create_schema)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class BookingDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsBusinessAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        user = self.request.user
        return Booking.objects.select_related("business").filter(business=user.business)

    @swagger_auto_schema(**schemas.booking_detail_schema)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.booking_delete_schema)
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "Booking deleted successfully."}, status=status.HTTP_200_OK
        )
