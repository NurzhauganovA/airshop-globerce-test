# app/api/v1/endpoints/auth.py

import random
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import redis.asyncio as redis

from app.controllers.notification_controller import NotificationController
from app.core import security
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.core.database import get_db
from app.controllers.internal import customer_controller, user_controller
from app.models.internal_model import User
from app.schemas.auth_schemas import (
    OTPSendRequest,
    OTPVerifyRequest,
    RefreshTokenRequest,
    Token,
    CASTokenRequest,
)
from app.schemas.user_schemas import UserProfileSchema, UserProfileUpdateSchema
from app.services.ibcc_service import IBCCAuthService


# We'll use a router for each major group of endpoints
router = APIRouter()
ibcc_service = IBCCAuthService()


@router.post("/send-otp", status_code=status.HTTP_200_OK)
async def send_otp(
    request: OTPSendRequest,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """
    Checks if a user exists with the given phone number. If not, it creates one.
    Then, it generates and "sends" an OTP to the user's phone number.
    In a real application, this would integrate with an SMS gateway.
    """
    # Check if user exists, or create a new one
    user = user_controller.get_by_phone(db, phone_number=request.phone_number)
    if not user:
        user = user_controller.create_with_phone(db, phone_number=request.phone_number)
        # After creating the user, create the associated customer profile
        db.commit()
        db.refresh(user)
        customer_controller.create_from_user(db, user=user)
        db.commit()
        db.refresh(user)

    # Generate a 6-digit OTP
    otp_expiry_seconds = 5 * 60  # 5 minutes

    if settings.MOCK_OTP:
        otp_code = settings.DEFAULT_OTP
    else:
        otp_code = str(random.randint(100000, 999999))
        notif_service = NotificationController(db=db)
        try:
            await notif_service.send_sms_by_purpose(
                "AUTHENTICATION",
                request.phone_number,
                *[otp_code],
            )
        except ValueError as e:
            # если не найден шаблон по purpose, или проблема с записью уведомления
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            # сбой отправки через провайдера
            raise HTTPException(status_code=502, detail="Failed to send OTP via SMS")

        # In a real app, you would send the OTP via SMS here.
        # For this example, we'll just print it to the console for easy testing.
        print(f"OTP for {request.phone_number}: {otp_code}")

    # Store the OTP in Redis with an expiration
    await redis_client.set(
        f"otp:{request.phone_number}", otp_code, ex=otp_expiry_seconds
    )

    return {"message": "OTP sent successfully."}


@router.post("/verify-otp", response_model=Token)
async def verify_otp(
    request: Request,
    otp_data: OTPVerifyRequest,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """
    Verifies an OTP. If valid, it logs in the user
    then returns an access token.
    """
    otp_key = f"otp:{otp_data.phone_number}"
    stored_otp = await redis_client.get(otp_key)

    if not stored_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP is invalid or has expired.",
        )

    if stored_otp != otp_data.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP."
        )

    # OTP is valid, clear it from storage to prevent reuse
    await redis_client.delete(otp_key)

    # At this point, the user should already exist.
    user = user_controller.get_by_phone(db, phone_number=otp_data.phone_number)
    if not user:
        # This is a safeguard. This case should not be reached if /send-otp is used correctly.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please request an OTP first.",
        )

    # Create user session data for the JWT
    user_session_data = {
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "validation_type": "none",
    }

    # Create and return the access token
    tokens = security.create_access_and_refresh_tokens(
        db=db,
        user_id=user.id,
        user_session_data=user_session_data,
    )
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }


@router.post("/login/access-token", response_model=Token)
async def login_for_access_token(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # First, try to authenticate using phone number, then by username.
    user = user_controller.get_by_phone(db, phone_number=form_data.username)
    if not user:
        user = user_controller.get_by_username(db, username=form_data.username)

    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create user session data
    user_session_data = {
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "validation_type": "none",  # No validation for standard login tokens
    }

    tokens = security.create_access_and_refresh_tokens(
        db=db,
        user_id=user.id,
        user_session_data=user_session_data,
    )
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }


@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    request: Request,
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Refreshes an access token using a valid refresh token.
    This endpoint uses refresh token rotation for enhanced security.
    """
    try:
        payload = security.jwt.decode(
            token_data.refresh_token,
            security.JWT_SECRET_KEY,
            algorithms=[security.JWT_ALGORITHM],
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type, expected refresh token",
            )

        user_id = payload.get("sub")
        jti = payload.get("jti")

        if user_id is None or jti is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token claims",
            )

        user = user_controller.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_session = (
            db.query(security.DBUserSession)
            .filter(security.DBUserSession.jti == jti)
            .first()
        )

        if not db_session or not db_session.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found or terminated. Token may have been revoked.",
            )

        # Invalidate old session (for refresh token rotation)
        db.delete(db_session)
        db.commit()

        # Create new session and tokens
        user_session_data = {
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "validation_type": db_session.validation_type,  # Carry over validation type
        }
        new_tokens = security.create_access_and_refresh_tokens(
            db=db, user_id=user_id, user_session_data=user_session_data
        )

        return {
            "access_token": new_tokens["access_token"],
            "refresh_token": new_tokens["refresh_token"],
            "token_type": "bearer",
        }

    except security.jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired"
        )
    except security.jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
        )


@router.get("/users/me", response_model=UserProfileSchema)
async def read_users_me(current_user: User = Depends(security.get_current_user)):

    user_response = UserProfileSchema.from_db_model(current_user)

    return user_response

@router.patch("/users/me", response_model=UserProfileSchema)
async def update_users_me(
    request: UserProfileUpdateSchema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    
    updated_user = request.update_db_model(current_user)
    db.add(updated_user)
    db.flush()
    db.commit()
    db.refresh(updated_user)

    return UserProfileSchema.from_db_model(updated_user)





@router.post("/cross-auth")
async def cross_auth(
    request: Request, cas_token_request: CASTokenRequest, db: Session = Depends(get_db)
):
    # make auth to IBUL
    # validate response
    # if ok create user_session
    ibul_user = await ibcc_service._get_ibcc_user(cas_token_request.cas)

    our_user = user_controller.get_by_phone(
        db=db, phone_number=ibul_user.user.phoneNumber
    )

    if not our_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found, ask to register first",
        )

    user_session_data = {
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "validation_type": "none",
    }

    # Create and return the access token
    tokens = security.create_access_and_refresh_tokens(
        db=db,
        user_id=our_user.id,
        user_session_data=user_session_data,
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }
