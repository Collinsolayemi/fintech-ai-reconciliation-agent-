from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration and financial guardrail thresholds."""

    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    ledger_api_url: str = "http://localhost:8080/api/v1"
    ledger_api_token: str = ""
    database_url: str = "postgresql://fintech_user:fintech_password@localhost:5432/fintech_db"

    # Guardrail thresholds
    auto_resolve_max_amount: float = 100.00
    min_confidence_threshold: float = 0.90

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
