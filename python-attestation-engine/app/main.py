"""Attestation report service: a standalone page at /attestation behind its own login.

The site login (one user from the settings) opens the page; the page asks for the RITM
portal login and password and builds the reports from the portal's data. The RITM
password lives in memory for the length of one job, or, when the user asks to remember
it, in the vault encrypted with a key derived from the site password.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from .jobs import RESULT_FILES, JobRejected, JobRunner, Pipeline
from .logging_config import configure_logging
from .security import LoginLimiter, Session, SessionStore, Vault, derive_vault_key, verify_password

configure_logging("python-attestation-engine")
logger = logging.getLogger(__name__)

BASE = "/attestation"
COOKIE = "attestation_session"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_FILES = {
    "app.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
}
LOGIN_ERRORS = {
    "wrong": "Неверный логин или пароль.",
    "limit": "Слишком много неудачных попыток. Подождите 15 минут.",
    "setup": "Вход не настроен: на сервере не задан ATTESTATION_PASSWORD_HASH.",
    "expired": "Сеанс завершён. Войдите снова.",
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@dataclass(frozen=True)
class Settings:
    username: str
    password_hash: str
    cookie_secure: bool
    data_dir: Path
    files_ttl: int
    session_idle: int
    session_absolute: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            username=os.getenv("ATTESTATION_USERNAME", "admin"),
            password_hash=os.getenv("ATTESTATION_PASSWORD_HASH", ""),
            cookie_secure=os.getenv("ATTESTATION_COOKIE_SECURE", "1") != "0",
            data_dir=Path(os.getenv("ATTESTATION_DATA_DIR", "/app/data")),
            files_ttl=int(os.getenv("ATTESTATION_FILES_TTL", "1800")),
            session_idle=int(os.getenv("ATTESTATION_SESSION_IDLE", "1800")),
            session_absolute=int(os.getenv("ATTESTATION_SESSION_ABSOLUTE", "28800")),
        )


class JobRequest(BaseModel):
    login: str = Field("", max_length=200)
    password: str = Field("", max_length=200)
    use_saved: bool = False
    remember: bool = False
    year: int = Field(..., ge=2015, le=2100)
    odd_semester: bool
    attestation: int = Field(..., ge=1, le=3)
    levels: list[str] = Field(..., min_length=1, max_length=2)


def ritm_pipeline(login, password, year, odd, attestation, levels, workdir, log) -> Path:
    """RITM portal -> XML -> analysis -> reports; the modules come from reports/ on PYTHONPATH."""
    import make_report
    import ritm_fetch

    session = ritm_fetch.login(login, password)
    period = ritm_fetch.AttestationPeriod(year, odd, attestation)
    log(period.label)
    return make_report.build_all(session, period, workdir, levels, log=log)


def current_defaults(today: Optional[datetime] = None) -> tuple[int, bool]:
    """Study year and semester by date: September-January odd, February-August even."""
    today = today or datetime.now()
    if today.month >= 9:
        return today.year, True
    if today.month == 1:
        return today.year - 1, True
    return today.year - 1, False


def client_address(request: Request) -> str:
    # The last address is the one added by our own proxy; earlier ones come from the client
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def create_app(settings: Settings, pipeline: Pipeline = ritm_pipeline) -> FastAPI:
    sessions = SessionStore(settings.session_idle, settings.session_absolute)
    limiter = LoginLimiter(per_client=5, total=20, window_seconds=15 * 60)
    vault = Vault(settings.data_dir)
    runner = JobRunner(pipeline, settings.files_ttl)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runner.start_cleaner()
        if not settings.password_hash:
            logger.warning("ATTESTATION_PASSWORD_HASH is not set: nobody can log in")
        yield

    app = FastAPI(
        title="Attestation Report Service",
        description="Отчёты об аттестации групп кафедры по данным портала РИТМ",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.sessions, app.state.limiter, app.state.vault, app.state.runner = sessions, limiter, vault, runner

    @app.middleware("http")
    async def protect(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        logger.info(
            "%s %s -> %s in %.3fs",
            request.method,
            request.url.path,
            response.status_code,
            time.monotonic() - started,
        )
        return response

    def current_session(request: Request) -> Optional[Session]:
        return sessions.get(request.cookies.get(COOKIE))

    def require_session(request: Request, check_csrf: bool = False) -> Session:
        session = current_session(request)
        if session is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сеанс завершён. Войдите снова.")
        # bytes: compare_digest refuses non-ASCII strings with TypeError, which would be a 500
        if check_csrf and not hmac.compare_digest(
            request.headers.get("x-csrf-token", "").encode("utf-8"), session.csrf.encode("utf-8")
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Запрос отклонён: устаревшая страница. Обновите её.")
        return session

    def page(name: str, error: str = "") -> HTMLResponse:
        html = (STATIC_DIR / name).read_text(encoding="utf-8")
        message = f'<p class="alert" role="alert">{escape(error)}</p>' if error else ""
        return HTMLResponse(html.replace("<!--error-->", message))

    @app.get("/health")
    async def health():
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

    @app.get(BASE)
    async def index(request: Request, error: str = ""):
        if current_session(request) is not None:
            return page("index.html")
        return page("login.html", LOGIN_ERRORS.get(error, ""))

    @app.get(BASE + "/static/{name}")
    async def static(name: str):
        if name not in STATIC_FILES:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет такого файла")
        return FileResponse(STATIC_DIR / name, media_type=STATIC_FILES[name])

    @app.post(BASE + "/login")
    def login(request: Request, username: str = Form(""), password: str = Form("")):
        client = client_address(request)
        if not settings.password_hash:
            return RedirectResponse(BASE + "?error=setup", status.HTTP_303_SEE_OTHER)
        if not limiter.allowed(client):
            logger.warning("Login refused: too many failures")
            return RedirectResponse(BASE + "?error=limit", status.HTTP_303_SEE_OTHER)
        # Both checks always run, so the response time does not tell which one failed
        name_ok = hmac.compare_digest(username.encode("utf-8"), settings.username.encode("utf-8"))
        password_ok = verify_password(password, settings.password_hash)
        if not (name_ok and password_ok):
            limiter.failed(client)
            logger.warning("Login failed")
            return RedirectResponse(BASE + "?error=wrong", status.HTTP_303_SEE_OTHER)

        limiter.succeeded(client)
        session = sessions.create(derive_vault_key(password, vault.salt()))
        logger.info("Login succeeded")
        response = RedirectResponse(BASE, status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            COOKIE,
            session.token,
            max_age=settings.session_absolute,
            path=BASE,
            secure=settings.cookie_secure,
            httponly=True,
            samesite="strict",
        )
        return response

    @app.post(BASE + "/logout")
    async def logout(request: Request):
        session = require_session(request, check_csrf=True)
        sessions.drop(session.token)
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(COOKIE, path=BASE, secure=settings.cookie_secure, httponly=True, samesite="strict")
        return response

    @app.get(BASE + "/api/me")
    async def me(request: Request):
        session = require_session(request)
        year, odd = current_defaults()
        return {
            "csrf": session.csrf,
            "remembered_login": vault.stored_login(),
            "year": year,
            "odd_semester": odd,
        }

    @app.post(BASE + "/api/jobs", status_code=status.HTTP_202_ACCEPTED)
    def start_job(request: Request, body: JobRequest):
        session = require_session(request, check_csrf=True)
        levels = [level for level in ("б", "м") if level in body.levels]
        if not levels:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выберите бакалавриат или магистратуру.")
        if body.use_saved:
            stored = vault.load(session.vault_key)
            if stored is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Сохранённый пароль РИТМ недоступен. Введите логин и пароль портала.",
                )
            ritm_login, ritm_password = stored
        else:
            ritm_login, ritm_password = body.login.strip(), body.password
            if not ritm_login or not ritm_password:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Введите логин и пароль портала РИТМ.")
            if body.remember:
                vault.save(session.vault_key, ritm_login, ritm_password)
                logger.info("RITM credentials saved to the vault")
        try:
            job = runner.start(
                session.token, ritm_login, ritm_password, body.year, body.odd_semester, body.attestation, levels
            )
        except JobRejected as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
        return job.public()

    @app.get(BASE + "/api/jobs/{job_id}")
    async def job_status(request: Request, job_id: str):
        session = require_session(request)
        job = runner.get(job_id, session.token)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена или её файлы уже удалены.")
        return job.public()

    @app.get(BASE + "/api/jobs/{job_id}/files/{key}")
    async def job_file(request: Request, job_id: str, key: str):
        session = require_session(request)
        job = runner.get(job_id, session.token)
        if job is None or key not in job.files or not job.files[key].exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не найден или уже удалён.")
        path = job.files[key]
        return FileResponse(path, filename=path.name)

    @app.post(BASE + "/api/vault/forget", status_code=status.HTTP_204_NO_CONTENT)
    async def forget(request: Request):
        require_session(request, check_csrf=True)
        vault.forget()
        logger.info("RITM credentials removed from the vault")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.exception_handler(HTTPException)
    async def json_error(request: Request, error: HTTPException):
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    return app


app = create_app(Settings.from_env())
