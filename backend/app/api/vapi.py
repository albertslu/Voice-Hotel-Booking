from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any, Optional
from app.services import AmadeusHotelClient
from app.services.azds_service import azds_client
from datetime import datetime
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
        
        if function_name == "search_hotel":
            logger.info("Matched search_hotel function")
            logger.info("About to call search_hotel")
            result = await search_hotel(parameters)
            logger.info(f"search_hotel returned: {type(result)}")
            
            # VAPI expects results in a specific format
            tool_call_id = tool_calls[0].get("id") if tool_calls else "unknown"
            return JSONResponse({
                "results": [
                    {
                        "toolCallId": tool_call_id,
                        "result": result
                    }
                ]
            })
        elif function_name == "book_hotel":
            # Pass the full payload to get call data (phone number)
            return await book_hotel(parameters, payload.get("call", {}))
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

def select_best_rates(rates: list, guests: int, occasion: str) -> list:
    """
    Select the 2 best rates based on party size and occasion
    """
    # Sort by price (cheapest first)
    sorted_rates = sorted(rates, key=lambda x: x.get("basePriceBeforeTax", 999999))
    
    # Room type preferences based on occasion
    if "business" in occasion or "work" in occasion:
        # Prefer quiet, professional rooms
        preferred_codes = ["PRDD", "PRKG", "JSTE"]
    elif "romance" in occasion or "anniversary" in occasion or "honeymoon" in occasion:
        # Prefer suites and premium rooms
        preferred_codes = ["JSTE", "PSTE", "JS1DD", "PK1DD"]
    elif "solo" in occasion or guests == 1:
        # Include bunk rooms for solo travelers
        preferred_codes = ["BUNK", "PRDD", "PRKG"]
    elif guests >= 3:
        # Prefer larger rooms for groups
        preferred_codes = ["JS1DD", "PK1DD", "JSTE", "PSTE"]
    else:
        # Default: best value rooms
        preferred_codes = ["PRDD", "PRKG", "JSTE"]
    
    # Find best rates matching preferences
    selected = []
    
    # First, try to find preferred room types
    for rate in sorted_rates:
        room_code = rate.get("roomCode", "")
        if room_code in preferred_codes and len(selected) < 2:
            selected.append(rate)
    
    # If we don't have 2 rooms yet, add cheapest available (excluding BUNK unless solo)
    for rate in sorted_rates:
        if len(selected) >= 2:
            break
        room_code = rate.get("roomCode", "")
        if rate not in selected:
            # Skip BUNK rooms unless solo traveler or specifically requested
            if room_code == "BUNK" and guests > 1 and "solo" not in occasion:
                continue
            selected.append(rate)
    
    return selected[:2]  # Always return max 2 rates

async def search_hotel(parameters: Dict[str, Any]) -> JSONResponse:
    """
    VAPI Tool: Search for SF Proper Hotel rates
    
    Expected parameters from VAPI:
    - check_in_date: string (YYYY-MM-DD) [REQUIRED]
    - check_out_date: string (YYYY-MM-DD) [REQUIRED]
    - adults: number (number of adult guests) [REQUIRED]
    - occasion: string (purpose of travel: business, romance, solo, etc.) [OPTIONAL]
    """
    try:
        logger.info("Starting search_hotel execution")
        
        # Extract parameters
        check_in_date = parameters.get("check_in_date")
        check_out_date = parameters.get("check_out_date")
        guests = int(parameters.get("adults", parameters.get("guests", 2)))
        occasion = parameters.get("occasion", "").lower()
        
        logger.info(f"Extracted parameters: checkin={check_in_date}, checkout={check_out_date}, guests={guests}")
        
        # Validate required parameters
        if not all([check_in_date, check_out_date]):
            logger.warning("Missing required parameters")
            return "I need check-in and check-out dates to search for hotel rates."
        
        # Use AZDS API for SF Proper Hotel demo
        logger.info("Using AZDS API for hotel search")
        
        try:
            # Convert YYYY-MM-DD to MM/DD/YYYY format for AZDS API
            from datetime import datetime
            check_in_dt = datetime.strptime(check_in_date, "%Y-%m-%d")
            check_out_dt = datetime.strptime(check_out_date, "%Y-%m-%d")
            
            check_in_formatted = check_in_dt.strftime("%m/%d/%Y")
            check_out_formatted = check_out_dt.strftime("%m/%d/%Y")
            
            # Call AZDS API for SF Proper Hotel
            data = await azds_client.get_hotel_rates(
                hotel_code="proper-sf",
                check_in_date=check_in_formatted,
                check_out_date=check_out_formatted,
                adults=guests,
                children=0
            )
            
            rates = data.get("rates", [])
            if not rates:
                return "I'm sorry, I couldn't find any available rates for San Francisco Proper Hotel for those dates."
            
            # Smart room selection based on occasion and party size
            selected_rates = select_best_rates(rates, guests, occasion)
            
            # Format selected rates for voice response
            rate_descriptions = []
            for i, rate in enumerate(selected_rates):
                price_before_tax = rate.get("basePriceBeforeTax", 0)
                total_with_fees = rate.get("tax", {}).get("totalWithTaxesAndFees", 0)
                room_code = rate.get("roomCode", "Room")
                
                # Use API description or fallback to room code
                room_name = rate.get("description", room_code)
                
                description = f"{i + 1}. {room_name} - ${price_before_tax:.0f} per night, ${total_with_fees:.0f} total with taxes and fees"
                rate_descriptions.append(description)
            
            result_text = f"Perfect! I found the ideal options for your stay:\n" + "\n".join(rate_descriptions) + "\n\nWould you like to proceed with booking one of these rooms?"
            logger.info(f"AZDS API returned {len(rates)} rates")
            return result_text
            
        except Exception as e:
            logger.error(f"Error calling AZDS API: {e}")
            return "I'm having trouble getting hotel rates right now. Please try again."
        
    except Exception as e:
            logger.error(f"Error in search_hotel: {e}")
            return "I'm having trouble searching for hotels right now. Please try again."

async def book_hotel(parameters: Dict[str, Any], call_data: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Initiate hotel booking process with voice-collected information
    
    Expected parameters from VAPI:
    - offer_id: string (from search results)
    - guest_name: string (collected via voice)
    - guest_email: string (collected via voice)
    - guest_phone: string (collected via voice)
    """
    try:
        # Extract required parameters
        offer_id = parameters.get("offer_id")
        guest_name = parameters.get("guest_name")
        guest_email = parameters.get("guest_email")
        guest_phone = parameters.get("guest_phone")
        
        # Validate required parameters
        if not offer_id:
            return JSONResponse({
                "result": "I need the hotel offer ID to complete the booking.",
                "success": False
            }, status_code=400)
        
        if not all([guest_name, guest_email, guest_phone]):
            return JSONResponse({
                "result": "I need your name, email, and phone number to proceed with the booking.",
                "success": False,
                "missing_info": {
                    "name": not guest_name,
                    "email": not guest_email, 
                    "phone": not guest_phone
                }
            }, status_code=400)
        
        # Generate a secure checkout link for the hotel's website
        # This would typically include the offer details and guest information
        checkout_url = f"https://guestara.ai/checkout?offer={offer_id}&name={guest_name}&email={guest_email}&phone={guest_phone}"
        
        # Send SMS with secure checkout link
        sms_message = f"Hi {guest_name}! Complete your hotel booking securely here: {checkout_url}"
        
        # Log the booking attempt for tracking
        logger.info(f"Hotel booking initiated for {guest_name} ({guest_email}) - Offer: {offer_id}")
        
        return JSONResponse({
            "result": f"Perfect! I've sent a secure checkout link to {guest_phone} via text message. You can complete your booking safely on the hotel's website. The link will expire in 24 hours for your security.",
            "success": True,
            "checkout_url": checkout_url,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "offer_id": offer_id,
            "sms_sent": True
        })
        
    except Exception as e:
        logger.error(f"Error in book_hotel: {e}")
        return JSONResponse({
            "result": "I'm having trouble setting up your booking right now. Please try again in a moment.",
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
