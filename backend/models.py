from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import date, datetime
from enum import Enum

class TitleEnum(str, Enum):
    MR = "MR"
    MRS = "MRS"
    MS = "MS"

class PaymentMethodEnum(str, Enum):
    CREDIT_CARD = "CREDIT_CARD"

class VendorCodeEnum(str, Enum):
    VI = "VI"  # Visa
    MC = "MC"  # Mastercard
    AX = "AX"  # American Express

class BookingStatusEnum(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

# VAPI Models
class VAPIMessage(BaseModel):
    type: str
    content: str

class VAPICall(BaseModel):
    id: str
    type: str
    phoneNumber: Optional[str] = None
    messages: List[VAPIMessage] = []

# Guest Information Models
class Guest(BaseModel):
    tid: int
    title: TitleEnum
    firstName: str
    lastName: str
    phone: str
    email: EmailStr

class TravelAgent(BaseModel):
    contact: dict

class GuestReference(BaseModel):
    guestReference: str

class RoomAssociation(BaseModel):
    guestReferences: List[GuestReference]
    hotelOfferId: str

# Payment Models
class PaymentCardInfo(BaseModel):
    vendorCode: VendorCodeEnum
    cardNumber: str
    expiryDate: str  # Format: YYYY-MM
    holderName: str

class PaymentCard(BaseModel):
    paymentCardInfo: PaymentCardInfo

class Payment(BaseModel):
    method: PaymentMethodEnum
    paymentCard: PaymentCard

# Hotel Booking Models
class HotelOrderData(BaseModel):
    type: str = "hotel-order"
    guests: List[Guest]
    travelAgent: TravelAgent
    roomAssociations: List[RoomAssociation]
    payment: Payment

class HotelOrder(BaseModel):
    data: HotelOrderData

# Database Models
class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    title: TitleEnum

class HotelCreate(BaseModel):
    amadeus_hotel_id: str
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = []

class BookingCreate(BaseModel):
    user_id: int
    hotel_id: int
    amadeus_offer_id: str
    room_type: Optional[str] = None
    price: float
    currency: str
    check_in_date: date
    check_out_date: date
    guests_count: int
    booking_status: BookingStatusEnum = BookingStatusEnum.PENDING
    amadeus_order_id: Optional[str] = None

# Voice Interaction Models
class VoiceBookingRequest(BaseModel):
    destination: str
    check_in_date: str
    check_out_date: str
    guests_count: int
    guest_info: Guest
    payment_info: Optional[Payment] = None

class HotelSearchResponse(BaseModel):
    hotels: List[dict]
    message: str

class BookingConfirmationResponse(BaseModel):
    booking_id: str
    confirmation_number: str
    message: str
    status: BookingStatusEnum
