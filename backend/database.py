from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_anon_key)

class DatabaseManager:
    def __init__(self):
        self.supabase = supabase

    async def create_user(self, user_data: dict):
        """Create a new user in the database"""
        try:
            result = self.supabase.table("users").insert(user_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_email(self, email: str):
        """Get user by email"""
        try:
            result = self.supabase.table("users").select("*").eq("email", email).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            raise

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

    async def create_booking(self, booking_data: dict):
        """Create a new booking in the database"""
        try:
            result = self.supabase.table("bookings").insert(booking_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            raise

    async def get_booking_by_id(self, booking_id: int):
        """Get booking by ID with user and hotel information"""
        try:
            result = self.supabase.table("bookings").select("""
                *,
                users(*),
                hotels(*)
            """).eq("id", booking_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting booking by ID: {e}")
            raise

    async def update_booking_status(self, booking_id: int, status: str, amadeus_order_id: str = None):
        """Update booking status and Amadeus order ID"""
        try:
            update_data = {"booking_status": status}
            if amadeus_order_id:
                update_data["amadeus_order_id"] = amadeus_order_id
            
            result = self.supabase.table("bookings").update(update_data).eq("id", booking_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            raise

# Global database instance
db = DatabaseManager()
