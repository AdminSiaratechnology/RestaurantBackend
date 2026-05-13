# from pydantic import BaseModel
# from typing import Optional
# from datetime import datetime


# class TenantOut(BaseModel):
#     id: int
#     name: str
#     slug: str
#     client_id: int   # ✅ FIXED
#     created_at: datetime | None 

#     class Config:
#         from_attributes = True


# class TenantUpdate(BaseModel):
#     name: Optional[str] = None
#     slug: Optional[str] = None
#     admin_id: Optional[int] = None

# class TenantCreate(BaseModel):
#     name: str
#     slug: str