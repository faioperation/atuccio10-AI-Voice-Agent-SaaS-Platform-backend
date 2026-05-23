"""
Backend → AI provision & config-update service.

Phase 1: Provision  → POST  {AI_BASE_URL}/agencies/
Phase 5: Config update → PATCH {AI_BASE_URL}/agencies/{business_id}/

Called by Django signals when a business completes setup or changes config.
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 60


def _ai_base_url() -> str:
    url = getattr(settings, "AI_BASE_URL", "").rstrip("/")
    if not url:
        print("[AI PROVISION] AI_BASE_URL not set in settings — skipping.")
    return url


def _check_provision_ready(business) -> dict | None:
    """
    Returns the full provision payload if business has completed all required steps,
    otherwise returns None.

    Required:
      1. Email verified (owner exists and is_verified)
      2. Active subscription
      3. TwilioConfig saved
      4. VoiceConfig saved
      5. At least 1 KnowledgeFile
      6. At least 1 active CRM connection
    """
    from apps.billing.models import SubscriptionStatus
    from django.contrib.auth import get_user_model

    User = get_user_model()
    owner = User.objects.filter(id=business.owner_id, is_verified=True).first()
    if not owner:
        return None

    sub = business.subscriptions.filter(status=SubscriptionStatus.ACTIVE).first()
    if not sub:
        return None
    # 3. Twilio config
    twilio = getattr(business, "twilio_config", None)
    if not twilio or not twilio.twilio_sid:
        return None

    voice = getattr(business, "voice_config", None)
    if not voice:
        return None

    knowledge_files = list(business.knowledge_files.all())
    if not knowledge_files:
        return None

    if not business.crm_connections.filter(is_active=True).exists():
        return None

    request = None
    from django.conf import settings as s

    def _file_url(file_field):
        if not file_field:
            return None
        media_root = s.MEDIA_URL.rstrip("/")
        base = getattr(s, "BACKEND_BASE_URL", "").rstrip("/")
        return f"{base}{media_root}/{file_field.name}" if base else file_field.url

    return {
        "business_id": str(business.id),
        "business_name": business.name,
        "api_key": business.api_key,
        "address": business.address or "",
        "open_time": str(business.open_time) if business.open_time else None,
        "close_time": str(business.close_time) if business.close_time else None,
        "off_days": business.off_days or [],
        "human_agent_phone": business.human_agent_phone or "",
        "is_active": business.is_active,
        "active_subscription_status": sub.status,
        "twilio": {
            "twilio_sid": twilio.twilio_sid,
            "twilio_token": twilio.twilio_token,
            "twilio_number": twilio.twilio_number,
        },
        "voice": {
            "gender": voice.gender,
            "tone": voice.tone,
            "voice_template_url": _file_url(voice.voice_template),
        },
        "knowledge_files": [
            {
                "id": str(kf.id),
                "name": kf.name,
                "file_url": _file_url(kf.file),
                "file_type": kf.file_type,
            }
            for kf in knowledge_files
        ],
    }


def provision_business(business) -> dict:
    """
    POST {AI_BASE_URL}/agencies/
    Called when all config is complete (via signal).
    Returns AI response or error dict.
    """
    base = _ai_base_url()
    if not base:
        return {"success": False, "errors": ["AI_BASE_URL not configured."]}

    payload = _check_provision_ready(business)
    if payload is None:
        print(f"[AI PROVISION] business {business.id} not ready yet — skipping.")
        return {"success": False, "errors": ["Business setup incomplete."]}

    url = f"{base}/agencies/"
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        print(
            f"[AI PROVISION] business {business.id} provisioned → instance_id={data.get('instance_id')}"
        )
        return data
    except requests.Timeout:
        print(f"[AI PROVISION] timeout calling {url}")
        return {"success": False, "errors": ["AI server timeout."]}
    except Exception as e:
        print(f"[AI PROVISION] error calling {url}: {e}")
        return {"success": False, "errors": [str(e)]}


def push_config_update(business, changed: dict) -> dict:
    """
    PATCH {AI_BASE_URL}/agencies/{business_id}/
    Called when Twilio / Voice / KnowledgeFile config changes (via signal).
    `changed` contains only the sections that changed, e.g.:
      {"voice": {...}} or {"knowledge_files": [...]} or {"twilio": {...}}
    """
    base = _ai_base_url()
    if not base:
        return {"success": False, "errors": ["AI_BASE_URL not configured."]}

    url = f"{base}/agencies/{business.id}/"
    try:
        resp = requests.patch(url, json=changed, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        print(
            f"[AI CONFIG UPDATE] business {business.id} updated → {list(changed.keys())}"
        )
        return data
    except requests.Timeout:
        print(f"[AI CONFIG UPDATE] timeout calling {url}")
        return {"success": False, "errors": ["AI server timeout."]}
    except Exception as e:
        print(f"[AI CONFIG UPDATE] error: {e}")
        return {"success": False, "errors": [str(e)]}
