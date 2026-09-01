from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.domain.models import User
from app.storage.db import get_session

DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(request: Request, db: DbSession) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_completed_onboarding(user: CurrentUser) -> User:
    if user.profile is None or not user.profile.onboarding_completed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Avval ro'yxatdan o'ting"
        )
    return user


CompletedOnboardingUser = Annotated[User, Depends(require_completed_onboarding)]
