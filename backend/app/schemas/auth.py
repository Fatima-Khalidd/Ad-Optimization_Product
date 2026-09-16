"""Request and response bodies for /api/auth."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    # extra="ignore" is explicit, not incidental: a body carrying "role": "admin" must be
    # accepted and the role dropped. There is no role field here and signup_client() takes
    # no role argument, so signup can never create an admin (docs/PLAN.md section 5).
    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(min_length=8)
    business_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    created_at: datetime


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_name: str
    base_fee: Decimal
    performance_fee_pct: Decimal


class MeOut(BaseModel):
    user: UserOut
    client: ClientOut | None = None
