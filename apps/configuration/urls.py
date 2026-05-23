from django.urls import path
from apps.configuration.views import (
    TwilioConfigView,
    VoiceConfigView,
    KnowledgeFileListCreateView,
    KnowledgeFileDetailView,
)

urlpatterns = [
    path("twilio-config/", TwilioConfigView.as_view(), name="twilio-config"),
    path("voice-config/", VoiceConfigView.as_view(), name="voice-config"),
    path(
        "knowledge-files/",
        KnowledgeFileListCreateView.as_view(),
        name="knowledge-files",
    ),
    path(
        "knowledge-files/<uuid:pk>/",
        KnowledgeFileDetailView.as_view(),
        name="knowledge-file-detail",
    ),
]
