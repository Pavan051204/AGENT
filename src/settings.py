import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_env: str
    # Gemini
    gemini_api_key: str
    gemini_model: str
    # Groq
    groq_api_key: str
    groq_model: str
    # Rate Limiting
    rate_limit_gemini: int
    # Other
    power_automate_email_url: str
    app_db_path: str
    jwt_secret: str
    pdf_docs_path: str


def get_config() -> AppConfig:
    return AppConfig(
        app_name=os.getenv("APP_NAME", "Novi Pilot"),
        app_env=os.getenv("APP_ENV", "dev"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "auto"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        rate_limit_gemini=int(os.getenv("RATE_LIMIT_GEMINI", "60")),
        power_automate_email_url=os.getenv("POWER_AUTOMATE_EMAIL_URL", ""),
        app_db_path=os.getenv("APP_DB_PATH", "./data/app.db"),
        jwt_secret=os.getenv("JWT_SECRET", "replace_me"),
        pdf_docs_path=os.getenv("PDF_DOCS_PATH", "./docs"),
    )
