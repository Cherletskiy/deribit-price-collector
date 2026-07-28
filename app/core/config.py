from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="deribit_db")
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="postgres")

    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)

    MARKET_DATA_PROVIDER: str = Field(default="deribit")
    DERIBIT_API_BASE_URL: str = Field(default="https://www.deribit.com/api/v2")
    DERIBIT_API_TIMEOUT_SEC: int = Field(default=10)
    PRICE_FETCH_INTERVAL_SEC: int = Field(default=60)
    PRICE_BATCH_SIZE: int = Field(default=5)
    RECONCILIATION_INTERVAL_SEC: int = Field(default=300)
    RECONCILIATION_LOOKBACK_SEC: int = Field(default=86400)
    RECONCILIATION_STALE_MULTIPLIER: int = Field(default=2)
    TICKERS: list[str] = Field(default_factory=lambda: ["btc_usd", "eth_usd"])

    LOG_LEVEL: str = Field(default="INFO")
    LOG_JSON: bool = Field(default=False)

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def supported_tickers(self) -> tuple[str, ...]:
        return tuple(self.TICKERS)

    @property
    def supported_tickers_set(self) -> frozenset[str]:
        return frozenset(self.TICKERS)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


config = Config()
