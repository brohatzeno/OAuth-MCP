"""
entity.co Mock Backend Service.

FastAPI-based mock backend for internal testing and Claude custom connector integration.

Features:
    - JWT-based authentication for @gmail.com users
    - Mock user database
    - Dummy data APIs
    - Claude connector compatibility (OpenAPI schema, JSON APIs)
    - Token revocation on logout
    - Full CORS support
"""

import os
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from .auth import (
    create_access_token,
    get_token_expiration,
    get_token_jti,
    security,
    validate_email_domain,
    verify_token,
)
from .database import (
    blacklist_token,
    cleanup_expired_tokens,
    get_dummy_data,
    get_user_by_email,
    is_token_blacklisted,
    validate_user_credentials,
)
from .models import (
    DummyDataResponse,
    ErrorResponse,
    HealthCheckResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserResponse,
)

# Load environment variables
load_dotenv()

# Configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
COMPANY_DOMAIN = os.getenv("COMPANY_DOMAIN", "gmail.com")

# =====================================================================
# FASTAPI APP SETUP
# =====================================================================

app = FastAPI(
    title="entity.co Mock Backend",
    description="Mock backend service for internal testing and Claude custom connector integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# AUTH HELPERS
# =====================================================================

async def get_current_active_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate a bearer token, reject revoked tokens, and return the user email."""
    token = credentials.credentials
    payload = verify_token(token)
    token_jti = payload.get("jti")

    if token_jti and is_token_blacklisted(token_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing email claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return email


# =====================================================================
# HEALTH CHECK ENDPOINTS
# =====================================================================

@app.get(
    "/",
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Health Check",
    description="Verify that the backend service is running and responding"
)
async def health_check():
    """Health check endpoint - confirms backend is operational"""
    return HealthCheckResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Health Status",
    description="Detailed health status endpoint"
)
async def health_status():
    """Detailed health check with service status"""
    return HealthCheckResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )


# =====================================================================
# AUTHENTICATION ENDPOINTS
# =====================================================================

@app.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Login",
    description="Authenticate with email and password to receive JWT token",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Invalid credentials"
        },
        422: {
            "description": "Validation error (invalid email format or missing fields)"
        }
    }
)
async def login(request: LoginRequest, response: Response):
    """
    Login endpoint - authenticate and receive JWT token

    Step-by-step flow:
    1. Client sends email and password
    2. Backend validates credentials against mock database
    3. Backend validates email domain (@gmail.com required)
    4. Backend generates JWT token with user claims
    5. Backend sets JWT in secure HTTP-only cookie
    6. Backend returns access_token for API requests

    Usage:
        POST /login
        {
            "email": "admin@gmail.com",
            "password": "password123"
        }

    Response:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "user": {
                "email": "admin@gmail.com",
                "full_name": "Admin User",
                "department": "Engineering"
            }
        }
    """

    # Step 1: Validate email domain
    if not validate_email_domain(request.email, COMPANY_DOMAIN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Email must be from @{COMPANY_DOMAIN} domain",
        )

    # Step 2: Validate credentials
    if not validate_user_credentials(request.email, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Step 3: Get user from database
    user = get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Step 4: Generate JWT token with user claims
    token_data = {
        "sub": user.email,           # Subject (unique user identifier)
        "full_name": user.full_name,
        "department": user.department,
    }
    access_token = create_access_token(data=token_data)

    # Step 5: Set JWT in secure HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=24 * 60 * 60,  # 24 hours
        httponly=True,
        secure=not DEBUG,  # HTTPS only in production
        samesite="Lax",
    )

    # Step 6: Return response
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            email=user.email,
            full_name=user.full_name,
            department=user.department,
        )
    )


@app.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Logout",
    description="Logout and invalidate JWT token"
)
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Logout endpoint - clear session and blacklist token

    Steps:
    1. Extracts JWT token from Authorization header
    2. Gets token's jti (unique identifier)
    3. Gets token expiration time
    4. Adds token to blacklist to prevent reuse
    5. Clears HTTP-only cookie
    6. Returns success message

    Usage:
        POST /logout
        Authorization: Bearer <your_jwt_token>

    Response:
        {
            "message": "Successfully logged out"
        }
    """

    token = credentials.credentials
    verify_token(token)

    jti = get_token_jti(token)
    expiration = get_token_expiration(token)
    if jti and expiration:
        blacklist_token(jti, expiration)

    # Clear cookie
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=not DEBUG,
        samesite="Lax",
    )

    return LogoutResponse(message="Successfully logged out")


@app.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Get Current User",
    description="Get information about the authenticated user",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized - no valid token provided"
        }
    }
)
async def get_me(current_user: str = Depends(get_current_active_user)):
    """
    Get current authenticated user information

    Requires valid JWT token in Authorization header or cookie

    Usage:
        GET /me
        Authorization: Bearer <your_jwt_token>

    Response:
        {
            "email": "admin@gmail.com",
            "full_name": "Admin User",
            "department": "Engineering"
        }
    """

    # Retrieve user from database
    user = get_user_by_email(current_user)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        email=user.email,
        full_name=user.full_name,
        department=user.department,
    )


# =====================================================================
# DUMMY DATA ENDPOINTS
# =====================================================================

@app.get(
    "/dummy-data",
    response_model=DummyDataResponse,
    status_code=status.HTTP_200_OK,
    tags=["Dummy Data"],
    summary="Get Dummy Data",
    description="Get static dummy data for connector testing"
)
async def get_static_dummy_data():
    """
    Get static dummy data.

    Returns sample records that are safe for local testing.

    Usage:
        GET /dummy-data

    Response:
        {
            "records": [
                {"id": "demo-001", "label": "Sample customer", "status": "active"}
            ],
            "source": "static-demo",
            "timestamp": "2024-05-13T10:00:00"
        }
    """
    data = get_dummy_data()
    return DummyDataResponse(
        records=data["records"],
        source=data["source"],
        timestamp=datetime.utcnow(),
    )


# =====================================================================
# PROTECTED TEST ENDPOINTS (Claude Connector Testing)
# =====================================================================

@app.get(
    "/api/test/protected",
    tags=["Testing"],
    summary="Protected Test Endpoint",
    description="Test endpoint requiring authentication (for Claude connector testing)"
)
async def protected_test_endpoint(current_user: str = Depends(get_current_active_user)):
    """
    Protected test endpoint - requires valid JWT token

    This endpoint is useful for testing Claude custom connectors
    to ensure authentication is working correctly

    Usage:
        GET /api/test/protected
        Authorization: Bearer <your_jwt_token>
    """

    user = get_user_by_email(current_user)
    return {
        "message": "This is a protected endpoint",
        "authenticated_user": current_user,
        "user_department": user.department if user else "Unknown",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post(
    "/api/test/echo",
    tags=["Testing"],
    summary="Echo Test Endpoint",
    description="Echo back any JSON data (for testing)",
    status_code=status.HTTP_200_OK,
)
async def echo_test(data: Dict[str, Any]):
    """
    Echo test endpoint - returns the data you send (for testing API integration)

    Usage:
        POST /api/test/echo
        {
            "message": "hello",
            "value": 123
        }

    Response:
        {
            "received": {...},
            "timestamp": "2024-05-13T10:00:00"
        }
    """

    return {
        "received": data,
        "timestamp": datetime.utcnow().isoformat(),
    }


# =====================================================================
# ERROR HANDLERS
# =====================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent error format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    """Handle Pydantic validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "status_code": 422,
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    if DEBUG:
        print(f"Unexpected error: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "Internal server error",
            "status_code": 500,
        },
    )


# =====================================================================
# STARTUP/SHUTDOWN EVENTS
# =====================================================================

@app.on_event("startup")
async def startup_event():
    """Startup event - initialization"""
    print("=" * 60)
    print("entity.co Mock Backend Starting...")
    print("=" * 60)
    print(f"Debug Mode: {DEBUG}")
    print(f"Allowed Origins: {ALLOWED_ORIGINS}")
    print(f"Company Domain: {COMPANY_DOMAIN}")
    scheme = "https" if os.getenv("SSL_CERT_FILE") and os.getenv("SSL_KEY_FILE") else "http"
    port = os.getenv("SERVER_PORT", "8000")
    print(f"OpenAPI Docs: {scheme}://localhost:{port}/docs")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event - cleanup"""
    cleanup_expired_tokens()
    print("entity.co Mock Backend shutting down...")


# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8000"))
    ssl_certfile = os.getenv("SSL_CERT_FILE") or None
    ssl_keyfile = os.getenv("SSL_KEY_FILE") or None

    uvicorn.run(
        "entity_backend.app:app",
        host=host,
        port=port,
        reload=DEBUG,
        log_level="info",
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )
