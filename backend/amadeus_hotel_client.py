import httpx
import asyncio
from typing import List, Dict, Optional
import logging
import os

logger = logging.getLogger(__name__)

class AmadeusHotelClient:
    def __init__(self, client_id: str = None, client_secret: str = None):
        """
        Initialize Amadeus Hotel Client
        
        Args:
            client_id: Amadeus API client ID (if None, will try to get from config or env)
            client_secret: Amadeus API client secret (if None, will try to get from config or env)
        """
        self.base_url = "https://api.amadeus.com/v1"
        
        # Try to get credentials from parameters, config, or environment
        if client_id and client_secret:
            self.client_id = client_id
            self.client_secret = client_secret
        else:
            try:
                from config import settings
                self.client_id = settings.amadeus_api_key
                self.client_secret = settings.amadeus_api_secret
            except ImportError:
                # Fallback to environment variables
                self.client_id = os.getenv('AMADEUS_API_KEY')
                self.client_secret = os.getenv('AMADEUS_API_SECRET')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Amadeus API credentials not found. Please provide client_id and client_secret or set environment variables.")
        
        self.access_token = None
        self.token_expires_at = None
    
    async def _get_access_token(self) -> str:
        """Get or refresh access token"""
        import time
        
        # Check if we have a valid token
        if self.access_token and self.token_expires_at and time.time() < self.token_expires_at:
            return self.access_token
        
        # Get new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/security/oauth2/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                self.token_expires_at = time.time() + token_data["expires_in"] - 60  # 60s buffer
                return self.access_token
            else:
                raise Exception(f"Failed to get access token: {response.text}")
    
    async def search_hotel_by_id(self, hotel_id: str) -> Optional[Dict]:
        """Search for a specific hotel by its Amadeus ID"""
        token = await self._get_access_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/reference-data/locations/hotels/by-hotels",
                headers={"Authorization": f"Bearer {token}"},
                params={"hotelIds": hotel_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [{}])[0] if data.get("data") else None
            else:
                logger.error(f"Hotel search failed: {response.text}")
                return None
    
    async def search_hotels_by_location(
        self, 
        location: str, 
        radius: int = 5, 
        radius_unit: str = "KM",
        hotel_source: str = "ALL"
    ) -> List[Dict]:
        """Search for hotels by location (city, coordinates, etc.)"""
        token = await self._get_access_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/reference-data/locations/hotels/by-city",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "cityCode": location,
                    "radius": radius,
                    "radiusUnit": radius_unit,
                    "hotelSource": hotel_source
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                logger.error(f"Hotel location search failed: {response.text}")
                return []
    
    async def get_hotel_offers(
        self, 
        hotel_id: str, 
        check_in: str, 
        check_out: str, 
        adults: int = 2,
        rooms: int = 1,
        currency: str = "USD",
        best_rate_only: bool = False,
        country_of_residence: str = None,
        price_range: str = None,
        board_type: str = None
    ) -> Dict:
        """Get hotel offers for a specific hotel"""
        token = await self._get_access_token()
        
        # Build parameters dynamically
        params = {
            "hotelIds": hotel_id,
            "checkInDate": check_in,
            "checkOutDate": check_out,
            "adults": adults,
            "roomQuantity": rooms,
            "currency": currency,
            "bestRateOnly": str(best_rate_only).lower()
        }
        
        # Add optional parameters if provided
        if country_of_residence:
            params["countryOfResidence"] = country_of_residence
        if price_range:
            params["priceRange"] = price_range
        if board_type:
            params["boardType"] = board_type
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.amadeus.com/v3/shopping/hotel-offers",
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Hotel offers search failed: {response.text}")
                return {"data": []}
    
    def format_hotel_offers(self, offers_data: Dict) -> List[Dict]:
        """Format hotel offers data for easy consumption"""
        if not offers_data.get("data"):
            return []
        
        hotel_data = offers_data["data"][0]
        hotel_info = hotel_data["hotel"]
        offers = hotel_data.get("offers", [])
        
        formatted_offers = []
        for offer in offers:
            room = offer.get("room", {})
            price = offer.get("price", {})
            type_est = room.get("typeEstimated", {})
            
            formatted_offer = {
                "hotel_name": hotel_info.get("name"),
                "hotel_id": hotel_info.get("hotelId"),
                "offer_id": offer.get("id"),
                "room_type": type_est.get("category", "Unknown"),
                "room_code": room.get("type", "Unknown"),
                "beds": type_est.get("beds", "Unknown"),
                "bed_type": type_est.get("bedType", "Unknown"),
                "rate_code": offer.get("rateCode", "Unknown"),
                "total_price": price.get("total"),
                "currency": price.get("currency"),
                "avg_per_night": price.get("variations", {}).get("average", {}).get("total"),
                "description": room.get("description", {}).get("text", ""),
                "check_in": offer.get("checkInDate"),
                "check_out": offer.get("checkOutDate"),
                "cancellation_deadline": None,
                "refundable": False
            }
            
            # Extract cancellation info
            policies = offer.get("policies", {})
            if "cancellations" in policies and policies["cancellations"]:
                formatted_offer["cancellation_deadline"] = policies["cancellations"][0].get("deadline")
            
            if "refundable" in policies:
                formatted_offer["refundable"] = policies["refundable"].get("cancellationRefund") == "REFUNDABLE_UP_TO_DEADLINE"
            
            formatted_offers.append(formatted_offer)
        
        return formatted_offers

# Example usage:
# client = AmadeusHotelClient()
# or with explicit credentials:
# client = AmadeusHotelClient(client_id="your_id", client_secret="your_secret")
