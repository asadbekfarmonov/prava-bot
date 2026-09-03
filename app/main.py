from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.config import get_settings
from app.observability.logging import configure_logging, log_event, log_exception
from app.storage.db import get_engine

# Strict Content-Security-Policy for the Mini App (docs/spec/05 + 09).
# Telegram loads the WebApp SDK from https://telegram.org; frames are allowed only
# for Telegram; SVG/plugins blocked via object-src 'none'.
CSP = (
    "default-src 'self'; "
    "media-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "script-src 'self' https://telegram.org; "
    "connect-src 'self' https://telegram.org https://*.telegram.org; "
    "frame-ancestors https://web.telegram.org https://*.telegram.org; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class _ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        # Vite emits content-hashed asset filenames, so they can be cached forever.
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        return response


def _cors_allow_origins(settings) -> list[str]:
    """Allowed CORS origins.

    Production (docs/spec/09 API security → CORS): allow ONLY the app origin and
    Telegram — never localhost. Development additionally allows the local Vite dev
    server so the Mini App can be iterated on locally.
    """
    telegram_origins = ["https://web.telegram.org", "https://telegram.org"]
    if settings.app_env == "development":
        return [
            settings.frontend_dev_url,
            settings.mini_app_url,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            *telegram_origins,
        ]
    # Production / staging: app origin + Telegram only. No localhost.
    return [settings.mini_app_url, *telegram_origins]


def register_frontend(app: FastAPI, frontend_dist_path: Path) -> None:
    index_path = frontend_dist_path / "index.html"
    assets_path = frontend_dist_path / "assets"
    if not index_path.exists():
        return
    if assets_path.exists():
        app.mount(
            "/assets", _ImmutableStaticFiles(directory=str(assets_path)), name="frontend-assets"
        )

    @app.get("/", include_in_schema=False)
    @app.head("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(index_path, headers={"Cache-Control": "no-cache"})

    @app.get("/{full_path:path}", include_in_schema=False)
    @app.head("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_route(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"api", "health"}:
            raise HTTPException(status_code=404)
        try:
            requested = (frontend_dist_path / full_path).resolve()
            requested.relative_to(frontend_dist_path)
        except ValueError:
            raise HTTPException(status_code=404) from None
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(index_path, headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    # Build the Telegram bot/dispatcher up front (only when webhooks are enabled) so
    # the lifespan handler can register/tear down the webhook. Kept thin: the bot only
    # opens the Mini App (docs/spec/13 "Telegram bot & webhook").
    telegram = _build_telegram(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- startup ---
        if telegram is not None:
            await _register_telegram_webhook_on_startup(settings, telegram)
        yield
        # --- shutdown ---
        if telegram is not None:
            await telegram["bot"].session.close()

    app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
    if telegram is not None:
        app.state.telegram_bot = telegram["bot"]
        app.state.telegram_dispatcher = telegram["dispatcher"]

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        https_only=settings.app_env != "development",
        same_site="lax",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    from app.api.admin_routes import router as admin_router
    from app.api.media_routes import router as media_router
    from app.api.theory_admin_routes import router as theory_admin_router
    from app.api.assessment_admin_routes import router as assessment_admin_router
    from app.api.assessment_routes import router as assessment_router
    from app.api.theory_routes import router as theory_router

    app.include_router(admin_router)
    app.include_router(media_router)
    app.include_router(theory_router)
    app.include_router(theory_admin_router)
    app.include_router(assessment_admin_router)
    app.include_router(assessment_router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        try:
            response = await call_next(request)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            error_id = uuid4().hex[:12]
            log_exception(
                "request_unhandled_error",
                exc,
                error_id=error_id,
                path=request.url.path,
                method=request.method,
            )
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.",
                    "error_id": error_id,
                },
            )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Content-Security-Policy", CSP)
        if settings.app_env != "development":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    if telegram is not None:
        _register_webhook_route(app, settings, telegram)

    @app.get("/health")
    async def health() -> JSONResponse:
        """Railway healthcheck: 200 only when the process is up AND the DB is reachable."""
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            log_exception("healthcheck_db_unreachable", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "database": "unreachable"},
            )
        return JSONResponse(
            status_code=200, content={"status": "ok", "environment": settings.app_env}
        )

    register_frontend(app, settings.frontend_dist_path)
    return app


def _build_telegram(settings) -> dict | None:
    """Create the (thin) bot + dispatcher when webhooks are enabled, else ``None``.

    Long polling is never used in production — the webhook route feeds the dispatcher
    (docs/spec/13). Returns a small dict so the lifespan + route share one instance.
    """
    if not (settings.telegram_webhook_enabled and settings.bot_token):
        return None
    from app.bot.bootstrap import create_bot, create_dispatcher

    return {"bot": create_bot(settings.bot_token), "dispatcher": create_dispatcher()}


async def _register_telegram_webhook_on_startup(settings, telegram: dict) -> None:
    """Register the Telegram webhook + menu-button Web App URL on startup."""
    from aiogram.types import MenuButtonWebApp, WebAppInfo

    bot = telegram["bot"]
    webhook_url = f"{settings.mini_app_url.rstrip('/')}/telegram/webhook"
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="prava-bot", web_app=WebAppInfo(url=settings.mini_app_url)
        )
    )
    await bot.set_webhook(
        webhook_url,
        secret_token=settings.telegram_webhook_secret,
        allowed_updates=["message"],
        drop_pending_updates=False,
    )
    # Do NOT log the secret or the full webhook payloads (docs/spec/09 webhook/bot).
    log_event("telegram_webhook_registered", webhook_path="/telegram/webhook")


def _register_webhook_route(app: FastAPI, settings, telegram: dict) -> None:
    from aiogram.types import Update

    bot = telegram["bot"]
    dispatcher = telegram["dispatcher"]

    @app.post("/telegram/webhook", include_in_schema=False)
    async def telegram_webhook(request: Request) -> dict[str, bool]:
        # Constant-time compare of the Telegram secret header; reject spoofed requests
        # with 403. Never log the secret or the full update payload (docs/spec/09).
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
        if not hmac.compare_digest(secret, settings.telegram_webhook_secret):
            log_event("telegram_webhook_rejected", reason="bad_secret")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Telegram webhook secret"
            )
        update = Update.model_validate(await request.json(), context={"bot": bot})
        await dispatcher.feed_update(bot, update)
        return {"ok": True}


app = create_app()
