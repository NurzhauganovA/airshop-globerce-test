import datetime
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    HTTPBasic,
    HTTPBasicCredentials,
)
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.controllers.internal import user_controller
from jose import jwt
from app.models.internal_model import User, UserSession as DBUserSession


# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token settings
JWT_SECRET_KEY = (
    settings.SECRET_KEY
)  # Replace with a strong, randomly generated secret key
JWT_ALGORITHM = "HS256"  # Algorithm for signing the JWT


# Security scheme for requiring authorization
security = HTTPBearer()
basic_auth = HTTPBasic()


def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_and_refresh_tokens(
    db: Session,
    user_id: str,
    user_session_data: dict,
    access_token_expire_minutes: Optional[int] = None,
    refresh_token_expire_days: Optional[int] = None,
) -> dict:
    """
    Creates a UserSession in the DB and corresponding JWT access and refresh tokens.

    Args:
        db (Session): The database session.
        user_id (str): The ID of the user.
        user_session_data (dict): User session information.
        access_token_expire_minutes (Optional[int]): Custom expiry for access token.
        refresh_token_expire_days (Optional[int]): Custom expiry for refresh token and session.

    Returns:
        dict: A dictionary containing the access and refresh tokens.
    """
    # 1. Create payload for the REFRESH token. This will be the main session identifier.
    refresh_jti = str(uuid.uuid4())
    # Refresh token duration (e.g., 7 days)
    if refresh_token_expire_days is None:
        refresh_token_expire_days = 7  # Default to 7 days
    refresh_token_expires = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(days=refresh_token_expire_days)
    refresh_payload = {
        "sub": str(user_id),  # Subject (user ID)
        "jti": refresh_jti,  # JWT ID, unique for each token
        "exp": refresh_token_expires,  # Expiration time
        "type": "refresh",  # Token type
    }

    # 2. Create the session in the DB using the REFRESH token's details.
    db_session = DBUserSession(
        jti=refresh_jti,
        user_id=user_id,
        ip_address=user_session_data.get("ip_address"),
        user_agent=user_session_data.get("user_agent"),
        validation_type=user_session_data.get("validation_type", "none"),
        expires_at=refresh_token_expires,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # 3. Create payload for the ACCESS token.
    if access_token_expire_minutes is None:
        access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    access_token_expires = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(minutes=access_token_expire_minutes)
    access_payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),  # Access token gets its own JTI
        "session_jti": refresh_jti,  # Link to the refresh token's session
        "exp": access_token_expires,
        "type": "access",  # Token type
    }

    access_token = jwt.encode(access_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return {"access_token": access_token, "refresh_token": refresh_token}


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> User:
    """
    Dependency to get the current user from a JWT token.
    Decodes the token, validates the session against the DB, and returns the user.

    Args:
        request (Request): The incoming request.
        db (Session): The database session.
        credentials (HTTPAuthorizationCredentials): The authorization credentials containing the JWT.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If the token is invalid, the session is not found, or validation fails.
    """
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type, expected access token",
            )

        user_id = payload.get("sub")
        session_jti = payload.get("session_jti")
        if user_id is None or session_jti is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims"
            )

        # Look up session in DB
        db_session = (
            db.query(DBUserSession).filter(DBUserSession.jti == session_jti).first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found"
            )

        if not db_session.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been terminated",
            )

        if db_session.expires_at < datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=None
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired"
            )

        # Validate session details based on validation_type
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent")

        if db_session.validation_type == "ip" and db_session.ip_address != ip_address:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid IP Address"
            )
        elif (
            db_session.validation_type == "user_agent"
            and db_session.user_agent != user_agent
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid User Agent"
            )
        elif db_session.validation_type == "all" and (
            db_session.ip_address != ip_address or db_session.user_agent != user_agent
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid IP Address or User Agent",
            )

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    except Exception as e:
        print(f"Unexpected error during token decoding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token validation",
        )


def get_current_technical_user_basic_auth(
    credentials: HTTPBasicCredentials = Depends(basic_auth),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency for HTTP Basic authentication.
    Authenticates a user and verifies they have 'is_technical' flag.
    """
    user = user_controller.get_by_username(db, username=credentials.username)
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    if not user.is_technical:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )

    return user
