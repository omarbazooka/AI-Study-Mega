from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.db.supabase_client import get_supabase_client
from app.core.config import settings

security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    """
    Centralized authentication dependency supporting both Supabase and Mock authentication modes.
    Resolves the authenticated user's identity based on Settings.AUTH_MODE.
    Raises 401 if in Supabase mode and credentials are missing, invalid, or expired.
    """
    if settings.AUTH_MODE == "mock":
        return settings.MOCK_USER_ID

    if settings.AUTH_MODE == "supabase":
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided."
            )
            
        token = credentials.credentials
        try:
            supabase = get_supabase_client()
            # Verify the access token with Supabase Auth
            user_resp = supabase.auth.get_user(token)
            if user_resp and user_resp.user:
                return str(user_resp.user.id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired authentication token: {str(e)}"
            )
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate authentication credentials."
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Invalid server authentication configuration."
    )

