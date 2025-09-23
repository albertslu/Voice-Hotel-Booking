from pydantic import BaseModel
from typing import List, Optional

# VAPI Models
class VAPIMessage(BaseModel):
    type: str
    content: str

class VAPICall(BaseModel):
    id: str
    type: str
    phoneNumber: Optional[str] = None
    messages: List[VAPIMessage] = []

# Simplified models for voice-based hotel search and checkout

# Database Models

class HotelCreate(BaseModel):
    amadeus_hotel_id: str
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = []

# Simple models for voice-based hotel search and checkout URL generation
class HotelSearchResponse(BaseModel):
    hotels: List[dict]
    message: str

class CheckoutResponse(BaseModel):
    checkout_url: str
    guest_name: str
    guest_email: str
    message: str
