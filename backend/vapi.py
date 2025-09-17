from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any, Optional
from models import Guest, Payment, HotelOrder, HotelOrderData, TravelAgent, RoomAssociation, GuestReference
from amadeus_client import amadeus_client
from database import db
from datetime import datetime, date
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["VAPI Webhooks"])

@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    Main VAPI webhook endpoint for handling function calls
    """
    try:
        payload = await request.json()
        logger.info(f"Received VAPI webhook: {payload}")
        
        # Extract message information
        message = payload.get("message", {})
        message_type = message.get("type")
        
        # Only handle function calls - VAPI handles conversation flow
        if message_type == "tool-calls":
            return await handle_function_call(payload)
        else:
            # For other message types, just acknowledge
            logger.info(f"Received message type: {message_type}")
            return JSONResponse({"status": "received"})
            
    except Exception as e:
        logger.error(f"Error processing VAPI webhook: {e}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)

async def handle_function_call(payload: Dict[Any, Any]):
    """Handle function calls from VAPI"""
    try:
        message = payload.get("message", {})
        message_type = message.get("type")
        
        # Handle tool-calls format
        tool_calls = message.get("toolCalls", [])
        if not tool_calls:
            logger.warning("No tool calls found in tool-calls message")
            return JSONResponse({"error": "No tool calls found"}, status_code=400)
        
        # Process the first tool call
        tool_call = tool_calls[0]
        function_info = tool_call.get("function", {})
        function_name = function_info.get("name")
        parameters = function_info.get("arguments", {})
        
        logger.info(f"Function call: {function_name} with parameters: {parameters}")
        logger.info(f"Function name type: {type(function_name)}, repr: {repr(function_name)}")
        logger.info("About to check function_name == 'search_hotels'")
        
        if function_name == "search_hotels":
            logger.info("Matched search_hotels function")
            logger.info("About to call search_hotels_tool")
            result = await search_hotels_tool(parameters)
            logger.info(f"search_hotels_tool returned: {type(result)}")
            return result
        elif function_name == "book_hotel":
            # Pass the full payload to get call data (phone number)
            return await book_hotel_tool(parameters, payload.get("call", {}))
        else:
            logger.warning(f"Unknown function call: {function_name}")
            return JSONResponse({
                "error": f"Unknown function: {function_name}"
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"Error handling function call: {e}")
        return JSONResponse({
            "error": "Failed to process function call",
            "details": str(e)
        }, status_code=500)

async def search_hotels_tool(parameters: Dict[str, Any]) -> JSONResponse:
    """
    VAPI Tool: Search for hotels using Amadeus API
    
    Expected parameters from VAPI:
    - destination: string (city name)
    - check_in_date: string (YYYY-MM-DD)
    - check_out_date: string (YYYY-MM-DD) 
    - guests: number (number of adults)
    """
    try:
        logger.info("Starting search_hotels_tool execution")
        
        # Extract parameters
        destination = parameters.get("destination")
        check_in_date = parameters.get("check_in_date")
        check_out_date = parameters.get("check_out_date")
        guests = int(parameters.get("guests", 1))
        
        logger.info(f"Extracted parameters: dest={destination}, checkin={check_in_date}, checkout={check_out_date}, guests={guests}")
        
        # Validate required parameters
        if not all([destination, check_in_date, check_out_date]):
            logger.warning("Missing required parameters")
            return JSONResponse({
                "error": "Missing required parameters",
                "required": ["destination", "check_in_date", "check_out_date"]
            }, status_code=400)
        
        # Get city code from destination
        logger.info(f"Getting city code for {destination}")
        city_code = await amadeus_client.get_city_code(destination)
        logger.info(f"Got city code: {city_code}")
        
        if not city_code:
            logger.warning(f"No city code found for {destination}")
            return JSONResponse({
                "result": f"Could not find city code for {destination}. Please try a different city name.",
                "success": False
            })
        
        # Search hotels
        logger.info(f"Searching hotels for city_code={city_code}")
        hotels = await amadeus_client.search_hotels(
            city_code=city_code,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            adults=guests
        )
        logger.info(f"Got {len(hotels) if hotels else 0} hotels from Amadeus")
        
        if not hotels:
            return JSONResponse({
                "result": f"No hotels found in {destination} for {check_in_date} to {check_out_date}. Please try different dates.",
                "success": False
            })
        
        # Format results for voice response
        hotel_list = []
        for i, hotel_offer in enumerate(hotels[:3]):  # Top 3 results
            hotel = hotel_offer.get("hotel", {})
            offers = hotel_offer.get("offers", [])
            
            if offers:
                offer = offers[0]
                price = offer.get("price", {})
                room = offer.get("room", {})
                
                hotel_info = {
                    "index": i + 1,
                    "name": hotel.get("name", "Unknown Hotel"),
                    "price": f"${price.get('total', 'N/A')} {price.get('currency', '')}",
                    "room_type": room.get("type", "Standard Room"),
                    "offer_id": offer.get("id")
                }
                hotel_list.append(hotel_info)
        
        # Create voice-friendly response
        hotel_descriptions = []
        for hotel in hotel_list:
            hotel_descriptions.append(f"{hotel['index']}. {hotel['name']} - {hotel['price']} for a {hotel['room_type']}")
        
        result_text = f"I found {len(hotel_list)} hotels in {destination}:\n" + "\n".join(hotel_descriptions)
        
        # VAPI expects just the result string, not a JSONResponse
        return result_text
        
    except Exception as e:
        logger.error(f"Error in search_hotels_tool: {e}")
        return "I'm having trouble searching for hotels right now. Please try again."

async def book_hotel_tool(parameters: Dict[str, Any], call_data: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Book a hotel using stored user profile
    
    Expected parameters from VAPI:
    - offer_id: string (from search results)
    
    Note: User is identified by phone number from the VAPI call
    """
    try:
        # Extract required parameters
        offer_id = parameters.get("offer_id")
        
        # Validate required parameters
        if not offer_id:
            return JSONResponse({
                "result": "I need the hotel offer ID to complete the booking.",
                "success": False
            }, status_code=400)
        
        # Get phone number from call data
        caller_phone = None
        if call_data:
            caller_phone = call_data.get("customer", {}).get("number")
        
        if not caller_phone:
            return JSONResponse({
                "result": "I couldn't identify your phone number. Please make sure you're calling from the phone number you used to sign up.",
                "success": False,
                "action_needed": "phone_identification_failed"
            }, status_code=400)
        
        # Get user profile from database by phone
        user_profile = await db.get_user_by_phone(caller_phone)
        if not user_profile:
            return JSONResponse({
                "result": f"I couldn't find a profile for phone number {caller_phone}. Please sign up at hotelbooking.buzz first, then call back to book.",
                "success": False,
                "redirect_to_signup": True
            })
        
        # Check if user has payment method on file
        if not user_profile.get("has_payment_method"):
            return JSONResponse({
                "result": "You need to add a payment method to your profile first. Please visit our website to add your card details.",
                "success": False,
                "redirect_to_payment": True
            })
        
        # Create hotel order using stored profile data
        hotel_order = HotelOrder(
            data=HotelOrderData(
                guests=[
                    Guest(
                        tid=1,
                        title=user_profile.get("title", "MR"),
                        firstName=user_profile["first_name"],
                        lastName=user_profile["last_name"],
                        phone=user_profile["phone"],
                        email=user_profile["email"]
                    )
                ],
                travelAgent=TravelAgent(contact={"email": user_profile["email"]}),
                roomAssociations=[
                    RoomAssociation(
                        guestReferences=[GuestReference(guestReference="1")],
                        hotelOfferId=offer_id
                    )
                ],
                payment=Payment(
                    method="CREDIT_CARD",
                    paymentCard={
                        "paymentCardInfo": {
                            "vendorCode": user_profile.get("card_vendor", "VI"),
                            "cardNumber": user_profile["card_number"],  # Encrypted in DB
                            "expiryDate": user_profile["card_expiry"],
                            "holderName": user_profile["card_holder_name"]
                        }
                    }
                )
            )
        )
        
        # Create booking via Amadeus
        booking_result = await amadeus_client.create_hotel_booking(hotel_order)
        
        if booking_result:
            # Store booking in database
            booking_data = {
                "user_id": user_profile["id"],
                "amadeus_order_id": booking_result.get("id"),
                "offer_id": offer_id,
                "booking_status": "CONFIRMED",
                "price": 0,  # Extract from offer details
                "currency": "USD"
            }
            
            # Save to Supabase
            booking_record = await db.create_booking(booking_data)
            
            confirmation_number = booking_result.get("associatedRecords", [{}])[0].get("reference", "N/A")
            
            return JSONResponse({
                "result": f"Perfect! Your hotel is booked. Confirmation number: {confirmation_number}. I've sent the details to {user_profile['email']}.",
                "success": True,
                "confirmation_number": confirmation_number,
                "booking_id": booking_result.get("id"),
                "user_name": user_profile["first_name"]
            })
        else:
            return JSONResponse({
                "result": "Sorry, the booking failed. This might be due to the room no longer being available or a payment issue. Please try a different hotel.",
                "success": False
            }, status_code=400)
        
    except Exception as e:
        logger.error(f"Error in book_hotel_tool: {e}")
        return JSONResponse({
            "result": "I'm having trouble completing your booking right now. Please try again in a moment.",
            "success": False,
            "error": str(e)
        }, status_code=500)

# Additional endpoints for testing
@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify VAPI integration is working"""
    return {"message": "VAPI webhook is working!", "timestamp": datetime.now().isoformat()}

@router.post("/test-search")
async def test_hotel_search(destination: str, check_in: str, check_out: str, guests: int = 1):
    """Test hotel search functionality"""
    try:
        city_code = await amadeus_client.get_city_code(destination)
        if not city_code:
            raise HTTPException(status_code=404, detail=f"City code not found for {destination}")
        
        hotels = await amadeus_client.search_hotels(
            city_code=city_code,
            check_in_date=check_in,
            check_out_date=check_out,
            adults=guests
        )
        
        return {
            "destination": destination,
            "city_code": city_code,
            "hotels_found": len(hotels),
            "hotels": hotels[:3]  # Return first 3 for testing
        }
        
    except Exception as e:
        logger.error(f"Error in test hotel search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
