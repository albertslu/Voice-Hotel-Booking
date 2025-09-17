from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    supabase_url: str
    supabase_key: str
    supabase_service_key: Optional[str] = None
    database_url: Optional[str] = None
    
    # FastAPI
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Environment
    environment: str = "development"
    
    # VAPI
    vapi_api_key: Optional[str] = None
    vapi_phone_number_id: Optional[str] = None
    
    # Hotel APIs
    booking_api_key: Optional[str] = None
    expedia_api_key: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
