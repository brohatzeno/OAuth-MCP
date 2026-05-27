"""
Pydantic Models for entity.co Mock Backend.

Defines request/response schemas for all API endpoints.
"""

from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, EmailStr, Field


# =====================================================================
# AUTHENTICATION MODELS
# =====================================================================

class LoginRequest(BaseModel):
    """Request model for login endpoint"""
    email: EmailStr = Field(..., description="User email (must be @gmail.com domain)")
    password: str = Field(..., description="User password", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@gmail.com",
                "password": "password123"
            }
        }


class UserResponse(BaseModel):
    """User information response model"""
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    department: str = Field(..., description="User department")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@gmail.com",
                "full_name": "Admin User",
                "department": "Engineering"
            }
        }


class LoginResponse(BaseModel):
    """Response model for login endpoint"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    user: UserResponse = Field(..., description="Authenticated user information")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "email": "admin@gmail.com",
                    "full_name": "Admin User",
                    "department": "Engineering"
                }
            }
        }


class LogoutResponse(BaseModel):
    """Response model for logout endpoint"""
    message: str = Field(..., description="Logout confirmation message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Successfully logged out"
            }
        }


# =====================================================================
# DUMMY DATA MODELS
# =====================================================================

class DummyDataResponse(BaseModel):
    """Response model for static dummy data."""
    records: list[Dict[str, Any]] = Field(..., description="Static demo records")
    source: str = Field(..., description="Origin of the dummy data")
    timestamp: datetime = Field(..., description="Current server timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "records": [
                    {"id": "demo-001", "label": "Sample customer", "status": "active"}
                ],
                "source": "static-demo",
                "timestamp": "2024-05-13T10:00:00",
            }
        }


# =====================================================================
# ERROR MODELS
# =====================================================================

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error type/code")
    message: str = Field(..., description="Human-readable error message")
    status_code: int = Field(..., description="HTTP status code")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "invalid_credentials",
                "message": "Invalid email or password",
                "status_code": 401
            }
        }


class ValidationErrorDetail(BaseModel):
    """Validation error detail"""
    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Validation error message")


class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    error: str = Field(default="validation_error", description="Error type")
    details: list[ValidationErrorDetail] = Field(..., description="List of validation errors")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "validation_error",
                "details": [
                    {
                        "field": "email",
                        "message": "must be a valid email from @gmail.com domain"
                    }
                ]
            }
        }


# =====================================================================
# HEALTH CHECK MODELS
# =====================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current server timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "timestamp": "2024-05-13T10:00:00"
            }
        }
