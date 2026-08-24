from datetime import date, datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from .constants import CustomerNoteType


# ============================================================
# CREATE
# ============================================================

class CustomerNoteCreate(BaseModel):

    note: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    note_type: CustomerNoteType = Field(
        default=CustomerNoteType.GENERAL,
    )

    reminder_date: Optional[date] = None

    is_pinned: bool = False

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Note cannot be empty"
            )

        return value


# ============================================================
# UPDATE
# ============================================================

class CustomerNoteUpdate(BaseModel):

    note: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )

    note_type: Optional[CustomerNoteType] = None

    reminder_date: Optional[date] = None

    is_pinned: Optional[bool] = None

    @field_validator("note")
    @classmethod
    def validate_note(
        cls,
        value: Optional[str],
    ) -> Optional[str]:

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "Note cannot be empty"
            )

        return value


# ============================================================
# RESPONSE
# ============================================================

class CustomerNoteResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    customer_id: int

    client_id: int

    branch_id: int

    note: str

    note_type: CustomerNoteType

    reminder_date: Optional[date] = None

    is_pinned: bool

    created_by: Optional[int] = None

    updated_by: Optional[int] = None

    created_at: datetime

    updated_at: datetime


# ============================================================
# LIST RESPONSE
# ============================================================

class CustomerNoteListResponse(BaseModel):

    items: list[CustomerNoteResponse]

    total: int

    page: int

    page_size: int

    total_pages: int

    has_next: bool

    has_previous: bool


# ============================================================
# SUMMARY
# ============================================================

class CustomerNoteSummary(BaseModel):

    total_notes: int

    pinned_notes: int

    allergy_notes: int

    complaint_notes: int

    feedback_notes: int

    preference_notes: int

    follow_up_notes: int