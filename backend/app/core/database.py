from supabase import create_client, Client
from .config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self._supabase: Optional[Client] = None
    
    @property
    def supabase(self) -> Client:
        """Lazy-load Supabase client"""
        if self._supabase is None:
            try:
                self._supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                raise
        return self._supabase


    async def create_hotel(self, hotel_data: dict):
        """Create a new hotel in the database"""
        try:
            result = self.supabase.table("hotels").insert(hotel_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating hotel: {e}")
            raise

    async def get_hotel_by_amadeus_id(self, amadeus_hotel_id: str):
        """Get hotel by Amadeus hotel ID"""
        try:
            result = self.supabase.table("hotels").select("*").eq("amadeus_hotel_id", amadeus_hotel_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting hotel by Amadeus ID: {e}")
            raise


# Global database instance
db = DatabaseManager()
