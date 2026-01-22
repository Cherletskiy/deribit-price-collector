from pydantic import Field, Json
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    # Database
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="deribit_db")
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="postgres")

    # Redis
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)

    # Deribit
    DERIBIT_API_BASE_URL: str = Field(default="https://www.deribit.com/api/v2")
    PRICE_FETCH_INTERVAL_SEC: int = Field(default=60)
    PRICE_BATCH_SIZE: int = Field(default=5)
    TICKERS: Json[list[str]] = Field(default=["btc_usd", "eth_usd"])

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    # Computed properties
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


config = Config()
