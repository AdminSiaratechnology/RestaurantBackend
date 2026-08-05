"""
app/accounts/crm/handlers/base.py

Abstract Base Handler interface and execution context wrapper.
Implements Strategy Pattern & Open-Closed Principle for CRM pipeline extensions.
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.accounts.bill.model import Bill
    from app.accounts.customer.model import Customer
    from app.accounts.order.model import Order

from app.accounts.crm.events.schema import BillCompletedEvent, CRMContextDTO


class CRMContext:
    """
    State container holding current DB session, entity references, and transient data across pipeline steps.
    """
    def __init__(
        self,
        event: BillCompletedEvent,
        db: AsyncSession,
        bill: Optional["Bill"] = None,
        customer: Optional["Customer"] = None,
        order: Optional["Order"] = None
    ):
        self.event = event
        self.db = db
        self.bill = bill
        self.customer = customer
        self.order = order
        self.dto = CRMContextDTO(event=event)


class BaseCRMHandler(ABC):
    """
    Abstract Interface for all CRM Event Handlers.
    Each handler is responsible for a single step in the CRM lifecycle.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name/Identifier of the handler."""
        pass

    @property
    def is_enabled(self) -> bool:
        """Flag to toggle handler on/off dynamically."""
        return True

    @abstractmethod
    async def process(self, context: CRMContext) -> None:
        """
        Executes handler logic using current context.

        Args:
            context: Shared pipeline execution context containing DB session and models.
        """
        pass
