from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_yasg.utils import swagger_auto_schema

from core.permissions import IsBusinessAdmin, HasActiveSubscription
from apps.configuration.models import (
    TwilioConfig,
    VoiceConfig,
    KnowledgeFile,
)
from apps.configuration.serializers import (
    TwilioConfigSerializer,
    VoiceConfigSerializer,
    KnowledgeFileSerializer,
)
from apps.configuration import schemas

# ---------------------------------------------------------------------------
# Reusable base for singleton config views (one per business)
# ---------------------------------------------------------------------------


class SingletonConfigView(APIView):
    """
    Base view for config models that are OneToOne with Business.
    - GET  → retrieve current config (masked display)
    - POST → create if not exists (409 if already exists)
    - PATCH→ update existing config
    """

    permission_classes = [IsBusinessAdmin]
    serializer_class = None
    model_class = None

    def _get_instance(self, business_id):
        return self.model_class.objects.filter(business_id=business_id).first()

    def get(self, request):
        instance = self._get_instance(request.user.business_id)
        if not instance:
            return Response(
                {"detail": "Not configured yet.", "code": "not_configured"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        if self._get_instance(request.user.business_id):
            return Response(
                {
                    "detail": "Config already exists. Use PATCH to update.",
                    "code": "already_exists",
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(business_id=request.user.business_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        instance = self._get_instance(request.user.business_id)
        if not instance:
            return Response(
                {
                    "detail": "No config found. Use POST to create first.",
                    "code": "not_configured",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class TwilioConfigView(SingletonConfigView):
    permission_classes = [IsBusinessAdmin, HasActiveSubscription]
    serializer_class = TwilioConfigSerializer
    model_class = TwilioConfig

    @swagger_auto_schema(**schemas.twilio_config_get_schema)
    def get(self, request):
        return super().get(request)

    @swagger_auto_schema(**schemas.twilio_config_create_schema)
    def post(self, request):
        return super().post(request)

    @swagger_auto_schema(**schemas.twilio_config_update_schema)
    def patch(self, request):
        return super().patch(request)


class VoiceConfigView(SingletonConfigView):
    permission_classes = [IsBusinessAdmin, HasActiveSubscription]
    serializer_class = VoiceConfigSerializer
    model_class = VoiceConfig
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(**schemas.voice_config_get_schema)
    def get(self, request):
        return super().get(request)

    @swagger_auto_schema(**schemas.voice_config_create_schema)
    def post(self, request):
        return super().post(request)

    @swagger_auto_schema(**schemas.voice_config_update_schema)
    def patch(self, request):
        return super().patch(request)


class KnowledgeFileListCreateView(APIView):
    """
    GET  → List all knowledge files for the business (newest first)
    POST → Upload a new knowledge file
    """

    permission_classes = [IsBusinessAdmin, HasActiveSubscription]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(**schemas.knowledge_file_list_schema)
    def get(self, request):
        qs = KnowledgeFile.objects.filter(
            business_id=request.user.business_id
        ).order_by("-created_at")
        serializer = KnowledgeFileSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(**schemas.knowledge_file_upload_schema)
    def post(self, request):
        files = request.FILES.getlist("file")

        if len(files) <= 1:
            serializer = KnowledgeFileSerializer(
                data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(business_id=request.user.business_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        created = []
        errors = []
        for f in files:
            data = request.data.copy()
            data["file"] = f
            if not data.get("name"):
                import os as _os

                data["name"] = _os.path.splitext(f.name)[0]
            serializer = KnowledgeFileSerializer(
                data=data, context={"request": request}
            )
            if serializer.is_valid():
                serializer.save(business_id=request.user.business_id)
                created.append(serializer.data)
            else:
                errors.append({"file": f.name, "errors": serializer.errors})

        if errors and not created:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        resp_status = (
            status.HTTP_201_CREATED if not errors else status.HTTP_207_MULTI_STATUS
        )
        return Response(
            {"created": created, "errors": errors},
            status=resp_status,
        )


class KnowledgeFileDetailView(APIView):
    """
    DELETE → Remove a specific knowledge file (must belong to same business)
    """

    permission_classes = [IsBusinessAdmin, HasActiveSubscription]

    def _get_object(self, pk, business_id):
        return KnowledgeFile.objects.filter(pk=pk, business_id=business_id).first()

    @swagger_auto_schema(**schemas.knowledge_file_delete_schema)
    def delete(self, request, pk):
        instance = self._get_object(pk, request.user.business_id)
        if not instance:
            return Response(
                {"detail": "Knowledge file not found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        file_id = str(instance.id)
        business = instance.business
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()

        try:
            from apps.ai_integration.provision_service import push_config_update

            push_config_update(
                business, {"knowledge_files": [{"id": file_id, "action": "remove"}]}
            )
        except Exception as e:
            print(f"[AI] failed to push knowledge file removal: {e}")

        return Response(
            {"detail": "Knowledge file deleted successfully."},
            status=status.HTTP_200_OK,
        )
