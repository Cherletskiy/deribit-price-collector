from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError

from app.api.endpoints import router
from app.core.db import close_db, init_db
from app.core.logging_config import setup_logger

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
