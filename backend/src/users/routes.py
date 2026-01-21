"""
User profile routes: /me, /profile
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session, User
from src.auth.dependencies import get_current_active_user
from src.auth.schemas import (
    UserResponse, UserUpdate, PasswordChange, MessageResponse, AVAILABLE_LOCATIONS
)
from .service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's profile.

    Requires authentication.
    """
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update current user's profile.

    Can update:
    - **full_name**: Display name
    - **location**: User's town (must be from available locations)
    - **preferences**: User preferences (categories, notifications)
    """
    # Validate location if provided
    if update_data.location and update_data.location not in AVAILABLE_LOCATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid location. Available: {', '.join(AVAILABLE_LOCATIONS)}"
        )

    # Convert preferences to dict if provided
    preferences_dict = None
    if update_data.preferences:
        preferences_dict = update_data.preferences.model_dump(exclude_none=True)

    updated_user = await UserService.update_user_profile(
        session=session,
        user=current_user,
        full_name=update_data.full_name,
        location=update_data.location,
        preferences=preferences_dict
    )

    return UserResponse.model_validate(updated_user)


@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Change current user's password.

    Requires current password for verification.
    """
    success = await UserService.change_password(
        session=session,
        user=current_user,
        current_password=password_data.current_password,
        new_password=password_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    return MessageResponse(message="Password changed successfully")


@router.get("/me/subscription")
async def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get current user's subscription details.
    """
    subscription = await UserService.get_user_subscription(
        session=session,
        user_id=current_user.id
    )

    return {
        "tier": current_user.tier,
        "subscription": subscription.model_dump() if subscription else None
    }


@router.delete("/me", response_model=MessageResponse)
async def deactivate_account(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Deactivate current user's account.

    This doesn't delete the account, just marks it as inactive.
    """
    await UserService.deactivate_user(session, current_user)
    return MessageResponse(message="Account deactivated successfully")


@router.get("/locations")
async def get_available_locations():
    """
    Get list of available locations for user profile.
    """
    return {
        "locations": AVAILABLE_LOCATIONS,
        "default": "Rybno"
    }
