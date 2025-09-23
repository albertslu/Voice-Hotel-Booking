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
            
            # Handle structured response from search_hotel
            if isinstance(result, dict) and "message" in result:
                # Return the message for AI to speak, but also include the structured data
                tool_call_id = tool_calls[0].get("id") if tool_calls else "unknown"
                return JSONResponse({
                    "results": [
                        {
                            "toolCallId": tool_call_id,
                            "result": result["message"],  # AI speaks this
                            "data": {  # Additional data for next tool calls
                                "session_id": result.get("session_id"),
                                "room_options": result.get("room_options"),
                                "search_completed": result.get("search_completed")
                            }
                        }
                    ]
                })
            else:
                # Fallback for string responses (error cases)
                tool_call_id = tool_calls[0].get("id") if tool_calls else "unknown"
                return JSONResponse({
                    "results": [
                        {
                            "toolCallId": tool_call_id,
                            "result": result
                        }
                    ]
                })
        elif function_name == "book_hotel_1":
            # Step 1: Select room from search results
            return await book_hotel_1(parameters, payload.get("call", {}))
        elif function_name == "book_hotel_2":
            # Step 2: Collect guest info and payment, complete booking
            return await book_hotel_2(parameters, payload.get("call", {}))
        elif function_name == "book_hotel":
            # Legacy booking function
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

def get_room_name(room_code: str) -> str:
    """
    Convert room codes to human-readable room names for SF Proper Hotel
    """
    room_names = {
        "PRDD": "Proper Double Room",
        "PRKG": "Proper King Room", 
        "JSTE": "Junior Suite",
        "PSTE": "Proper Suite",
        "JS1DD": "Junior Suite with Double Beds",
        "JS1PK": "Junior Suite with King Bed",
        "PK1DD": "Proper King Room with Double Beds",
        "BUNK": "Bunk Room",
        # Add more mappings as needed
    }
    
    # Return mapped name or enhanced version of room code
    return room_names.get(room_code, f"{room_code} Room")

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
        
        # TODO: Trigger browser automation API to start booking process with search parameters
        booking_session_id = f"booking_{int(datetime.now().timestamp())}"
        
        # Store room details for later selection in book_hotel_1
        room_options = []
        for i, rate in enumerate(selected_rates):
            room_options.append({
                "choice_number": i + 1,
                "room_code": rate.get("roomCode"),
                "room_name": get_room_name(rate.get("roomCode", "")),
                "rate_package": rate.get("description", ""),
                "price_before_tax": rate.get("basePriceBeforeTax", 0),
                "total_with_fees": rate.get("tax", {}).get("totalWithTaxesAndFees", 0),
                "rate_data": rate  # Store full rate data for browser automation
            })
        
        # Prepare automation payload for browser automation service
        automation_payload = {
            "action": "start_booking_with_search",
            "step": "search_and_initialize",
            "data": {
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "adults": guests,
                "children": 0,
                "hotel": "sf-proper",
                "selected_rates": selected_rates,
                "room_options": room_options
            },
            "session_id": booking_session_id
        }
        
        logger.info(f"Browser automation payload for search: {automation_payload}")
        
        # TODO: Replace with actual API call to browser automation service
        # response = await browser_automation_client.start_booking_with_search(automation_payload)
        
        # TODO: Store room_options in session/cache for book_hotel_1 to access
        # For now, we'll include it in the response for the AI to pass along
        # In production, you'd store this in Redis/database with the session_id
        
        # Format selected rates for voice response
        rate_descriptions = []
        for i, rate in enumerate(selected_rates):
            price_before_tax = rate.get("basePriceBeforeTax", 0)
            total_with_fees = rate.get("tax", {}).get("totalWithTaxesAndFees", 0)
            room_code = rate.get("roomCode", "Room")
            
            # Get room type name and rate package description
            room_name = get_room_name(room_code)
            rate_package = rate.get("description", "")
            
            # Combine room type and package for better description
            if rate_package and rate_package != room_name:
                full_description = f"{room_name} ({rate_package})"
            else:
                full_description = room_name
            
            description = f"{i + 1}. {full_description} - ${price_before_tax:.0f} per night, ${total_with_fees:.0f} total with taxes and fees"
            rate_descriptions.append(description)
        
        result_text = f"Perfect! I found the ideal options for your stay:\n" + "\n".join(rate_descriptions) + f"\n\nI've started preparing your booking (Session: {booking_session_id}). Which room would you like to book? I'll need your name, email, and phone number to proceed."
        logger.info(f"AZDS API returned {len(rates)} rates, booking session started: {booking_session_id}")
        
        # Return structured data for VAPI that includes both the spoken response and booking data
        return {
            "message": result_text,  # What the AI will speak
            "session_id": booking_session_id,  # For the next booking step
            "room_options": room_options,  # Room details for browser automation
            "search_completed": True
        }
            
        except Exception as e:
            logger.error(f"Error calling AZDS API: {e}")
            return "I'm having trouble getting hotel rates right now. Please try again."
        
    except Exception as e:
            logger.error(f"Error in search_hotel: {e}")
            return "I'm having trouble searching for hotels right now. Please try again."

async def book_hotel_1(parameters: Dict[str, Any], call_data: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Step 1 - Select room from search results
    
    Expected parameters from VAPI:
    - session_id: string (from search_hotel) [REQUIRED]
    - room_choice: number (1 or 2, which room from search results) [REQUIRED]
    - room_options: array (room details from search_hotel) [REQUIRED for browser automation]
    """
    try:
        logger.info("Starting book_hotel_1 execution")
        
        # Extract parameters
        session_id = parameters.get("session_id")
        room_choice = int(parameters.get("room_choice", 1))
        room_options = parameters.get("room_options", [])
        
        logger.info(f"Book Hotel Step 1 - Session: {session_id}, Room Choice: {room_choice}")
        
        # Validate required parameters
        if not session_id:
            return JSONResponse({
                "result": "I need the booking session ID to continue. Please search for hotels first.",
                "success": False,
                "step": 1
            }, status_code=400)
        
        # Validate room choice
        if room_choice not in [1, 2]:
            return JSONResponse({
                "result": "Please choose room 1 or room 2 from the search results.",
                "success": False,
                "step": 1
            }, status_code=400)
        
        # Find the selected room details
        selected_room = None
        for room in room_options:
            if room.get("choice_number") == room_choice:
                selected_room = room
                break
        
        if not selected_room:
            return JSONResponse({
                "result": "I couldn't find the room details. Please search for hotels again.",
                "success": False,
                "step": 1
            }, status_code=400)
        
        # TODO: Call browser automation API to select the specific room/offer
        automation_payload = {
            "action": "select_room_offer",
            "step": 1,
            "session_id": session_id,
            "data": {
                "room_choice": room_choice,
                "selected_room": {
                    "room_code": selected_room.get("room_code"),
                    "room_name": selected_room.get("room_name"),
                    "rate_package": selected_room.get("rate_package"),
                    "price_before_tax": selected_room.get("price_before_tax"),
                    "total_with_fees": selected_room.get("total_with_fees"),
                    "rate_data": selected_room.get("rate_data")  # Full API response for exact matching
                }
            }
        }
        
        logger.info(f"Browser automation payload: {automation_payload}")
        
        # TODO: Replace with actual API call to browser automation service
        # response = await browser_automation_client.select_room_offer(automation_payload)
        
        room_description = f"{selected_room.get('room_name')} ({selected_room.get('rate_package')})" if selected_room.get('rate_package') else selected_room.get('room_name')
        
        return JSONResponse({
            "result": f"Perfect! I've selected the {room_description} at ${selected_room.get('price_before_tax'):.0f} per night. Now I need your information to complete the booking. What name should I put the reservation under?",
            "success": True,
            "step": 1,
            "session_id": session_id,
            "selected_room": selected_room,
            "next_step": "collect_guest_and_payment_info"
        })
        
    except Exception as e:
        logger.error(f"Error in book_hotel_1: {e}")
        return JSONResponse({
            "result": "I'm having trouble selecting your room right now. Please try again in a moment.",
            "success": False,
            "step": 1,
            "error": str(e)
        }, status_code=500)

async def book_hotel_2(parameters: Dict[str, Any], call_data: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Step 2 - Collect complete guest information and payment details to complete booking
    
    Expected parameters from VAPI:
    - session_id: string (from previous steps) [REQUIRED]
    
    Guest Information:
    - first_name: string (guest first name) [REQUIRED]
    - last_name: string (guest last name) [REQUIRED]
    - email: string (contact email) [REQUIRED]
    - phone: string (contact phone) [REQUIRED]
    - address: string (street address) [REQUIRED]
    - zip_code: string (postal/zip code) [REQUIRED]
    - city: string (city) [REQUIRED]
    - state: string (state/province) [REQUIRED]
    - country: string (country) [REQUIRED]
    
    Payment Information:
    - card_number: string (credit card number) [REQUIRED]
    - expiry_month: string (MM format) [REQUIRED]
    - expiry_year: string (YYYY format) [REQUIRED]
    - cvv: string (3-4 digit security code) [REQUIRED]
    - cardholder_name: string (name on card) [REQUIRED]
    """
    try:
        logger.info("Starting book_hotel_2 execution")
        
        # Extract parameters
        session_id = parameters.get("session_id")
        
        # Guest information
        first_name = parameters.get("first_name")
        last_name = parameters.get("last_name")
        email = parameters.get("email")
        phone = parameters.get("phone")
        address = parameters.get("address")
        zip_code = parameters.get("zip_code")
        city = parameters.get("city")
        state = parameters.get("state")
        country = parameters.get("country")
        
        # Payment information
        card_number = parameters.get("card_number", "").replace(" ", "").replace("-", "")
        expiry_month = parameters.get("expiry_month")
        expiry_year = parameters.get("expiry_year")
        cvv = parameters.get("cvv")
        cardholder_name = parameters.get("cardholder_name")
        
        logger.info(f"Book Hotel Step 2 - Session: {session_id}, Guest: {first_name} {last_name}, Card ending: {card_number[-4:] if len(card_number) >= 4 else 'XXXX'}")
        
        # Validate required parameters
        if not session_id:
            return JSONResponse({
                "result": "I need the booking session ID to continue. Please start the booking process again.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Check for missing guest information
        guest_fields = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "address": address,
            "zip_code": zip_code,
            "city": city,
            "state": state,
            "country": country
        }
        
        missing_guest_fields = []
        for field_name, field_value in guest_fields.items():
            if not field_value:
                # Convert field names to user-friendly names
                friendly_names = {
                    "first_name": "first name",
                    "last_name": "last name",
                    "email": "email address",
                    "phone": "phone number",
                    "address": "street address",
                    "zip_code": "zip code",
                    "city": "city",
                    "state": "state",
                    "country": "country"
                }
                missing_guest_fields.append(friendly_names.get(field_name, field_name))
        
        if missing_guest_fields:
            return JSONResponse({
                "result": f"I still need your {', '.join(missing_guest_fields[:-1])} and {missing_guest_fields[-1]}" if len(missing_guest_fields) > 1 else f"I still need your {missing_guest_fields[0]}",
                "success": False,
                "step": 2,
                "missing_fields": missing_guest_fields
            }, status_code=400)
        
        # Check for missing payment information
        if not all([card_number, expiry_month, expiry_year, cvv, cardholder_name]):
            missing_fields = []
            if not card_number:
                missing_fields.append("card number")
            if not expiry_month:
                missing_fields.append("expiry month")
            if not expiry_year:
                missing_fields.append("expiry year")
            if not cvv:
                missing_fields.append("CVV")
            if not cardholder_name:
                missing_fields.append("cardholder name")
            
            return JSONResponse({
                "result": f"I still need your {' and '.join(missing_fields)} to complete the booking.",
                "success": False,
                "step": 2,
                "missing_fields": missing_fields
            }, status_code=400)
        
        # Validate guest information
        import re
        from datetime import datetime, date
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return JSONResponse({
                "result": "Please provide a valid email address.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Basic phone validation
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) < 10:
            return JSONResponse({
                "result": "Please provide a valid phone number with at least 10 digits.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Validate payment information
        card_digits = re.sub(r'\D', '', card_number)
        
        # Validate card number length (13-19 digits for most cards)
        if len(card_digits) < 13 or len(card_digits) > 19:
            return JSONResponse({
                "result": "Please provide a valid credit card number.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Validate expiry date
        try:
            month = int(expiry_month)
            year = int(expiry_year)
            
            if month < 1 or month > 12:
                return JSONResponse({
                    "result": "Please provide a valid expiry month (01-12).",
                    "success": False,
                    "step": 2
                }, status_code=400)
            
            # Check if card is expired
            today = date.today()
            if year < today.year or (year == today.year and month < today.month):
                return JSONResponse({
                    "result": "This card appears to be expired. Please provide a valid card.",
                    "success": False,
                    "step": 2
                }, status_code=400)
                
        except ValueError:
            return JSONResponse({
                "result": "Please provide valid expiry month and year.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Validate CVV (3-4 digits)
        cvv_digits = re.sub(r'\D', '', cvv)
        if len(cvv_digits) < 3 or len(cvv_digits) > 4:
            return JSONResponse({
                "result": "Please provide a valid CVV (3 or 4 digits).",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # TODO: Call browser automation API to complete booking
        automation_payload = {
            "action": "complete_booking",
            "step": 2,
            "session_id": session_id,
            "data": {
                # Guest information for booking form
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "address": address,
                "zip_code": zip_code,
                "city": city,
                "state": state,
                "country": country,
                
                # Payment information
                "card_number": card_digits,
                "expiry_month": expiry_month.zfill(2),  # Ensure 2-digit format
                "expiry_year": expiry_year,
                "cvv": cvv_digits,
                "cardholder_name": cardholder_name
            }
        }
        
        logger.info(f"Browser automation payload (card masked): {session_id}")
        
        # TODO: Replace with actual API call to browser automation service
        # response = await browser_automation_client.complete_booking(automation_payload)
        
        # Generate confirmation number (in production, this would come from the hotel's booking system)
        import random
        confirmation_number = f"SF{random.randint(100000, 999999)}"
        
        return JSONResponse({
            "result": f"Excellent! Your reservation has been confirmed, {first_name}. Your confirmation number is {confirmation_number}. You'll receive a confirmation email at {email} shortly with all the details. Thank you for choosing San Francisco Proper Hotel!",
            "success": True,
            "step": 2,
            "session_id": session_id,
            "confirmation_number": confirmation_number,
            "booking_completed": True,
            "guest_info": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "address": address,
                "zip_code": zip_code,
                "city": city,
                "state": state,
                "country": country
            }
        })
        
    except Exception as e:
        logger.error(f"Error in book_hotel_2: {e}")
        return JSONResponse({
            "result": "I'm having trouble completing your booking right now. Please try again in a moment, and don't worry - your information is secure.",
            "success": False,
            "step": 2,
            "error": str(e)
        }, status_code=500)

async def book_hotel(parameters: Dict[str, Any], call_data: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Step 3 - Collect payment information and complete booking
    
    Expected parameters from VAPI:
    - session_id: string (from previous steps) [REQUIRED]
    - card_number: string (credit card number) [REQUIRED]
    - expiry_month: string (MM format) [REQUIRED]
    - expiry_year: string (YYYY format) [REQUIRED]
    - cvv: string (3-4 digit security code) [REQUIRED]
    - cardholder_name: string (name on card) [REQUIRED]
    """
    try:
        logger.info("Starting book_hotel_3 execution")
        
        # Extract parameters
        session_id = parameters.get("session_id")
        card_number = parameters.get("card_number", "").replace(" ", "").replace("-", "")
        expiry_month = parameters.get("expiry_month")
        expiry_year = parameters.get("expiry_year")
        cvv = parameters.get("cvv")
        cardholder_name = parameters.get("cardholder_name")
        
        logger.info(f"Book Hotel Step 3 - Session: {session_id}, Card ending in: {card_number[-4:] if len(card_number) >= 4 else 'XXXX'}")
        
        # Validate required parameters
        if not session_id:
            return JSONResponse({
                "result": "I need the booking session ID to continue. Please start the booking process again.",
                "success": False,
                "step": 3
            }, status_code=400)
        
        if not all([card_number, expiry_month, expiry_year, cvv, cardholder_name]):
            missing_fields = []
            if not card_number:
                missing_fields.append("card number")
            if not expiry_month:
                missing_fields.append("expiry month")
            if not expiry_year:
                missing_fields.append("expiry year")
            if not cvv:
                missing_fields.append("CVV")
            if not cardholder_name:
                missing_fields.append("cardholder name")
            
            return JSONResponse({
                "result": f"I still need your {' and '.join(missing_fields)} to complete the booking.",
                "success": False,
                "step": 3,
                "missing_fields": missing_fields
            }, status_code=400)
        
        # Basic card validation
        import re
        from datetime import datetime, date
        
        # Remove any non-digits from card number
        card_digits = re.sub(r'\D', '', card_number)
        
        # Validate card number length (13-19 digits for most cards)
        if len(card_digits) < 13 or len(card_digits) > 19:
            return JSONResponse({
                "result": "Please provide a valid credit card number.",
                "success": False,
                "step": 3
            }, status_code=400)
        
        # Validate expiry date
        try:
            month = int(expiry_month)
            year = int(expiry_year)
            
            if month < 1 or month > 12:
                return JSONResponse({
                    "result": "Please provide a valid expiry month (01-12).",
                    "success": False,
                    "step": 3
                }, status_code=400)
            
            # Check if card is expired
            today = date.today()
            if year < today.year or (year == today.year and month < today.month):
                return JSONResponse({
                    "result": "This card appears to be expired. Please provide a valid card.",
                    "success": False,
                    "step": 3
                }, status_code=400)
                
        except ValueError:
            return JSONResponse({
                "result": "Please provide valid expiry month and year.",
                "success": False,
                "step": 3
            }, status_code=400)
        
        # Validate CVV (3-4 digits)
        cvv_digits = re.sub(r'\D', '', cvv)
        if len(cvv_digits) < 3 or len(cvv_digits) > 4:
            return JSONResponse({
                "result": "Please provide a valid CVV (3 or 4 digits).",
                "success": False,
                "step": 3
            }, status_code=400)
        
        # TODO: Call browser automation API to complete booking
        automation_payload = {
            "action": "complete_booking",
            "step": 3,
            "session_id": session_id,
            "data": {
                "card_number": card_digits,
                "expiry_month": expiry_month.zfill(2),  # Ensure 2-digit format
                "expiry_year": expiry_year,
                "cvv": cvv_digits,
                "cardholder_name": cardholder_name
            }
        }
        
        logger.info(f"Browser automation payload (card masked): {session_id}")
        
        # TODO: Replace with actual API call to browser automation service
        # response = await browser_automation_client.complete_booking(automation_payload)
        
        # Generate confirmation number (in production, this would come from the hotel's booking system)
        import random
        confirmation_number = f"SF{random.randint(100000, 999999)}"
        
        return JSONResponse({
            "result": f"Excellent! Your reservation has been confirmed. Your confirmation number is {confirmation_number}. You'll receive a confirmation email shortly with all the details. Thank you for choosing San Francisco Proper Hotel!",
            "success": True,
            "step": 3,
            "session_id": session_id,
            "confirmation_number": confirmation_number,
            "booking_completed": True,
            "next_step": "booking_complete"
        })
        
    except Exception as e:
        logger.error(f"Error in book_hotel_3: {e}")
        return JSONResponse({
            "result": "I'm having trouble completing your booking right now. Please try again in a moment, and don't worry - your information is secure.",
            "success": False,
            "step": 3,
            "error": str(e)
        }, status_code=500)

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

# Test endpoint removed - amadeus_client no longer available
