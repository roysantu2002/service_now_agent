from fastapi import APIRouter, Request, HTTPException
from typing import Any, Dict
from datetime import datetime
import json
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Optional: internal trigger simulation
async def trigger_internal_webhook(payload: Dict[str, Any]):
    logger.info(f"🔁 Internal webhook triggered with: {json.dumps(payload, indent=2)}")


@router.post("/servicenow/test-webhook")
async def test_servicenow_webhook(request: Request) -> Dict[str, Any]:
    """
    Receives full payload from ServiceNow, prints entire JSON payload,
    extracts key fields, and auto-triggers internal webhook.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"❌ Invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    timestamp = datetime.utcnow().isoformat()

    # ✅ 1️⃣ Print the entire payload (raw ServiceNow JSON)
    print("\n🚀 === ServiceNow Webhook Triggered ===")
    print(f"🕒 Timestamp: {timestamp}")
    print("📦 Full JSON Payload Received:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("======================================\n")

    # ✅ 2️⃣ Extract `result` section if present
    result = payload.get("result", payload) if isinstance(payload, dict) else {}

    # ✅ 3️⃣ Safe getter for nested fields (handles dict.value pattern)
    def safe_get(obj, key):
        val = obj.get(key)
        if isinstance(val, dict):
            return val.get("value", None)
        return val

    # ✅ 4️⃣ Extract key info for summary or internal routing
    key_info = {
        "sys_id": safe_get(result, "sys_id"),
        "number": safe_get(result, "number"),
        "short_description": safe_get(result, "short_description"),
        "priority": safe_get(result, "priority"),
        "impact": safe_get(result, "impact"),
        "urgency": safe_get(result, "urgency"),
        "state": safe_get(result, "state"),
        "category": safe_get(result, "category"),
        "caller_id": safe_get(result, "caller_id"),
        "opened_by": safe_get(result, "opened_by"),
        "sys_updated_on": safe_get(result, "sys_updated_on"),
        "sys_created_on": safe_get(result, "sys_created_on"),
        "assignment_group": safe_get(result, "assignment_group"),
        "assigned_to": safe_get(result, "assigned_to"),
    }

    # ✅ 5️⃣ Print extracted key fields
    print("📋 === Extracted Key Fields ===")
    for k, v in key_info.items():
        print(f"{k:20}: {v}")
    print("======================================\n")

    # ✅ 6️⃣ Log everything for debug
    logger.info(f"ServiceNow webhook received:\n{json.dumps(payload, indent=2)}")
    logger.info(f"Extracted fields:\n{json.dumps(key_info, indent=2)}")

    # ✅ 7️⃣ Auto trigger internal webhook for processing (background)
    asyncio.create_task(trigger_internal_webhook({
        "event": "servicenow_incident_created",
        "source": "servicenow_test_webhook",
        "received_at": timestamp,
        "summary": key_info,
        "raw_payload": payload
    }))

    # ✅ 8️⃣ Return response to ServiceNow
    return {
        "status": "success",
        "message": "ServiceNow webhook received successfully",
        "timestamp": timestamp,
        "key_fields": key_info,
    }
