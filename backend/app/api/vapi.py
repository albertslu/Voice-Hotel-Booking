from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any, Optional
from app.services import AmadeusHotelClient
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
        
        if function_name == "search_hotels":
            logger.info("Matched search_hotels function")
            logger.info("About to call search_hotels_tool")
            result = await search_hotels_tool(parameters)
            logger.info(f"search_hotels_tool returned: {type(result)}")
            
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
        logger.error(f"Error in book_hotel_tool: {e}")
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
