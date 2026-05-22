from drf_yasg import openapi

TAG = "CRM Integration"

crm_oauth_url_schema = dict(
    operation_summary="Get CRM OAuth URL",
    operation_description="Generate OAuth authorization URL for connecting a CRM (hubspot/salesforce/zoho/pipedrive)",
    responses={200: openapi.Response("Authorization URL")},
    tags=[TAG],
)

crm_connections_list_schema = dict(
    operation_summary="List Connected CRMs",
    operation_description="Get all active CRM connections for the current user's business",
    responses={200: "List of connected CRMs"},
    tags=[TAG],
)

crm_disconnect_schema = dict(
    operation_summary="Disconnect CRM",
    operation_description="Deactivate a CRM connection by connection ID",
    responses={200: "Disconnected", 404: "Not found"},
    tags=[TAG],
)

crm_sync_schema = dict(
    operation_summary="Sync CRM Leads",
    operation_description="Manually pull latest leads from a connected CRM into the database",
    responses={200: openapi.Response("Sync result: {success, saved, updated}")},
    tags=[TAG],
)

crm_sync_all_schema = dict(
    operation_summary="Sync All Connected CRM Leads",
    operation_description="Manually sync leads from all active CRM connections for the business",
    responses={200: openapi.Response("Sync result: {success, total_saved, total_updated, total_errors, details}")},
    tags=[TAG],
)

crm_leads_list_schema = dict(
    operation_summary="List Synced Leads",
    operation_description="Get all leads synced from CRMs. Filter by crm_type.",
    manual_parameters=[
        openapi.Parameter("crm_type", openapi.IN_QUERY, description="hubspot/salesforce/zoho/pipedrive", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False),
    ],
    responses={200: "Paginated leads list"},
    tags=[TAG],
)

crm_sync_interval_schema = dict(
    operation_summary="Set CRM Sync Interval",
    operation_description=(
        "Set how often (in minutes) a polling-based CRM connection should sync leads.\n\n"
        "**Only works for:** `pipedrive`, `salesforce` (webhook-based CRMs sync automatically).\n\n"
        "**Min:** 60 minutes — values below this will be rejected.\n"
        "**Max:** 1440 minutes (24 hours).\n"
        "**Default:** 60 minutes (used when no interval has been set)."
    ),
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["interval_minutes"],
        properties={
            "interval_minutes": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Sync interval in minutes (1–120). Default is 60.",
                example=60,
            ),
        },
    ),
    responses={
        200: openapi.Response(
            "Interval updated",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "detail": openapi.Schema(type=openapi.TYPE_STRING),
                    "crm_type": openapi.Schema(type=openapi.TYPE_STRING),
                    "interval_minutes": openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            ),
        ),
        400: openapi.Response("Validation error"),
        404: openapi.Response("Connection not found"),
    },
    tags=[TAG],
)

crm_webhook_schema = dict(
    operation_summary="CRM Webhook Receiver",
    operation_description="Endpoint for CRMs to POST new lead/contact events to",
    manual_parameters=[
        openapi.Parameter("crm_type", openapi.IN_PATH, description="hubspot/salesforce/zoho/pipedrive", type=openapi.TYPE_STRING, required=True),
    ],
    responses={200: "Processed", 401: "Invalid signature"},
    tags=[TAG],
)
