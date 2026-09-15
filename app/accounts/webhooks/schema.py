from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# =========================================================
# UBER WEBHOOK META
# =========================================================

class UberWebhookMeta(BaseModel):

    model_config = ConfigDict(
        extra="allow",
    )

    resource_id: Optional[str] = None

    status: Optional[str] = None

    user_id: Optional[str] = None


# =========================================================
# UBER WEBHOOK PAYLOAD
# =========================================================

class UberWebhookPayload(BaseModel):

    model_config = ConfigDict(
        extra="allow",
    )

    event_id: str

    event_type: str

    event_time: Optional[int] = None

    resource_href: Optional[str] = None

    meta: Optional[UberWebhookMeta] = None

    webhook_meta: Optional[dict[str, Any]] = None