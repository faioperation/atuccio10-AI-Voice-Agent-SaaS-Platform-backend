import xml.etree.ElementTree as ET
from apps.crm_integration.models import SyncedLead


def _build_name(first, last):
    return " ".join(filter(None, [(first or "").strip(), (last or "").strip()])) or None


def upsert_lead(conn, crm_id, **fields):
    # On create → status defaults to "pending" so AI can pick it up.
    # On update → never overwrite status (AI may have already set it to done/etc).
    obj, created = SyncedLead.objects.get_or_create(
        crm_connection=conn,
        crm_lead_id=str(crm_id),
        defaults={"business": conn.business, "status": "pending", **fields},
    )
    if not created:
        # Update non-status fields only
        update_fields = {k: v for k, v in fields.items() if k != "status"}
        update_fields["business"] = conn.business
        for attr, val in update_fields.items():
            setattr(obj, attr, val)
        obj.save(update_fields=list(update_fields.keys()) + ["updated_at"])
    else:
        _notify_new_lead(conn, fields)


def _notify_new_lead(conn, lead_data):
    try:
        from apps.notifications.models import Notification
        from apps.notifications.services import notify_business_admins
        name = lead_data.get("name") or "Unknown"
        notify_business_admins(
            business=conn.business,
            notification_type=Notification.NotificationType.NEW_LEAD,
            title="New Lead",
            message=f"New lead '{name}' synced from {conn.get_crm_type_display()}.",
            data={
                "crm_type": conn.crm_type,
                "name": name,
                "email": lead_data.get("email"),
                "phone": lead_data.get("phone"),
            },
        )
    except Exception:
        pass


def parse_salesforce_soap(body: str) -> dict:
    try:
        root = ET.fromstring(body)
        obj = root.find(".//{http://soap.sforce.com/2005/09/outbound}sObject")
        if obj is None:
            return {}
        return {
            (child.tag.split("}")[-1] if "}" in child.tag else child.tag): child.text
            for child in obj
        }
    except Exception:
        return {}


def handle_hubspot(conn, data):
    from apps.crm_integration.services.hubspot import HubSpotService

    service = HubSpotService(conn)
    for event in (data if isinstance(data, list) else [data]):
        object_id = event.get("objectId")
        if not object_id:
            continue
        contact = service.fetch_contact_by_id(object_id)
        if contact:
            props = contact.get("properties", {})
            upsert_lead(conn, object_id,
                        crm_object_type="contact",
                        name=_build_name(props.get("firstname"), props.get("lastname")),
                        email=props.get("email") or None,
                        phone=props.get("phone") or None,
                        raw_data=contact)
        else:
            upsert_lead(conn, object_id, crm_object_type="contact", raw_data=event)


def handle_salesforce(conn, data):
    upsert_lead(conn, data.get("Id") or data.get("id"),
                crm_object_type="lead",
                name=_build_name(data.get("FirstName"), data.get("LastName")),
                email=data.get("Email") or None,
                phone=data.get("Phone") or None,
                company=data.get("Company") or None,
                raw_data=data)


def handle_zoho(conn, data):
    if isinstance(data, list):
        record = data[0] if data else {}
    elif "data" in data:
        records = data["data"]
        record = records[0] if isinstance(records, list) and records else records or {}
    else:
        record = data

    lead_id = (
        record.get("id") or record.get("ID") or record.get("lead_id")
        or record.get("email") or record.get("Email")
        or record.get("phone") or record.get("Phone")
    )
    if not lead_id:
        return

    upsert_lead(conn, lead_id,
                crm_object_type="lead",
                name=_build_name(
                    record.get("First_Name") or record.get("first_name"),
                    record.get("Last_Name") or record.get("last_name"),
                ),
                email=record.get("Email") or record.get("email") or None,
                phone=record.get("Phone") or record.get("phone") or None,
                raw_data=record)


def handle_pipedrive(conn, data):
    from apps.crm_integration.services.pipedrive import PipedriveService

    service = PipedriveService(conn)
    item = data.get("current") or data
    fields = service._extract_person_fields(item)
    upsert_lead(conn, item.get("id"), crm_object_type="person", raw_data=item,
                name=fields.get("name"), email=fields.get("email"), phone=fields.get("phone"))


_HANDLERS = {
    "hubspot": handle_hubspot,
    "salesforce": handle_salesforce,
    "zoho": handle_zoho,
    "pipedrive": handle_pipedrive,
}


def dispatch(crm_type, conn, data):
    handler = _HANDLERS.get(crm_type)
    if handler:
        handler(conn, data)
