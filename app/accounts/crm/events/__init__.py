"""
CRM Events Package.
"""

from app.accounts.crm.events.publisher import CRMEventPublisher, crm_event_publisher
from app.accounts.crm.events.dispatcher import CRMEventDispatcher
from app.accounts.crm.events.consumer import CRMEventConsumer
from app.accounts.crm.events.schema import BillCompletedEvent, CRMContextDTO
from app.accounts.crm.events.model import CRMProcessedEvent

__all__ = [
    "CRMEventPublisher",
    "crm_event_publisher",
    "CRMEventDispatcher",
    "CRMEventConsumer",
    "BillCompletedEvent",
    "CRMContextDTO",
    "CRMProcessedEvent",
]
