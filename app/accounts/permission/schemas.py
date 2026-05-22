from pydantic import BaseModel


# ✅ Shared permission fields
class StaffPermissionBase(BaseModel):
    manage_orders: bool = False
    manage_staff: bool = False
    manage_inventory: bool = False
    manage_customers: bool = False
    manage_reports: bool = False
    manage_branches: bool = False
    access_billing: bool = False
    edit_menu_items: bool = False
    manage_tables: bool = False
    manage_kitchen: bool = False


# ✅ CREATE schema
class StaffPermissionCreate(StaffPermissionBase):
    staff_id: int


# ✅ UPDATE schema
class StaffPermissionUpdate(StaffPermissionBase):
    pass


# ✅ RESPONSE schema
class StaffPermissionOut(StaffPermissionBase):
    staff_id: int

    class Config:
        from_attributes = True