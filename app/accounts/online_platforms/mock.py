from datetime import datetime, timezone
from typing import Any, Dict

from .base import BasePlatformAdapter


class MockPlatformAdapter(BasePlatformAdapter):

    platform_name = "mock"

    async def parse_order(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {
            "platform_order_id": str(
                payload.get("order_id")
                or payload.get("id")
                or f"MOCK-{datetime.now().timestamp()}"
            ),

            "order_number": payload.get("order_number"),

            "customer": {
                "name": payload.get(
                    "customer_name",
                    "Mock Customer",
                ),
                "phone": payload.get("customer_phone"),
                "email": payload.get("customer_email"),
            },

            "items": [
                {
                    "platform_item_id": str(
                        item.get("item_id")
                        or item.get("id")
                    ),
                    "name": item.get("name"),
                    "quantity": float(
                        item.get("quantity", 1)
                    ),
                    "price": float(
                        item.get("price", 0)
                    ),
                    "notes": item.get("notes"),
                }
                for item in payload.get("items", [])
            ],

            "pricing": {
                "subtotal": float(
                    payload.get("subtotal", 0)
                ),
                "tax": float(
                    payload.get("tax", 0)
                ),
                "delivery_charge": float(
                    payload.get("delivery_charge", 0)
                ),
                "discount": float(
                    payload.get("discount", 0)
                ),
                "total": float(
                    payload.get("total", 0)
                ),
            },

            "delivery": {
                "type": payload.get(
                    "delivery_type",
                    "delivery",
                ),
                "address": payload.get(
                    "delivery_address"
                ),
            },

            "raw_payload": payload,
        }

    async def accept_order(
        self,
        platform_order_id: str,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "platform": self.platform_name,
            "platform_order_id": platform_order_id,
            "status": "ACCEPTED",
            "message": "Mock order accepted successfully",
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    async def reject_order(
        self,
        platform_order_id: str,
        reason: str | None = None,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "platform": self.platform_name,
            "platform_order_id": platform_order_id,
            "status": "REJECTED",
            "reason": reason or "Rejected by restaurant",
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    async def update_order_status(
        self,
        platform_order_id: str,
        status: str,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "platform": self.platform_name,
            "platform_order_id": platform_order_id,
            "status": status,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }