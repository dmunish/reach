from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Automatically reads from Backend/.env file.
    """
    # Supabase - required fields
    supabase_url: str
    supabase_key: str
    
    # LocationIQ - using Field with validation_alias to map LOCATION_IQ_KEY
    locationiq_api_key: str = Field(default="", validation_alias="location_iq_key")
    locationiq_base_url: str = "https://us1.locationiq.com/v1"
    
    # Matching thresholds
    fuzzy_match_threshold: float = 0.85
    prefer_lower_admin_levels: bool = True
    
    # Caching
    cache_ttl_days: int = 30
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding='utf-8',
        extra='ignore',  # Ignore extra fields in .env
        case_sensitive=False  # Allow case-insensitive matching
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings singleton.
    Settings are automatically loaded from .env file via pydantic-settings.
    """
    return Settings()  # type: ignore[call-arg]  # pydantic-settings loads from env