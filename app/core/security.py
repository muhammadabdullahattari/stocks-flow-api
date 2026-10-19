from passlib.context import CryptContext
from jose import JWTError, jwt
from app.core.config import settings
from fastapi.security import HTTPBearer
from fastapi import HTTPException, status
from typing import Optional
import logging
from app.core.supabase_client import supabase
import hashlib

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def verify_supabase_token(token: str) -> dict:
    # 1. Attempt fast local cryptographic JWT verification (0.1ms, avoids external HTTP roundtrip)
    if getattr(settings, "SUPABASE_JWT_SECRET", None):
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            if payload and "sub" in payload:
                return {
                    "sub": str(payload["sub"]),
                    "email": payload.get("email"),
                    "user_metadata": payload.get("user_metadata", {}) or {}
                }
        except Exception:
            # Fallback to Supabase API if local signature verification fails
            pass

    try:
        response = supabase.auth.get_user(token)        
        
        if hasattr(response, 'user'):
            user = response.user
        else:
            user = response
        
        if not user or not hasattr(user, 'id'):
            logger.error(f"Invalid user object: {user}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or expired token")
        
        return {
            "sub": str(user.id),
            "email": getattr(user, 'email', None),
            "user_metadata": getattr(user, 'user_metadata', {}) or {}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )


def get_user_id_from_token(token: str) -> str:
    payload = verify_supabase_token(token)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID"
        )
    return user_id


def get_token_from_header(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    return parts[1]