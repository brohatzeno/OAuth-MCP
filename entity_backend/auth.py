"""
JWT Authentication Module.

Handles JWT token creation, validation, and verification.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your_super_secret_key_change_in_production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Security scheme for OpenAPI/Swagger
security = HTTPBearer(description="Bearer token authentication")


# =====================================================================
# JWT TOKEN CREATION & VALIDATION
# =====================================================================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token

    Args:
        data: Claims to include in token (e.g., email, user info)
        expires_delta: Custom expiration time (uses default if not provided)

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Add standard JWT claims
    to_encode.update({
        "exp": expire,                      # Expiration time
        "iat": datetime.utcnow(),          # Issued at
        "jti": str(uuid.uuid4()),          # Unique token identifier for blacklist
    })

    # Encode JWT using HS256 algorithm
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token

    Args:
        token: JWT token to verify

    Returns:
        Decoded token claims

    Raises:
        HTTPException if token is invalid or expired
    """
    try:
        # Decode and verify token signature
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_token_expiration(token: str) -> Optional[datetime]:
    """Get token expiration time"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if exp:
            return datetime.utcfromtimestamp(exp)
        return None
    except JWTError:
        return None


def get_token_jti(token: str) -> Optional[str]:
    """Get token's unique identifier (jti) for blacklisting"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("jti")
    except JWTError:
        return None


# =====================================================================
# CREDENTIALS VALIDATION
# =====================================================================

def validate_email_domain(email: str, allowed_domain: str = "gmail.com") -> bool:
    """
    Validate that email belongs to allowed domain

    Args:
        email: Email address to validate
        allowed_domain: Required email domain

    Returns:
        True if email is from allowed domain
    """
    if "@" not in email:
        return False

    domain = email.split("@")[1].lower()
    return domain == allowed_domain.lower()
