import os
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

_bearer = HTTPBearer()


@dataclass(frozen=True)
class UserContext:
    user_id: str
    is_anonymous: bool


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserContext:
    """
    Verify the Supabase JWT and return a UserContext.

    Raises:
        401 — token missing, malformed, or expired
        401 — token lacks a 'sub' claim
    """
    supabase_jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured.",
        )
    
    try:
        payload = jwt.decode(
            credentials.credentials,
            supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Supabase JWTs omit 'aud' by default
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserContext(
        user_id=user_id,
        is_anonymous=payload.get("is_anonymous", False),
    )


def require_authenticated(user: UserContext) -> None:
    """
    Raise 403 if the user holds an anonymous session.
    Call this at the top of any endpoint that requires a full account.
    """
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a logged-in account. "
                   "Sign up or log in to access conversation history.",
        )
