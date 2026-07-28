from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError

from app.api.endpoints import router
from app.core.db import close_db, init_db
from app.core.logging_config import setup_logger
from app.core.metrics import runtime_metrics

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
    path = request.url.path
    runtime_metrics.on_request_start(path)
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        runtime_metrics.on_request_end(path, 500, duration_ms)
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    runtime_metrics.on_request_end(path, response.status_code, duration_ms)
    return response


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    errors = exc.errors(include_url=False)
    for error in errors:
        if "ctx" in error and "error" in error["ctx"]:
            error["ctx"]["error"] = str(error["ctx"]["error"])
    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


app.include_router(router)
