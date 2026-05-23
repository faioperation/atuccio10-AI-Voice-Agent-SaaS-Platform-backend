from django.urls import path
from apps.crm_integration import views

urlpatterns = [
    path(
        "oauth-url/<str:crm_type>/",
        views.CRMOAuthURLView.as_view(),
        name="crm-oauth-url",
    ),
    path(
        "callback/<str:crm_type>/",
        views.CRMOAuthCallbackView.as_view(),
        name="crm-oauth-callback",
    ),
    path(
        "connections/",
        views.CRMConnectionListView.as_view(),
        name="crm-connections-list",
    ),
    path(
        "connections/<str:connection_id>/disconnect/",
        views.CRMDisconnectView.as_view(),
        name="crm-disconnect",
    ),
    path(
        "connections/<str:connection_id>/sync/",
        views.CRMSyncView.as_view(),
        name="crm-sync",
    ),
    path(
        "connections/<str:connection_id>/sync-interval/",
        views.CRMSyncIntervalView.as_view(),
        name="crm-sync-interval",
    ),
    path("connections/sync-all/", views.CRMSyncAllView.as_view(), name="crm-sync-all"),
    path("webhook/<str:crm_type>/", views.CRMWebhookView.as_view(), name="crm-webhook"),
    path("leads/", views.SyncedLeadsView.as_view(), name="synced-leads"),
]
