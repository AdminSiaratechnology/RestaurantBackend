# app/accounts/change_password/schema.py

from pydantic import BaseModel, Field, model_validator


class ChangePasswordRequest(BaseModel):
    current_password: str

    new_password: str = Field(
        min_length=8,
        description="New password must be at least 8 characters"
    )

    confirm_password: str

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError(
                "New password and confirm password do not match"
            )
        return self


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str