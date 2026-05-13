# from pydantic import BaseModel, EmailStr, Field

# class AdminCreate(BaseModel):
#     name: str
#     email: EmailStr
#     password: str = Field(min_length=4)
#     # role: str = "ADMIN"
#     is_active: bool = True


# class AdminOut(BaseModel):
#     id: int
#     name: str
#     email: str
#     is_active: bool

#     class Config:
#         from_attributes = True


# class AdminUpdate(BaseModel):
#     name: str | None = None
#     email: str | None = None
#     password: str | None = None
#     is_active: bool | None = None


# class AdminLogin(BaseModel):
#     email: EmailStr
#     password: str

