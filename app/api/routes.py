from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import CompletedOnboardingUser, CurrentUser, DbSession
from app.api.schemas import (
    DevLoginRequest,
    MockAnswerIn,
    PracticeAnswerIn,
    PracticeSessionIn,
    ProfileIn,
    TelegramLoginRequest,
)
from app.api.telegram_auth import TelegramAuthError, validate_init_data
from app.config import get_settings
from app.domain.enums import Category, Language, Topic
from app.domain.models import StudentProfile
from app.observability.logging import log_event
from app.services import mock, practice
from app.services.users import upsert_telegram_user, user_out

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@router.post("/auth/telegram-mini-app")
def telegram_login(payload: TelegramLoginRequest, request: Request, db: DbSession) -> dict:
    try:
        auth_payload = validate_init_data(payload.init_data)
    except TelegramAuthError as exc:
        log_event("telegram_login_failed", reason=str(exc))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = upsert_telegram_user(db, auth_payload["user"])
    request.session.clear()
    request.session["user_id"] = user.id
    log_event("telegram_login_succeeded", user_id=user.id)
    return {"user": user_out(user)}


@router.get("/auth/me")
def me(user: CurrentUser) -> dict:
    return {"user": user_out(user), "profile": _profile_out(user.profile)}


@router.post("/auth/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/dev/config")
def dev_config() -> dict:
    settings = get_settings()
    return {"dev_auth_enabled": settings.is_dev_auth_available, "app_env": settings.app_env}


@router.post("/dev/login")
def dev_login(payload: DevLoginRequest, request: Request, db: DbSession) -> dict:
    # Gated to APP_ENV=development AND DEV_AUTH_ENABLED. 404 otherwise.
    if not get_settings().is_dev_auth_available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dev login is disabled")
    user = upsert_telegram_user(
        db,
        {
            "id": payload.telegram_id,
            "username": payload.username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
        },
    )
    request.session.clear()
    request.session["user_id"] = user.id
    log_event("dev_login_succeeded", user_id=user.id)
    return {"user": user_out(user)}


# --------------------------------------------------------------------------- #
# Profile / onboarding
# --------------------------------------------------------------------------- #
def _profile_out(profile: StudentProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "display_name": profile.display_name,
        "ranking_name": profile.ranking_name,
        "show_on_ranking": profile.show_on_ranking,
        "category": profile.category.value,
        "language": profile.language.value,
        "target_exam_date": profile.target_exam_date.isoformat()
        if profile.target_exam_date
        else None,
        "daily_goal": profile.daily_goal,
        "timezone": profile.timezone,
        "onboarding_completed": profile.onboarding_completed,
    }


@router.put("/profile")
def put_profile(payload: ProfileIn, user: CurrentUser, db: DbSession) -> dict:
    profile = user.profile
    if profile is None:
        profile = StudentProfile(user_id=user.id)
        db.add(profile)
    profile.display_name = payload.display_name
    profile.ranking_name = payload.ranking_name or payload.display_name
    profile.show_on_ranking = payload.show_on_ranking
    profile.category = Category(payload.category)
    profile.language = Language(payload.language)
    profile.target_exam_date = payload.target_exam_date
    profile.daily_goal = payload.daily_goal
    profile.timezone = payload.timezone
    profile.onboarding_completed = True
    db.commit()
    db.refresh(profile)
    return {"profile": _profile_out(profile)}


# --------------------------------------------------------------------------- #
# Practice loop (onboarding-gated)
# --------------------------------------------------------------------------- #
def _parse_topic(topic: str | None) -> Topic | None:
    if topic is None or topic == "":
        return None
    try:
        return Topic(topic)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum mavzu"
        ) from exc


@router.post("/practice/sessions")
def create_practice_session(
    payload: PracticeSessionIn, user: CompletedOnboardingUser, db: DbSession
) -> dict:
    topic = _parse_topic(payload.topic)
    session = practice.create_practice_session(db, user, topic)
    return {
        "id": session.id,
        "topic": session.topic.value if session.topic else None,
        "source": session.source.value,
        "category": session.category.value,
    }


@router.get("/practice/sessions/{session_id}")
def get_practice_session(
    session_id: str, user: CompletedOnboardingUser, db: DbSession
) -> dict:
    session = practice.get_owned_session(db, user, session_id)
    return {
        "id": session.id,
        "topic": session.topic.value if session.topic else None,
        "source": session.source.value,
        "category": session.category.value,
        "started_at": session.started_at.isoformat() if session.started_at else None,
    }


@router.get("/practice/questions/next")
def next_question(
    user: CompletedOnboardingUser,
    db: DbSession,
    topic: str | None = Query(default=None),
) -> dict:
    parsed = _parse_topic(topic)
    payload = practice.next_question_payload(db, parsed)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bu mavzuda savol topilmadi"
        )
    return payload


@router.post("/practice/answers")
def submit_practice_answer(
    payload: PracticeAnswerIn, user: CompletedOnboardingUser, db: DbSession
) -> dict:
    return practice.submit_answer(
        db,
        user,
        practice_session_id=payload.practice_session_id,
        question_id=payload.question_id,
        selected_option_id=payload.selected_option_id,
        time_spent_seconds=payload.time_spent_seconds,
    )


# --------------------------------------------------------------------------- #
# Mock exam (onboarding-gated) — docs/spec/03, 05, 09, 12
# --------------------------------------------------------------------------- #
@router.post("/mock/attempts")
def start_mock(user: CompletedOnboardingUser, db: DbSession) -> dict:
    category = user.profile.category
    language = user.profile.language
    attempt = mock.start_attempt(db, user, category=category, language=language)
    return mock.attempt_state(db, attempt)


@router.get("/mock/attempts/current")
def current_mock(user: CompletedOnboardingUser, db: DbSession) -> dict:
    state = mock.get_current(db, user)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi"
        )
    return state


@router.get("/mock/attempts/{attempt_id}")
def get_mock(attempt_id: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    attempt = mock.get_owned_attempt(db, user, attempt_id)
    attempt = mock.finalize_if_expired(db, attempt)
    return mock.attempt_state(db, attempt)


@router.post("/mock/attempts/{attempt_id}/answers")
def save_mock_answer(
    attempt_id: str, payload: MockAnswerIn, user: CompletedOnboardingUser, db: DbSession
) -> dict:
    return mock.save_answer(
        db,
        user,
        attempt_id=attempt_id,
        question_version_id=payload.question_version_id,
        selected_option_id=payload.selected_option_id,
        marked_for_review=payload.marked_for_review,
    )


@router.post("/mock/attempts/{attempt_id}/submit")
def submit_mock(attempt_id: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    return mock.submit_attempt(db, user, attempt_id)


@router.get("/mock/attempts/{attempt_id}/review")
def review_mock(attempt_id: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    return mock.review(db, user, attempt_id)
