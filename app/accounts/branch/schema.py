from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.accounts.branch.model import statusEnum


# ============================================================
# CREATE BRANCH
# ============================================================

class BranchCreate(BaseModel):
    name: str
    address: str
    city: str

    status: statusEnum = statusEnum.ACTIVE

    client_id: int

    brand_id: int | None = None


# ============================================================
# BRANCH RESPONSE
# ============================================================

class BranchOut(BaseModel):
    id: int

    name: str

    client_id: int

    branch_code: str

    brand_id: int | None = None

    address: str

    city: str

    status: statusEnum

    created_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# UPDATE BRANCH
# ============================================================

class BranchUpdate(BaseModel):
    name: str | None = None

    address: str | None = None

    city: str | None = None

    brand_id: int | None = None

    status: statusEnum | None = None


# ============================================================
# CHANGE STATUS
# ============================================================

class BranchStatusUpdate(BaseModel):
    status: statusEnum