# app/schemas/auth_schemas.py

from pydantic import BaseModel, Field
from typing import Optional

# --- Request Schemas ---


class OTPSendRequest(BaseModel):
    """
    Schema for a request to send a one-time password (OTP).
    """

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="The recipient's phone number.",
        examples=["+1234567890", "555-1234"],
    )


class OTPVerifyRequest(BaseModel):
    """
    Schema for a request to verify a one-time password (OTP).
    """

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="The user's phone number.",
        examples=["+1234567890"],
    )
    otp: str = Field(
        ...,
        min_length=4,
        max_length=8,
        description="The OTP received by the user.",
        examples=["123456"],
    )


class AdminAuthRequest(BaseModel):
    """
    Schema for an administrator's authentication request.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="The admin's username.",
        examples=["admin"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="The admin's password.",
        examples=["password123"],
    )


# --- Response Schemas ---


class AuthResponse(BaseModel):
    """
    Generic schema for a response from authentication endpoints.
    It includes a simple message and an optional token.
    """

    message: str = Field(
        ...,
        description="A user-friendly message describing the result of the operation.",
        examples=["OTP sent successfully", "Admin authentication successful"],
    )
    token: Optional[str] = Field(
        None,
        description="An optional JWT or similar access token returned on successful authentication.",
    )


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CASTokenRequest(BaseModel):
    """
    Schema for a request to exchange a CAS ticket for an access token.
    """

    cas: str
