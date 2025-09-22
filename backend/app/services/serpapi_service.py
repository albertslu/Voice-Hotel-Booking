"""
SerpAPI Hotel Search Service

This service uses SerpAPI to search Google Hotels for hotel availability and pricing.
"""

import os
import httpx
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SerpAPIHotelClient:
    """Client for searching hotels using SerpAPI Google Hotels engine"""
    
    def __init__(self, api_key: str = None):
        """Initialize SerpAPI client
        
        Args:
            api_key: SerpAPI key. If not provided, will try to load from config/env
        """
        self.base_url = "https://serpapi.com/search"
        
        if api_key:
            self.api_key = api_key
        else:
            # Try to load from config
            self.api_key = None
            try:
                from app.core.config import settings
                self.api_key = settings.serpapi_key
            except (ImportError, AttributeError):
                pass
            
            # Fallback to environment variable
            if not self.api_key:
                self.api_key = os.getenv('SERPAPI_KEY')
        
        if not self.api_key:
            raise ValueError("SerpAPI key not found. Please set SERPAPI_KEY in .env file")
    
    async def search_hotels(
        self,
        query: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        children: int = 0,
        currency: str = "USD",
        location: Optional[str] = None,
        gl: str = "us",
        hl: str = "en"
    ) -> Dict:
        """Search for hotels using Google Hotels
        
        Args:
            query: Hotel name or search query (e.g., "LUMA Hotel San Francisco")
            check_in_date: Check-in date (YYYY-MM-DD format)
            check_out_date: Check-out date (YYYY-MM-DD format)
            adults: Number of adults
            children: Number of children
            currency: Currency code (e.g., USD, EUR)
            location: Optional location/city to search in
            gl: Country code for Google search (default: us)
            hl: Language code (default: en)
            
        Returns:
            Dict containing search results with hotels and pricing
        """
        params = {
            "engine": "google_hotels",
            "q": query,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "adults": adults,
            "currency": currency,
            "gl": gl,
            "hl": hl,
            "api_key": self.api_key
        }
        
        if children > 0:
            params["children"] = children
            
        if location:
            params["location"] = location
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"SerpAPI search successful for '{query}'")
                return data
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error during SerpAPI search: {e}")
                raise
            except Exception as e:
                logger.error(f"Error during SerpAPI search: {e}")
                raise
    
    def format_hotel_results(self, search_data: Dict) -> List[Dict]:
        """Format SerpAPI results into a clean structure
        
        Args:
            search_data: Raw SerpAPI response
            
        Returns:
            List of formatted hotel dictionaries
        """
        hotels = []
        
        if "properties" not in search_data:
            return hotels
        
        for property_data in search_data["properties"]:
            hotel = {
                "name": property_data.get("name", "Unknown Hotel"),
                "type": property_data.get("type", "Hotel"),
                "link": property_data.get("link"),
                "rating": property_data.get("overall_rating"),
                "reviews_count": property_data.get("reviews"),
                "description": property_data.get("description"),
                "amenities": property_data.get("amenities", []),
                "images": property_data.get("images", []),
                "location": {
                    "address": property_data.get("address"),
                    "neighborhood": property_data.get("neighborhood"),
                    "gps_coordinates": property_data.get("gps_coordinates", {})
                }
            }
            
            # Extract pricing information
            if "rate_per_night" in property_data:
                rate = property_data["rate_per_night"]
                hotel["pricing"] = {
                    "lowest_rate": rate.get("lowest"),
                    "highest_rate": rate.get("highest"),
                    "currency": search_data.get("search_parameters", {}).get("currency", "USD")
                }
            
            # Extract booking options
            if "prices" in property_data:
                hotel["booking_options"] = []
                for price_option in property_data["prices"]:
                    option = {
                        "source": price_option.get("source"),
                        "rate_per_night": price_option.get("rate_per_night", {}).get("lowest"),
                        "total_price": price_option.get("total_price"),
                        "link": price_option.get("link")
                    }
                    hotel["booking_options"].append(option)
            
            hotels.append(hotel)
        
        return hotels
    
    async def search_hotel_by_name(
        self,
        hotel_name: str,
        city: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        currency: str = "USD"
    ) -> Optional[Dict]:
        """Search for a specific hotel by name and city
        
        Args:
            hotel_name: Name of the hotel
            city: City where the hotel is located
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            adults: Number of adults
            currency: Currency code
            
        Returns:
            Dict with hotel information if found, None otherwise
        """
        query = f"{hotel_name} {city}"
        results = await self.search_hotels(
            query=query,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            adults=adults,
            currency=currency
        )
        
        formatted_hotels = self.format_hotel_results(results)
        
        # Try to find exact match
        for hotel in formatted_hotels:
            if hotel_name.lower() in hotel["name"].lower():
                return hotel
        
        # Return first result if no exact match
        return formatted_hotels[0] if formatted_hotels else None


# Example usage
async def main():
    """Example usage of SerpAPI hotel search"""
    try:
        client = SerpAPIHotelClient()
        
        # Search for LUMA Hotel
        print("🔍 Searching for LUMA Hotel San Francisco...")
        results = await client.search_hotel_by_name(
            hotel_name="LUMA Hotel",
            city="San Francisco",
            check_in_date="2025-11-11",
            check_out_date="2025-11-13",
            adults=2,
            currency="USD"
        )
        
        if results:
            print(f"\n✅ Found: {results['name']}")
            print(f"⭐ Rating: {results['rating']} ({results['reviews_count']} reviews)")
            
            if results.get('pricing'):
                print(f"💰 Lowest Rate: ${results['pricing']['lowest_rate']} per night")
            
            if results.get('booking_options'):
                print(f"\n📋 Available on {len(results['booking_options'])} booking sites:")
                for i, option in enumerate(results['booking_options'][:5], 1):
                    print(f"  {i}. {option['source']} - ${option['rate_per_night']}/night")
        else:
            print("❌ Hotel not found")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
