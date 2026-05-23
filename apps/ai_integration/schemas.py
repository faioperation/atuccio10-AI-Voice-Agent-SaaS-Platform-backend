from drf_yasg import openapi

TAG = "AI Integration"

_api_key_header = openapi.Parameter(
    "X-API-Key",
    openapi.IN_HEADER,
    description="Per-business API key issued at provision time.",
    type=openapi.TYPE_STRING,
    required=True,
)

# ── Leads ─────────────────────────────────────────────────────────────────────

ai_leads_list_schema = dict(
    operation_summary="[AI] Fetch Pending Leads",
    operation_description=(
        "Returns up to 50 `pending` leads for the business.\n\n"
        "No query params needed — business is resolved from `X-API-Key`.\n\n"
        "When `count` is 0 the AI should go idle and wait for the next sync cycle."
    ),
    manual_parameters=[_api_key_header],
    responses={
        200: openapi.Response(
            "Pending leads",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "count": openapi.Schema(type=openapi.TYPE_INTEGER, example=3),
                    "results": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid"),
                                "name": openapi.Schema(type=openapi.TYPE_STRING),
                                "email": openapi.Schema(type=openapi.TYPE_STRING),
                                "phone": openapi.Schema(type=openapi.TYPE_STRING),
                                "crm_type": openapi.Schema(type=openapi.TYPE_STRING, example="hubspot"),
                                "status": openapi.Schema(type=openapi.TYPE_STRING, example="pending"),
                                "last_synced_at": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                            },
                        ),
                    ),
                },
            ),
        ),
        401: openapi.Response("Invalid or missing X-API-Key"),
    },
    tags=[TAG],
)

ai_lead_status_update_schema = dict(
    operation_summary="[AI] Update Lead Status",
    operation_description=(
        "Updates the status of a single lead.\n\n"
        "**Call flow:**\n"
        "1. PATCH `status: calling` — lock the lead before dialing\n"
        "2. PATCH final status after call ends (via `POST /api/ai/call-logs/` which is atomic)\n\n"
        "**Valid statuses:** `pending`, `calling`, `done`, `not_interested`, `no_answer`, `meeting_scheduled`"
    ),
    manual_parameters=[_api_key_header],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["status"],
        properties={
            "status": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["pending", "calling", "done", "not_interested", "no_answer", "meeting_scheduled"],
                example="calling",
            ),
        },
    ),
    responses={
        200: openapi.Response("Status updated", schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid"),
                "status": openapi.Schema(type=openapi.TYPE_STRING),
            },
        )),
        404: openapi.Response("Lead not found"),
        401: openapi.Response("Invalid or missing X-API-Key"),
    },
    tags=[TAG],
)

# ── Call Log ──────────────────────────────────────────────────────────────────

ai_call_log_create_schema = dict(
    operation_summary="[AI] Submit Call Log",
    operation_description=(
        "Creates a call log entry.\n\n"
        "If `lead_id` **and** `lead_status` are provided, the lead's status is updated "
        "in the **same DB transaction** (atomic) — no separate PATCH needed.\n\n"
        "Omit `lead_id` for inbound/unknown calls."
    ),
    manual_parameters=[_api_key_header],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["name", "phone_number", "duration", "status"],
        properties={
            "lead_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid", description="Optional"),
            "lead_status": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["done", "not_interested", "no_answer", "meeting_scheduled"],
                description="Required if lead_id is provided",
            ),
            "name": openapi.Schema(type=openapi.TYPE_STRING, example="Kishor Mahmud"),
            "phone_number": openapi.Schema(type=openapi.TYPE_STRING, example="+8801XXXXXXXXX"),
            "location": openapi.Schema(type=openapi.TYPE_STRING, example="Dhaka"),
            "duration": openapi.Schema(type=openapi.TYPE_STRING, example="05:30"),
            "status": openapi.Schema(type=openapi.TYPE_STRING, example="Not interested"),
            "audio_url": openapi.Schema(type=openapi.TYPE_STRING, format="uri"),
            "summary": openapi.Schema(type=openapi.TYPE_STRING),
            "transcript": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    example={"AI": "Hello!", "customer": "Hi there"},
                ),
            ),
        },
    ),
    responses={
        201: openapi.Response("Call log saved", schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "call_log_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid"),
                "lead_status": openapi.Schema(type=openapi.TYPE_STRING),
            },
        )),
        404: openapi.Response("Lead not found"),
        401: openapi.Response("Invalid or missing X-API-Key"),
    },
    tags=[TAG],
)

# ── Booking ───────────────────────────────────────────────────────────────────

ai_booking_create_schema = dict(
    operation_summary="[AI] Create Booking",
    operation_description=(
        "Creates a meeting booking.\n\n"
        "If `lead_id` is provided, the lead status is atomically set to `meeting_scheduled`."
    ),
    manual_parameters=[_api_key_header],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["meeting_date", "meeting_time", "customer_name"],
        properties={
            "lead_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid", description="Optional"),
            "meeting_date": openapi.Schema(type=openapi.TYPE_STRING, format="date", example="2026-06-15"),
            "meeting_time": openapi.Schema(type=openapi.TYPE_STRING, example="10:00:00"),
            "meeting_link": openapi.Schema(type=openapi.TYPE_STRING, format="uri"),
            "status": openapi.Schema(type=openapi.TYPE_STRING, example="scheduled"),
            "customer_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kishor"),
            "customer_email": openapi.Schema(type=openapi.TYPE_STRING, format="email"),
            "customer_phone": openapi.Schema(type=openapi.TYPE_STRING, example="+8801XXXXXXXXX"),
        },
    ),
    responses={
        201: openapi.Response("Booking created", schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "booking_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid"),
            },
        )),
        401: openapi.Response("Invalid or missing X-API-Key"),
    },
    tags=[TAG],
)
