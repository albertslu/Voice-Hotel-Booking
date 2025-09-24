from pydantic_settings import BaseSettings
from typing import Optional, List
import json


class Settings(BaseSettings):
    # Environment
    environment: str = "development"
    debug: bool = True
    port: int = 8000
    secret_key: str
    
    # FastAPI & CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000", "https://guestara.ai"]
    allowed_hosts: List[str] = ["localhost", "127.0.0.1", "api.guestara.ai"]
    
    # Domain Configuration
    webhook_url: str = "https://api.guestara.ai/webhook/vapi"
    
    # VAPI Configuration
    vapi_api_key: Optional[str] = None
    vapi_public_key: Optional[str] = None
    vapi_webhook_secret: Optional[str] = None
    
    
    # Amadeus Configuration (legacy - keeping for reference)
    amadeus_api_key: Optional[str] = None
    amadeus_api_secret: Optional[str] = None
    amadeus_base_url: Optional[str] = "https://api.amadeus.com/v1"
    
    # Google Travel Partner Prices API Configuration
    google_travel_partner_api_key: Optional[str] = None
    google_travel_partner_base_url: Optional[str] = "https://travelpartner.googleapis.com/v3"
    
    # SerpAPI Configuration
    serpapi_key: Optional[str] = None
    serpapi_base_url: Optional[str] = "https://serpapi.com/search"
    
    # MakCorps API Configuration
    makcorps_api_key: Optional[str] = None
    
    # Supabase Configuration
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: Optional[str] = None
    
    # Redis Configuration
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_url: Optional[str] = None  # Alternative to individual settings
    
    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = "../.env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name in ['cors_origins', 'allowed_hosts']:
                # Parse JSON-like strings for lists
                try:
                    return json.loads(raw_val)
                except json.JSONDecodeError:
                    # Fallback to comma-separated values
                    return [item.strip() for item in raw_val.split(',')]
            return cls.json_loads(raw_val)


settings = Settings()
