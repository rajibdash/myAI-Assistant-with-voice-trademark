import hashlib
import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint

from app.domain import (
    Brief,
    HashApproval,
    Presentation,
    Problem,
    Source,
    SourceInput,
    canonical_hash,
)
from app.providers import ExtractiveGenerator, Generator, OpenAISelector
from app.render import PowerPointRenderer
from app.service import Service
from app.store import Store

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
Key = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[!-~]+$")
]


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    database: Path = Path(".local-data/assistant.sqlite3")
    renderer: Path = ROOT / "workers/render/dist/render.js"
    openai_key: str | None = field(default=None, repr=False)
    openai_model: str = "gpt-5.4"

    def __post_init__(self) -> None:
        if len(self.token) < 32 or any(not "!" <= char <= "~" for char in self.token):
            raise ValueError("PRESENTATION_API_TOKEN must contain at least 32 visible ASCII chars")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            token=os.environ.get("PRESENTATION_API_TOKEN", ""),
            database=Path(os.environ.get("PRESENTATION_DATABASE", ".local-data/assistant.sqlite3")),
            openai_key=os.environ.get("OPENAI_API_KEY") or None,
            openai_model=os.environ.get("PRESENTATION_OPENAI_MODEL", "gpt-5.4"),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.database)
    generators: dict[str, Generator] = {"extractive": ExtractiveGenerator()}
    if settings.openai_key:
        generators["openai"] = OpenAISelector(settings.openai_key, settings.openai_model)
    service = Service(store, generators)
    renderer = PowerPointRenderer(settings.renderer)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        store.fail_interrupted_runs()
        yield

    app = FastAPI(
        title="Owner-voice presentation foundation",
        version="0.1.0",
        description="Local evidence and PPTX increment; no voice or public deployment.",
        lifespan=lifespan,
    )
    app.state.service = service
    app.state.renderer = renderer
    bearer = HTTPBearer(auto_error=False)

    def authenticate(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        candidate = credentials.credentials if credentials else ""
        if not secrets.compare_digest(candidate.encode(), settings.token.encode()):
            raise Problem(401, "unauthorized", "Valid bearer token required")

    auth = [Depends(authenticate)]

    @app.middleware("http")
    async def metadata(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def problem_response(request: Request, problem: Problem) -> JSONResponse:
        return JSONResponse(
            status_code=problem.status,
            content={
                "code": problem.code,
                "message": problem.message,
                "request_id": request.state.request_id,
                "retryable": problem.retryable,
            },
            headers={"WWW-Authenticate": "Bearer"} if problem.status == 401 else None,
        )

    @app.exception_handler(Problem)
    async def domain_error(request: Request, error: Problem) -> JSONResponse:
        LOGGER.warning("request_failed request_id=%s code=%s", request.state.request_id, error.code)
        return problem_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _: RequestValidationError) -> JSONResponse:
        # FastAPI's default errors echo raw input, which can include private source content.
        return problem_response(
            request, Problem(422, "invalid_request", "Request validation failed")
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return problem_response(
            request, Problem(error.status_code, "http_error", "Request rejected")
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception) -> JSONResponse:
        LOGGER.error(
            "internal_error request_id=%s exception_type=%s",
            request.state.request_id,
            type(error).__name__,
        )
        response = problem_response(
            request, Problem(500, "internal_error", "Unexpected server error; see request ID")
        )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "local-single-owner"}

    @app.post("/v1/sources", dependencies=auth, response_model=Source)
    def add_source(data: SourceInput, idempotency_key: Key) -> Source:
        return service.add_source(data, idempotency_key)

    @app.get("/v1/sources/{source_id}", dependencies=auth, response_model=Source)
    def get_source(source_id: str) -> Source:
        return service.source(source_id)

    @app.post("/v1/sources/{source_id}/approve", dependencies=auth, response_model=Source)
    def approve_source(source_id: str, approval: HashApproval) -> Source:
        return service.review_source(source_id, approval)

    @app.post("/v1/sources/{source_id}/withdraw", dependencies=auth, response_model=Source)
    def withdraw_source(source_id: str) -> Source:
        return service.withdraw_source(source_id)

    @app.post("/v1/presentations", dependencies=auth, response_model=Presentation)
    def generate(brief: Brief, idempotency_key: Key) -> Presentation:
        return service.generate(brief, idempotency_key)

    @app.get("/v1/presentations/{presentation_id}", dependencies=auth, response_model=Presentation)
    def get_presentation(presentation_id: str) -> Presentation:
        return service.presentation(presentation_id)

    @app.post(
        "/v1/presentations/{presentation_id}/approve",
        dependencies=auth,
        response_model=Presentation,
    )
    def approve(presentation_id: str, approval: HashApproval) -> Presentation:
        return service.approve(presentation_id, approval)

    @app.get("/v1/presentations/{presentation_id}/pptx", dependencies=auth)
    def powerpoint(presentation_id: str) -> Response:
        deck = service.approved_deck(presentation_id)
        artifact = renderer.render(deck)
        artifact_hash = hashlib.sha256(artifact).hexdigest()
        service.record_export(presentation_id, canonical_hash(deck), artifact_hash)
        return Response(
            artifact,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{presentation_id}.pptx"',
                "X-Artifact-SHA256": artifact_hash,
                "X-Deck-SHA256": canonical_hash(deck),
            },
        )

    @app.get("/v1/audit", dependencies=auth)
    def audit() -> list[dict[str, object]]:
        return store.events()

    return app


def run() -> None:
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=8000, workers=1)
