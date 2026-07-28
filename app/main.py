from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic_core import ValidationError

from app.api.endpoints import router
from app.core.db import close_db, init_db
from app.core.error_responses import build_error_response
from app.core.logging_config import setup_logger
from app.core.metrics import runtime_metrics
from app.core.request_context import request_id_context

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting application...")
    try:
        await init_db()
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

    finally:
        logger.info("Shutting down application...")
        await close_db()


app = FastAPI(
    title="Deribit Price Collector API",
    description="API to query BTC/ETH index prices collected from Deribit",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def collect_runtime_metrics(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    path = request.url.path
    runtime_metrics.on_request_start(path)
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        runtime_metrics.on_request_end(path, 500, duration_ms)
        request_id_context.reset(token)
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    runtime_metrics.on_request_end(path, response.status_code, duration_ms)
    response.headers["X-Request-ID"] = request_id
    request_id_context.reset(token)
    return response


def normalize_validation_errors(
    errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    for error in errors:
        if "ctx" in error and "error" in error["ctx"]:
            error["ctx"]["error"] = str(error["ctx"]["error"])
    return [dict(error) for error in errors]


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    normalized_errors = normalize_validation_errors(exc.errors())
    return build_error_response(
        status_code=422,
        request_id=request.state.request_id,
        error_code="validation_error",
        message="Validation failed",
        details=normalized_errors,
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    normalized_errors = normalize_validation_errors(exc.errors(include_url=False))
    return build_error_response(
        status_code=422,
        request_id=request.state.request_id,
        error_code="validation_error",
        message="Validation failed",
        details=normalized_errors,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    details = None if isinstance(detail, str) else detail
    return build_error_response(
        status_code=exc.status_code,
        request_id=request.state.request_id,
        error_code=f"http_{exc.status_code}",
        message=message,
        details=details,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error | path=%s", request.url.path)
    return build_error_response(
        status_code=500,
        request_id=request.state.request_id,
        error_code="internal_server_error",
        message="Internal server error",
    )


app.include_router(router)
