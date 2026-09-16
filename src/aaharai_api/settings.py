from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="server/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 30.0
    google_oauth_client_id: str | None = None
    google_auth_required: bool = False
    food_catalog_path: Path = Path(
        "android/app/src/commonMain/composeResources/files/aaharai-ifct/data.csv"
    )
