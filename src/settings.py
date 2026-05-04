import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_env: str
    # OpenAI
    openai_api_key: str
    openai_model: str
    openai_fast_model: str
    # Groq
    groq_api_key: str
    groq_model: str
    # Gemini
    gemini_api_key: str
    gemini_model: str
    # Rate Limiting
    rate_limit_openai: int
    rate_limit_groq: int
    rate_limit_gemini: int
    # Adaptive Mode
    adaptive_mode: bool
    model_timeout: int
    # Other
    power_automate_email_url: str
    app_db_path: str
    vector_db_path: str
    jwt_secret: str


def get_config() -> AppConfig:
    return AppConfig(
        app_name=os.getenv("APP_NAME", "Enterprise Multi-Agent Copilot"),
        app_env=os.getenv("APP_ENV", "dev"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        openai_fast_model=os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        rate_limit_openai=int(os.getenv("RATE_LIMIT_OPENAI", "60")),
        rate_limit_groq=int(os.getenv("RATE_LIMIT_GROQ", "30")),
        rate_limit_gemini=int(os.getenv("RATE_LIMIT_GEMINI", "40")),
        adaptive_mode=os.getenv("ADAPTIVE_MODE", "true").lower() == "true",
        model_timeout=int(os.getenv("MODEL_TIMEOUT", "30")),
        power_automate_email_url=os.getenv("POWER_AUTOMATE_EMAIL_URL", ""),
        app_db_path=os.getenv("APP_DB_PATH", "./data/app.db"),
        vector_db_path=os.getenv("VECTOR_DB_PATH", os.getenv("VECTOR_STORE_PATH", "./data/vector_store")),
        jwt_secret=os.getenv("JWT_SECRET", "replace_me"),
    )
