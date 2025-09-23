from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging
from app.core import settings
from app.api import vapi_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="Voice Hotel Booking API",
    description="A FastAPI backend for voice-powered hotel booking through VAPI",
    version="1.0.0"
)

# Configure CORS
allowed_origins = settings.cors_origins if hasattr(settings, 'cors_origins') else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(vapi_router)

@app.get("/")
async def root():
    return {"message": "Voice Hotel Booking API is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "voice-hotel-booking"}

@app.get("/config/test")
async def test_config():
    """Test endpoint to verify configuration"""
    return {
        "environment": settings.environment,
        "webhook_url": settings.webhook_url if hasattr(settings, 'webhook_url') else "Not configured",
        "amadeus_configured": bool(settings.amadeus_api_key and settings.amadeus_api_secret),
        "supabase_configured": bool(settings.supabase_url and settings.supabase_anon_key)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
