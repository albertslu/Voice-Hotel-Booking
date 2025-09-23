"""
AZDS Hotel API Service
Simple service to call AZDS hotel booking API
"""
import httpx
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AZDSHotelClient:
    def __init__(self):
        self.base_url = "https://newbooking.azds.com/api/hotel"
    
    async def get_hotel_rates(
        self,
        hotel_code: str,
        check_in_date: str,  # MM/DD/YYYY format
        check_out_date: str,  # MM/DD/YYYY format
        adults: int,
        children: int = 0,
        lang: str = "en"
    ) -> Dict[str, Any]:
        """
        Get hotel rates from AZDS API
        
        Args:
            hotel_code: Hotel code (e.g., 'proper-sf')
            check_in_date: Check-in date in MM/DD/YYYY format
            check_out_date: Check-out date in MM/DD/YYYY format
            adults: Number of adults
            children: Number of children
            lang: Language code
            
        Returns:
            Raw API response from AZDS
        """
        try:
            url = f"{self.base_url}/{hotel_code}/rates"
            params = {
                "from": check_in_date,
                "to": check_out_date,
                "adults": adults,
                "children": children,
                "lang": lang
            }
            
            logger.info(f"Calling AZDS API: {url} with params: {params}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"AZDS API returned {len(data.get('rates', []))} rates")
                
                return data
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling AZDS API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling AZDS API: {e}")
            raise

# Global client instance
azds_client = AZDSHotelClient()
