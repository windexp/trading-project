from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Trading Bot"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "secret"
    
    # Database
    DATABASE_URL: str = "sqlite:///./trading.db"
    
    
    ACCOUNTS: str = "[]" # JSON string of list of dicts: [{"account_no": "...", "app_key": "...", "app_secret": "..."}]
    # KIS API
    KIS_BASE_URL: str = "https://openapi.koreainvestment.com:9443"
    
    # Discord
    DISCORD_WEBHOOK_URL: str | None = None
    
    # Gemini API
    GEMINI_API_KEY: str | None = None
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
