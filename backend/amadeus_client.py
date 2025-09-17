from amadeus import Client, ResponseError
from config import settings
import logging
from typing import List, Dict, Optional
from models import HotelOrder

logger = logging.getLogger(__name__)

class AmadeusHotelClient:
    def __init__(self):
        self.amadeus = Client(
            client_id=settings.amadeus_api_key,
            client_secret=settings.amadeus_api_secret
        )

    async def search_hotels(self, city_code: str, check_in_date: str, check_out_date: str, adults: int = 1) -> List[Dict]:
        """
        Search for hotels using Amadeus Hotel Search API
        
        Args:
            city_code: IATA city code (e.g., 'NYC', 'LON', 'PAR')
            check_in_date: Check-in date in YYYY-MM-DD format
            check_out_date: Check-out date in YYYY-MM-DD format
            adults: Number of adults
        
        Returns:
            List of hotel offers
        """
        try:
            # First, get hotels by city
            response = self.amadeus.reference_data.locations.hotels.by_city.get(
                cityCode=city_code
            )
            
            if not response.data:
                logger.warning(f"No hotels found for city code: {city_code}")
                return []

            # Get hotel IDs (limit to first 10 for demo)
            hotel_ids = [hotel['hotelId'] for hotel in response.data[:10]]
            hotel_ids_str = ','.join(hotel_ids)

            # Search for offers
            offers_response = self.amadeus.shopping.hotel_offers.get(
                hotelIds=hotel_ids_str,
                checkInDate=check_in_date,
                checkOutDate=check_out_date,
                adults=adults
            )

            return offers_response.data if offers_response.data else []

        except ResponseError as error:
            logger.error(f"Amadeus API error in search_hotels: {error}")
            raise Exception(f"Hotel search failed: {error}")
        except Exception as e:
            logger.error(f"Unexpected error in search_hotels: {e}")
            raise

    async def get_hotel_offer_details(self, offer_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific hotel offer
        
        Args:
            offer_id: The offer ID from hotel search results
            
        Returns:
            Detailed offer information
        """
        try:
            response = self.amadeus.shopping.hotel_offer(offer_id).get()
            return response.data if response.data else None
        except ResponseError as error:
            logger.error(f"Amadeus API error in get_hotel_offer_details: {error}")
            raise Exception(f"Failed to get offer details: {error}")
        except Exception as e:
            logger.error(f"Unexpected error in get_hotel_offer_details: {e}")
            raise

    async def create_hotel_booking(self, hotel_order: HotelOrder) -> Dict:
        """
        Create a hotel booking using Amadeus Hotel Booking API
        
        Args:
            hotel_order: HotelOrder object with booking details
            
        Returns:
            Booking confirmation details
        """
        try:
            # Convert Pydantic model to dict for API call
            booking_data = hotel_order.dict()
            
            response = self.amadeus.booking.hotel_orders.post(booking_data)
            
            if response.data:
                logger.info(f"Hotel booking created successfully: {response.data}")
                return response.data
            else:
                logger.error("No data returned from booking API")
                raise Exception("Booking failed - no data returned")

        except ResponseError as error:
            logger.error(f"Amadeus API error in create_hotel_booking: {error}")
            raise Exception(f"Hotel booking failed: {error}")
        except Exception as e:
            logger.error(f"Unexpected error in create_hotel_booking: {e}")
            raise

    async def get_city_code(self, city_name: str) -> Optional[str]:
        """
        Get IATA city code from city name
        
        Args:
            city_name: Name of the city
            
        Returns:
            IATA city code if found
        """
        try:
            response = self.amadeus.reference_data.locations.get(
                keyword=city_name,
                subType='CITY'
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0]['iataCode']
            else:
                logger.warning(f"No city code found for: {city_name}")
                return None
                
        except ResponseError as error:
            logger.error(f"Amadeus API error in get_city_code: {error}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_city_code: {e}")
            return None

# Global Amadeus client instance
amadeus_client = AmadeusHotelClient()
