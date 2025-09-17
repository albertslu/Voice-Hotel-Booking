from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any
from models import VAPICall, VoiceBookingRequest, Guest, Payment, HotelOrder, HotelOrderData, TravelAgent, RoomAssociation, GuestReference
from amadeus_client import amadeus_client
from database import db
from datetime import datetime, date
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["VAPI Webhooks"])

# Store conversation state (in production, use Redis or database)
conversation_state = {}

@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    Main VAPI webhook endpoint for handling voice interactions
    """
    try:
        payload = await request.json()
        logger.info(f"Received VAPI webhook: {payload}")
        
        # Extract call information
        call_id = payload.get("call", {}).get("id")
        message_type = payload.get("message", {}).get("type")
        
        if not call_id:
            logger.error("No call ID found in webhook payload")
            return JSONResponse({"error": "Invalid payload"}, status_code=400)
        
        # Handle different message types
        if message_type == "conversation-update":
            return await handle_conversation_update(call_id, payload)
        elif message_type == "function-call":
            return await handle_function_call(call_id, payload)
        elif message_type == "end-of-call-report":
            return await handle_end_of_call(call_id, payload)
        else:
            logger.info(f"Unhandled message type: {message_type}")
            return JSONResponse({"status": "received"})
            
    except Exception as e:
        logger.error(f"Error processing VAPI webhook: {e}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)

async def handle_conversation_update(call_id: str, payload: Dict[Any, Any]):
    """Handle conversation updates from VAPI"""
    try:
        transcript = payload.get("message", {}).get("transcript", "")
        
        # Initialize conversation state if not exists
        if call_id not in conversation_state:
            conversation_state[call_id] = {
                "step": "greeting",
                "booking_data": {},
                "transcript": []
            }
        
        # Add to transcript
        conversation_state[call_id]["transcript"].append(transcript)
        
        # Analyze transcript and determine next action
        response = await analyze_and_respond(call_id, transcript)
        
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"Error handling conversation update: {e}")
        return JSONResponse({"error": "Failed to process conversation"}, status_code=500)

async def handle_function_call(call_id: str, payload: Dict[Any, Any]):
    """Handle function calls from VAPI"""
    try:
        function_call = payload.get("message", {}).get("functionCall", {})
        function_name = function_call.get("name")
        parameters = function_call.get("parameters", {})
        
        logger.info(f"Function call: {function_name} with parameters: {parameters}")
        
        if function_name == "search_hotels":
            return await search_hotels_function(call_id, parameters)
        elif function_name == "book_hotel":
            return await book_hotel_function(call_id, parameters)
        else:
            logger.warning(f"Unknown function call: {function_name}")
            return JSONResponse({"error": f"Unknown function: {function_name}"})
            
    except Exception as e:
        logger.error(f"Error handling function call: {e}")
        return JSONResponse({"error": "Failed to process function call"}, status_code=500)

async def handle_end_of_call(call_id: str, payload: Dict[Any, Any]):
    """Handle end of call cleanup"""
    try:
        # Clean up conversation state
        if call_id in conversation_state:
            logger.info(f"Cleaning up conversation state for call: {call_id}")
            del conversation_state[call_id]
        
        return JSONResponse({"status": "call_ended"})
        
    except Exception as e:
        logger.error(f"Error handling end of call: {e}")
        return JSONResponse({"error": "Failed to process end of call"}, status_code=500)

async def analyze_and_respond(call_id: str, transcript: str) -> Dict[str, Any]:
    """
    Analyze user input and determine appropriate response
    """
    state = conversation_state[call_id]
    current_step = state["step"]
    booking_data = state["booking_data"]
    
    # Simple keyword-based analysis (in production, use NLP/LLM)
    transcript_lower = transcript.lower()
    
    if current_step == "greeting":
        if any(word in transcript_lower for word in ["hotel", "book", "reservation", "room"]):
            state["step"] = "get_destination"
            return {
                "message": {
                    "type": "assistant-message",
                    "content": "I'd be happy to help you book a hotel! Where would you like to stay?"
                }
            }
    
    elif current_step == "get_destination":
        # Extract destination (simple approach)
        booking_data["destination"] = transcript.strip()
        state["step"] = "get_dates"
        return {
            "message": {
                "type": "assistant-message", 
                "content": f"Great! You want to stay in {booking_data['destination']}. When would you like to check in? Please provide the date."
            }
        }
    
    elif current_step == "get_dates":
        # Extract check-in date (simple approach)
        booking_data["check_in_date"] = transcript.strip()
        state["step"] = "get_checkout_date"
        return {
            "message": {
                "type": "assistant-message",
                "content": "And when would you like to check out?"
            }
        }
    
    elif current_step == "get_checkout_date":
        booking_data["check_out_date"] = transcript.strip()
        state["step"] = "get_guests"
        return {
            "message": {
                "type": "assistant-message",
                "content": "How many guests will be staying?"
            }
        }
    
    elif current_step == "get_guests":
        booking_data["guests"] = transcript.strip()
        state["step"] = "search_hotels"
        
        # Trigger hotel search
        return {
            "message": {
                "type": "function-call",
                "functionCall": {
                    "name": "search_hotels",
                    "parameters": booking_data
                }
            }
        }
    
    # Default response
    return {
        "message": {
            "type": "assistant-message",
            "content": "I'm here to help you book a hotel. Could you please tell me where you'd like to stay?"
        }
    }

async def search_hotels_function(call_id: str, parameters: Dict[str, Any]) -> JSONResponse:
    """Search for hotels using Amadeus API"""
    try:
        destination = parameters.get("destination", "")
        check_in = parameters.get("check_in_date", "")
        check_out = parameters.get("check_out_date", "")
        guests = int(parameters.get("guests", 1))
        
        # Get city code from destination
        city_code = await amadeus_client.get_city_code(destination)
        if not city_code:
            return JSONResponse({
                "message": {
                    "type": "assistant-message",
                    "content": f"I couldn't find hotels for {destination}. Could you try a different city?"
                }
            })
        
        # Search hotels
        hotels = await amadeus_client.search_hotels(
            city_code=city_code,
            check_in_date=check_in,
            check_out_date=check_out,
            adults=guests
        )
        
        if not hotels:
            return JSONResponse({
                "message": {
                    "type": "assistant-message",
                    "content": f"I couldn't find any available hotels in {destination} for those dates. Would you like to try different dates?"
                }
            })
        
        # Store search results in conversation state
        conversation_state[call_id]["search_results"] = hotels
        conversation_state[call_id]["step"] = "present_options"
        
        # Present top 3 options
        hotel_options = []
        for i, hotel in enumerate(hotels[:3]):
            hotel_info = hotel.get("hotel", {})
            offers = hotel.get("offers", [])
            if offers:
                price = offers[0].get("price", {})
                hotel_options.append(f"{i+1}. {hotel_info.get('name', 'Unknown Hotel')} - ${price.get('total', 'N/A')} {price.get('currency', '')}")
        
        options_text = "\n".join(hotel_options)
        
        return JSONResponse({
            "message": {
                "type": "assistant-message",
                "content": f"I found some great options for you:\n{options_text}\n\nWhich hotel would you like to book? Just say the number."
            }
        })
        
    except Exception as e:
        logger.error(f"Error in search_hotels_function: {e}")
        return JSONResponse({
            "message": {
                "type": "assistant-message",
                "content": "I'm having trouble searching for hotels right now. Could you please try again?"
            }
        })

async def book_hotel_function(call_id: str, parameters: Dict[str, Any]) -> JSONResponse:
    """Book a hotel using Amadeus API"""
    try:
        # This would be called after user provides personal details and payment info
        # For demo purposes, we'll use placeholder data
        
        return JSONResponse({
            "message": {
                "type": "assistant-message",
                "content": "I would need your personal details and payment information to complete the booking. For this demo, I'll simulate a successful booking. Your reservation has been confirmed! You'll receive a confirmation email shortly."
            }
        })
        
    except Exception as e:
        logger.error(f"Error in book_hotel_function: {e}")
        return JSONResponse({
            "message": {
                "type": "assistant-message",
                "content": "I'm having trouble completing your booking right now. Please try again or contact our support team."
            }
        })

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
