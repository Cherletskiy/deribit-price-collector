from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.endpoints import router
from app.core.logging_config import setup_logger
from app.core.db import init_db, close_db


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

app.include_router(router)
