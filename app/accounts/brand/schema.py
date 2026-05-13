from datetime import datetime
from pydantic import BaseModel


class BrandCreate(BaseModel):
    name: str
    slug: str
    client_id: int


class BrandOut(BaseModel):
    id: int
    name: str
    slug: str
    client_id: int
    created_at: datetime | None

    class Config:
        from_attributes = True


class BrandUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None