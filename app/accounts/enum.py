import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    PARTNER = "partner"
    CLIENT = "client"
    STAFF = "staff"