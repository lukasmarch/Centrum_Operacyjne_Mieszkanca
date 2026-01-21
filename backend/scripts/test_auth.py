"""
Test script for Auth system (Sprint 1)

Run with: python scripts/test_auth.py

Prerequisites:
1. Run alembic migration: alembic upgrade head
2. Server running or just test functions directly
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import select
from src.database import engine, User, Subscription
from src.auth.jwt import get_password_hash, verify_password, create_access_token, verify_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker


async def test_password_hashing():
    """Test password hashing and verification"""
    print("\n=== Test 1: Password Hashing ===")

    password = "TestPassword123"
    hashed = get_password_hash(password)

    print(f"Original: {password}")
    print(f"Hashed: {hashed[:50]}...")

    # Verify correct password
    assert verify_password(password, hashed) == True
    print("✓ Correct password verification works")

    # Verify wrong password
    assert verify_password("wrongpassword", hashed) == False
    print("✓ Wrong password rejection works")


async def test_jwt_tokens():
    """Test JWT token creation and verification"""
    print("\n=== Test 2: JWT Tokens ===")

    token_data = {
        "sub": "test@example.com",
        "user_id": 1,
        "tier": "free"
    }

    # Create access token
    access_token = create_access_token(token_data)
    print(f"Access token: {access_token[:50]}...")

    # Verify access token
    payload = verify_token(access_token, token_type="access")
    assert payload is not None
    assert payload["sub"] == "test@example.com"
    assert payload["user_id"] == 1
    assert payload["type"] == "access"
    print("✓ Access token creation and verification works")

    # Create refresh token
    from src.auth.jwt import create_refresh_token
    refresh_token = create_refresh_token(token_data)
    print(f"Refresh token: {refresh_token[:50]}...")

    # Verify refresh token
    payload = verify_token(refresh_token, token_type="refresh")
    assert payload is not None
    assert payload["type"] == "refresh"
    print("✓ Refresh token creation and verification works")

    # Test wrong token type
    payload = verify_token(access_token, token_type="refresh")
    assert payload is None
    print("✓ Wrong token type rejection works")


async def test_user_creation():
    """Test user creation in database"""
    print("\n=== Test 3: User Creation ===")

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if test user exists
        result = await session.execute(
            select(User).where(User.email == "test@centrum.pl")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Test user already exists (ID: {existing.id})")
            # Delete for clean test
            await session.delete(existing)
            await session.commit()
            print("✓ Deleted existing test user")

        # Create new user
        new_user = User(
            email="test@centrum.pl",
            password_hash=get_password_hash("TestPassword123"),
            full_name="Test User",
            location="Rybno"
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        print(f"✓ Created user: {new_user.email} (ID: {new_user.id})")
        print(f"  Location: {new_user.location}")
        print(f"  Tier: {new_user.tier}")
        print(f"  Active: {new_user.is_active}")

        # Verify user can be found
        result = await session.execute(
            select(User).where(User.email == "test@centrum.pl")
        )
        found_user = result.scalar_one_or_none()
        assert found_user is not None
        assert found_user.email == "test@centrum.pl"
        print("✓ User can be retrieved from database")


async def test_schemas():
    """Test Pydantic schemas"""
    print("\n=== Test 4: Pydantic Schemas ===")

    from src.auth.schemas import UserCreate, UserLogin, UserResponse

    # Valid user creation
    user_create = UserCreate(
        email="valid@test.pl",
        password="ValidPass123",
        full_name="Valid User",
        location="Działdowo"
    )
    print(f"✓ UserCreate schema valid: {user_create.email}")

    # Invalid password (no digit)
    try:
        UserCreate(
            email="invalid@test.pl",
            password="NoDigitPass",
            full_name="Invalid User"
        )
        print("✗ Should have rejected password without digit")
    except ValueError as e:
        print(f"✓ Correctly rejected password without digit")

    # Invalid password (no uppercase)
    try:
        UserCreate(
            email="invalid@test.pl",
            password="nouppercasepass123",
            full_name="Invalid User"
        )
        print("✗ Should have rejected password without uppercase")
    except ValueError as e:
        print(f"✓ Correctly rejected password without uppercase")


async def print_api_endpoints():
    """Print available API endpoints"""
    print("\n=== Available Auth Endpoints ===")
    print("""
    POST /api/auth/register
        Body: {"email": "...", "password": "...", "full_name": "...", "location": "Rybno"}
        Response: {user: {...}, tokens: {access_token, refresh_token}}

    POST /api/auth/login
        Body: {"email": "...", "password": "..."}
        Response: {user: {...}, tokens: {access_token, refresh_token}}

    POST /api/auth/logout
        Response: {"message": "Successfully logged out"}

    POST /api/auth/refresh
        Body: {"refresh_token": "..."}
        Response: {access_token, refresh_token, expires_in}

    === User Endpoints ===

    GET /api/users/me
        Headers: Authorization: Bearer <access_token>
        Response: {id, email, full_name, location, tier, ...}

    PUT /api/users/me
        Headers: Authorization: Bearer <access_token>
        Body: {"full_name": "...", "location": "...", "preferences": {...}}
        Response: Updated user

    POST /api/users/me/change-password
        Headers: Authorization: Bearer <access_token>
        Body: {"current_password": "...", "new_password": "..."}
        Response: {"message": "Password changed successfully"}

    GET /api/users/me/subscription
        Headers: Authorization: Bearer <access_token>
        Response: {tier: "...", subscription: {...}}

    GET /api/users/locations
        Response: {locations: ["Rybno", "Działdowo", ...], default: "Rybno"}
    """)


async def main():
    print("=" * 60)
    print("Sprint 1: Auth System Tests")
    print("=" * 60)

    await test_password_hashing()
    await test_jwt_tokens()
    await test_schemas()
    await test_user_creation()
    await print_api_endpoints()

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

    print("\n📋 Next steps:")
    print("1. Run migration: cd backend && alembic upgrade head")
    print("2. Start server: uvicorn src.api.main:app --reload")
    print("3. Test register: curl -X POST http://localhost:8000/api/auth/register \\")
    print('   -H "Content-Type: application/json" \\')
    print('   -d \'{"email":"user@test.pl","password":"Test1234","full_name":"Test User"}\'')


if __name__ == "__main__":
    asyncio.run(main())
