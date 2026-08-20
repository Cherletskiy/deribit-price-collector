from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import config
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


async_engine = create_async_engine(
    url=config.DATABASE_URL, echo=False, pool_size=5, max_overflow=10
)
async_session_factory = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
)


async def get_async_session():
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


sync_engine = create_engine(
    url=config.DATABASE_SYNC_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


Base = declarative_base()


async def init_db():
    logger.info("Initializing database connection")
    try:
        await ping_db()
        logger.info("Database connection OK")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def ping_db() -> None:
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db():
    logger.info("Closing database connection")
    await async_engine.dispose()
    logger.info("Database connection closed")
