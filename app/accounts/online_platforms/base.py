from abc import ABC, abstractmethod
from typing import Any, Dict


class BasePlatformAdapter(ABC):
    """
    Base interface for all online ordering platform adapters.

    Every platform such as Zomato, Swiggy, ONDC, etc.
    must implement this contract.
    """

    platform_name: str = "base"

    def __init__(
        self,
        connection: Any,
        config: Dict[str, Any] | None = None,
    ):
        self.connection = connection
        self.config = config or {}

    @abstractmethod
    async def parse_order(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert platform-specific order payload
        into our normalized order format.
        """
        raise NotImplementedError

    @abstractmethod
    async def accept_order(
        self,
        platform_order_id: str,
    ) -> Dict[str, Any]:
        """
        Accept order on external platform.
        """
        raise NotImplementedError

    @abstractmethod
    async def reject_order(
        self,
        platform_order_id: str,
        reason: str | None = None,
    ) -> Dict[str, Any]:
        """
        Reject order on external platform.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_order_status(
        self,
        platform_order_id: str,
        status: str,
    ) -> Dict[str, Any]:
        """
        Sync kitchen/order status with external platform.

        Example:
        ACCEPTED
        PREPARING
        READY
        DISPATCHED
        COMPLETED
        """
        raise NotImplementedError

    async def validate_connection(self) -> bool:
        """
        Optional connection validation.
        Override in real adapters if needed.
        """
        return True