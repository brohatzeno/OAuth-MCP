"""
Mock Database Module.

Contains hardcoded user data and dummy records for development/testing.
In production, replace with actual database connections.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


# =====================================================================
# MOCK USERS DATABASE
# =====================================================================

@dataclass
class MockUser:
    """Mock user data structure"""
    email: str
    full_name: str
    password: str  # In production, use hashed passwords
    department: str


# Hardcoded mock users for testing
# Password: all users have password "password123" for demo purposes
MOCK_USERS: Dict[str, MockUser] = {
    "admin@gmail.com": MockUser(
        email="admin@gmail.com",
        full_name="Admin User",
        password="password123",
        department="Engineering"
    ),
    "qa@gmail.com": MockUser(
        email="qa@gmail.com",
        full_name="QA Team Lead",
        password="password123",
        department="Quality Assurance"
    ),
    "finance@gmail.com": MockUser(
        email="finance@gmail.com",
        full_name="Finance Manager",
        password="password123",
        department="Finance"
    ),
    "marketing@gmail.com": MockUser(
        email="marketing@gmail.com",
        full_name="Marketing Director",
        password="password123",
        department="Marketing"
    ),
    "sales@gmail.com": MockUser(
        email="sales@gmail.com",
        full_name="Sales Lead",
        password="password123",
        department="Sales"
    ),
}


def get_user_by_email(email: str) -> Optional[MockUser]:
    """
    Retrieve user from mock database by email

    Args:
        email: User email address

    Returns:
        MockUser object if found, None otherwise
    """
    return MOCK_USERS.get(email.lower())


def validate_user_credentials(email: str, password: str) -> bool:
    """
    Validate user credentials against mock database

    Args:
        email: User email address
        password: User password

    Returns:
        True if credentials are valid, False otherwise
    """
    user = get_user_by_email(email)

    if not user:
        return False

    # In production, use bcrypt.verify() or similar
    return user.password == password


# =====================================================================
# MOCK DUMMY DATA
# =====================================================================

DUMMY_DATA: Dict[str, Any] = {
    "records": [
        {"id": "demo-001", "label": "Sample customer", "status": "active"},
        {"id": "demo-002", "label": "Sample invoice", "status": "pending"},
        {"id": "demo-003", "label": "Sample support ticket", "status": "resolved"},
    ],
    "source": "static-demo",
}


def get_dummy_data() -> Dict[str, Any]:
    """Get static dummy data for testing."""
    return DUMMY_DATA.copy()


# =====================================================================
# IN-MEMORY TOKEN BLACKLIST
# Used for logout functionality
# =====================================================================

# Store revoked tokens here (token jti -> expiration_time)
TOKEN_BLACKLIST: Dict[str, datetime] = {}


def blacklist_token(token_jti: str, expiration: datetime) -> None:
    """
    Add token to blacklist (used on logout)

    Args:
        token_jti: JWT jti (unique identifier)
        expiration: Token expiration time
    """
    TOKEN_BLACKLIST[token_jti] = expiration


def is_token_blacklisted(token_jti: str) -> bool:
    """
    Check if token has been blacklisted

    Args:
        token_jti: JWT jti

    Returns:
        True if token is blacklisted, False otherwise
    """
    return token_jti in TOKEN_BLACKLIST


def cleanup_expired_tokens() -> None:
    """Remove expired tokens from blacklist"""
    now = datetime.utcnow()
    expired_tokens = [
        jti for jti, exp in TOKEN_BLACKLIST.items()
        if exp < now
    ]
    for jti in expired_tokens:
        del TOKEN_BLACKLIST[jti]
