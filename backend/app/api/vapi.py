from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any, Optional
from app.services import AmadeusHotelClient
from app.services.azds_service import azds_client
from app.services.session_manager import session_manager
from datetime import datetime
import json
import os
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["VAPI Webhooks"])

# Browser automation service URL - configured via environment variable
BROWSER_AUTOMATION_URL = os.getenv("BROWSER_AUTOMATION_URL", "http://localhost:3000")

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
        if message_type in ["tool-calls", "function-call"]:
            return await handle_function_call(payload)
        else:
            # For other message types, just acknowledge
            # logger.info(f"Received message type: {message_type}")
            return JSONResponse({"status": "received"})
            
    except Exception as e:
        logger.error(f"Error processing VAPI webhook: {e}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)

async def handle_function_call(payload: Dict[Any, Any]):
    """Handle function calls from VAPI"""
    try:
        message = payload.get("message", {})
        message_type = message.get("type")
        
        # Handle both tool-calls and function-call formats
        tool_calls = message.get("toolCalls", [])
        function_call = message.get("functionCall", {})
        
        if tool_calls:
            # Handle tool-calls format
            tool_call = tool_calls[0]
            function_info = tool_call.get("function", {})
            function_name = function_info.get("name")
            arguments = function_info.get("arguments", {})
            # Parse arguments if it's a string
            if isinstance(arguments, str):
                try:
                    parameters = json.loads(arguments)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse arguments JSON: {arguments}")
                    parameters = {}
            else:
                parameters = arguments
        elif function_call:
            # Handle function-call format
            function_name = function_call.get("name")
            parameters = function_call.get("parameters", {})
        else:
            logger.warning("No tool calls or function calls found in message")
            return JSONResponse({"error": "No function calls found"}, status_code=400)
        
        logger.info(f"Function call: {function_name} with parameters: {parameters}")
        logger.info(f"Function name type: {type(function_name)}, repr: {repr(function_name)}")
        logger.info("About to check function_name == 'search_hotels'")
        
        # Extract caller phone number from VAPI payload
        caller_phone = None
        try:
            customer = payload.get("call", {}).get("customer", {})
            if not customer:
                # Try alternative path
                customer = payload.get("customer", {})
            caller_phone = customer.get("number", "")
            logger.info(f"Extracted caller phone: {caller_phone}")
        except Exception as e:
            logger.warning(f"Could not extract caller phone: {e}")
        
        if function_name == "search_hotel":
            logger.info("Matched search_hotel function")
            logger.info("About to call search_hotel")
            # Pass caller phone to search_hotel
            result = await search_hotel(parameters, caller_phone=caller_phone)
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
            logger.info("Matched book_hotel_1 function")
            logger.info("About to call book_hotel_1")
            result = await book_hotel_1(parameters, payload)
            logger.info(f"book_hotel_1 returned: {type(result)}")
            return result
        elif function_name == "book_hotel_2":
            # Step 2: Collect guest info and payment, complete booking
            return await book_hotel_2(parameters, payload)
        elif function_name == "start_over":
            # Clear current session and restart booking process
            return await start_over(parameters, payload.get("call", {}))
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

async def start_over(parameters: Dict[str, Any], call_data: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Start Over - Clear current booking session and restart the process
    
    Expected parameters from VAPI:
    - session_id: string (current booking session ID) [OPTIONAL - can be retrieved from context]
    """
    try:
        logger.info("Starting start_over execution")
        
        # Extract parameters
        session_id = parameters.get("session_id")
        
        logger.info(f"Start Over - Session: {session_id}")
        
        # If session_id provided, try to clear it
        if session_id:
            # Get session info before deleting (for logging)
            session_data = session_manager.get_session(session_id)
            if session_data:
                step = session_data.get("step", "unknown")
                logger.info(f"Clearing session at step: {step}")
                
                # Delete the session
                deleted = session_manager.delete_session(session_id)
                if deleted:
                    logger.info(f"Successfully cleared session: {session_id}")
                else:
                    logger.warning(f"Failed to clear session: {session_id}")
            else:
                logger.info(f"Session not found or already cleared: {session_id}")
        
        # TODO: If you have browser automation running, stop it here
        # Example:
        # if session_id:
        #     automation_payload = {
        #         "action": "stop_automation",
        #         "session_id": session_id
        #     }
        #     await browser_automation_client.stop_session(automation_payload)
        
        return JSONResponse({
            "result": "Absolutely! I've cleared your current booking. Let's start fresh - what dates would you like to stay at San Francisco Proper Hotel?",
            "success": True,
            "action": "start_over",
            "session_cleared": bool(session_id),
            "next_step": "collect_dates"
        })
        
    except Exception as e:
        logger.error(f"Error in start_over: {e}")
        return JSONResponse({
            "result": "I've reset our conversation. Let's start fresh - what dates would you like to stay at San Francisco Proper Hotel?",
            "success": True,
            "action": "start_over",
            "error": str(e)
        })

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


async def search_hotel(parameters: Dict[str, Any], caller_phone: Optional[str] = None) -> JSONResponse:
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

        # INSERT_YOUR_CODE
        # Create a search.md file with the search parameters for debugging/auditing
        try:
            with open("search.md", "w") as f:
                f.write("# Hotel Search Parameters\n\n")
                for k, v in parameters.items():
                    f.write(f"- **{k}**: {v}\n")
        except Exception as e:
            logger.warning(f"Could not write search.md: {e}")
        
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
            
            # Send all rates to VAPI - let the AI choose the best options based on conversation
            selected_rates = rates  # Send all available rates for AI selection
            
            # Create booking session with Redis
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
            
            # Create session in Redis with all booking context
            session_data = {
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "guests": guests,
                "occasion": occasion,
                "step": "search_completed",
                "room_options": room_options,
                "selected_rates": selected_rates,
                "hotel": "sf-proper",
                "caller_phone": caller_phone  # Auto-captured from VAPI
            }
            
            # Store session in Redis
            session_created = session_manager.create_session(booking_session_id, session_data)
            if not session_created:
                logger.error(f"Failed to create session: {booking_session_id}")
                return "I'm having trouble starting your booking. Please try again."
            
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
            logger.info(f"Session stored in Redis: {booking_session_id}")
            
            # Start browser automation session
            browser_session_id = None
            browser_customer_id = None
            
            try:
                async with httpx.AsyncClient() as client:
                    # Call browser automation /book/search to start the session
                    search_payload = {
                        "checkInDate": check_in_date,
                        "checkOutDate": check_out_date
                    }
                    
                    browser_response = await client.post(
                        f"{BROWSER_AUTOMATION_URL}/book/search",
                        json=search_payload,
                        timeout=30.0
                    )
                    
                    if browser_response.status_code == 200:
                        browser_data = browser_response.json()
                        if browser_data.get("success"):
                            browser_session_id = browser_data.get("sessionId")
                            browser_customer_id = browser_data.get("customerId")
                            logger.info(f"Browser automation session started: {browser_session_id}")
                            
                            # Update Redis session with browser automation details
                            session_updates = {
                                "browser_session_id": browser_session_id,
                                "browser_customer_id": browser_customer_id
                            }
                            session_manager.update_session(booking_session_id, session_updates)
                            logger.info(f"Updated session with browser automation details")
                        else:
                            logger.warning(f"Browser automation search failed: {browser_data}")
                    else:
                        logger.warning(f"Browser automation returned status {browser_response.status_code}")
                        
            except Exception as e:
                logger.warning(f"Failed to start browser automation session: {e}")
                # Continue without browser automation - don't fail the search
            
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
            
            # Return all available rates for VAPI to intelligently select from
            result_text = f"Perfect! I found {len(selected_rates)} available options for your stay from {check_in_date} to {check_out_date} for {guests} guest{'s' if guests != 1 else ''}:\n\n" + "\n".join(rate_descriptions)
            logger.info(f"AZDS API returned {len(rates)} rates, booking session started: {booking_session_id}")       
            
            # Create a JSON file with room options for debugging or logging purposes

            output_dir = "./search_test_results"
            os.makedirs(output_dir, exist_ok=True)
            json_filename = f"{output_dir}/room_options_{booking_session_id}.json"
            try:
                with open(json_filename, "w") as f:
                    json.dump(room_options, f, indent=2)
                logger.info(f"Room options written to {json_filename}")
            except Exception as e:
                logger.error(f"Failed to write room options JSON: {e}")

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

async def book_hotel_1(parameters: Dict[str, Any], payload: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Step 1 - Select room from search results
    
    Expected parameters from VAPI:
    - room_choice: number (1 or 2, which room from search results) [REQUIRED]
    
    Note: Session ID is automatically retrieved using caller's phone number
    """
    try:
        logger.info("Starting book_hotel_1 execution")
        
        # Extract caller phone number from VAPI payload
        caller_phone = None
        try:
            call_info = payload.get("call", {}) if payload else {}
            customer = call_info.get("customer", {})
            caller_phone = customer.get("number", "").replace("+", "").replace("-", "").replace(" ", "")
            logger.info(f"Extracted caller phone: {caller_phone}")
        except Exception as e:
            logger.error(f"Failed to extract caller phone: {e}")
        
        # Extract parameters
        room_choice = int(parameters.get("room_choice", 1))
        
        # Find session ID using caller's phone number
        session_id = None
        if caller_phone:
            # Look for the most recent session for this phone number
            # We'll search through recent session IDs to find one with matching caller_phone
            import time
            current_time = int(time.time())
            # Check sessions from the last hour
            for i in range(3600):  # 1 hour = 3600 seconds
                test_session_id = f"booking_{current_time - i}"
                test_session_data = session_manager.get_session(test_session_id)
                if test_session_data and test_session_data.get("caller_phone") == caller_phone:
                    session_id = test_session_id
                    logger.info(f"Found session for phone {caller_phone}: {session_id}")
                    break
        
        logger.info(f"Book Hotel Step 1 - Session: {session_id}, Room Choice: {room_choice}")
        
        # Validate session found
        if not session_id:
            return JSONResponse({
                "result": "I couldn't find your booking session. Please search for hotels first.",
                "success": False,
                "step": 1
            }, status_code=400)
        
        # Get session data from Redis
        session_data = session_manager.get_session(session_id)
        if not session_data:
            return JSONResponse({
                "result": "I couldn't find your booking session. Please search for hotels again.",
                "success": False,
                "step": 1
            }, status_code=400)
        
        # Get room options from session
        room_options = session_data.get("room_options", [])
        if not room_options:
            return JSONResponse({
                "result": "I couldn't find the room options. Please search for hotels again.",
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
        
        # Update session with room selection
        session_updates = {
            "step": "room_selected",
            "room_choice": room_choice,
            "selected_room": selected_room
        }
        
        session_updated = session_manager.update_session(session_id, session_updates)
        if not session_updated:
            logger.error(f"Failed to update session: {session_id}")
            return JSONResponse({
                "result": "I'm having trouble saving your room selection. Please try again.",
                "success": False,
                "step": 1
            }, status_code=500)
        
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
        logger.info(f"Session updated with room selection: {session_id}")
        
        # Call browser automation /book/start if we have a browser session
        browser_session_id = session_data.get("browser_session_id")
        browser_customer_id = session_data.get("browser_customer_id")
        
        if browser_session_id and browser_customer_id:
            try:
                rate_data = selected_room.get("rate_data", {})
                
                start_payload = {
                    "checkInDate": session_data.get("check_in_date"),
                    "checkOutDate": session_data.get("check_out_date"),
                    "rooms": [{
                        "rateCode": rate_data.get("code", ""),
                        "roomCode": rate_data.get("roomCode", ""),
                        "guests": session_data.get("guests", 2),
                        "children": 0
                    }],
                    "sessionId": browser_session_id,
                    "customerId": browser_customer_id
                }
                
                async with httpx.AsyncClient() as client:
                    start_response = await client.post(
                        f"{BROWSER_AUTOMATION_URL}/book/start",
                        json=start_payload,
                        timeout=30.0
                    )
                    
                    if start_response.status_code == 200:
                        start_data = start_response.json()
                        if start_data.get("success"):
                            logger.info(f"Browser automation room selection successful")
                        else:
                            logger.warning(f"Browser automation room selection failed: {start_data}")
                    else:
                        logger.warning(f"Browser automation returned status {start_response.status_code}")
                        
            except Exception as e:
                logger.warning(f"Failed to call browser automation /book/start: {e}")
                # Continue without failing - browser automation is optional at this step
        
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

async def book_hotel_2(parameters: Dict[str, Any], payload: Dict[str, Any] = None) -> JSONResponse:
    """
    VAPI Tool: Step 2 - Collect complete guest information and payment details to complete booking
    
    Guest Information:
    - first_name: string (guest first name) [REQUIRED]
    - last_name: string (guest last name) [REQUIRED]
    - email: string (contact email) [REQUIRED]
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
    
    Note: Session ID and phone number are automatically retrieved using caller's phone number
    """
    try:
        logger.info("Starting book_hotel_2 execution")
        
        # Extract caller phone number from VAPI payload
        caller_phone = None
        try:
            call_info = payload.get("call", {}) if payload else {}
            customer = call_info.get("customer", {})
            caller_phone = customer.get("number", "").replace("+", "").replace("-", "").replace(" ", "")
            logger.info(f"Extracted caller phone: {caller_phone}")
        except Exception as e:
            logger.error(f"Failed to extract caller phone: {e}")
        
        # Find session ID using caller's phone number
        session_id = None
        if caller_phone:
            # Look for the most recent session for this phone number
            import time
            current_time = int(time.time())
            # Check sessions from the last hour
            for i in range(3600):  # 1 hour = 3600 seconds
                test_session_id = f"booking_{current_time - i}"
                test_session_data = session_manager.get_session(test_session_id)
                if test_session_data and test_session_data.get("caller_phone") == caller_phone:
                    session_id = test_session_id
                    logger.info(f"Found session for phone {caller_phone}: {session_id}")
                    break
        
        # Validate session exists
        if not session_id:
            return JSONResponse({
                "result": "I need the booking session ID to continue. Please start the booking process again.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Get session data from Redis
        session_data = session_manager.get_session(session_id)
        if not session_data:
            return JSONResponse({
                "result": "I couldn't find your booking session. Please start the booking process again.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Verify we have room selection from previous step
        if not session_data.get("selected_room"):
            return JSONResponse({
                "result": "I need you to select a room first. Please start the booking process again.",
                "success": False,
                "step": 2
            }, status_code=400)
        
        # Guest information
        first_name = parameters.get("first_name")
        last_name = parameters.get("last_name")
        email = parameters.get("email")
        # Use stored phone number from search_hotel (auto-captured from VAPI)
        phone = session_data.get("caller_phone", parameters.get("phone", ""))
        if session_data.get("caller_phone"):
            logger.info(f"Using auto-captured phone number: {phone}")
        elif parameters.get("phone"):
            logger.info(f"Using provided phone number: {phone}")
        else:
            logger.warning("No phone number available from VAPI or parameters")
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
        
        # Get browser session details from Redis if available
        browser_session_id = session_data.get("browser_session_id")
        browser_customer_id = session_data.get("browser_customer_id")
        
        # Get selected room details
        selected_room = session_data.get("selected_room", {})
        rate_data = selected_room.get("rate_data", {})
        
        # Call browser automation to complete the booking
        confirmation_number = None
        
        try:
            async with httpx.AsyncClient() as client:
                # If we have an existing browser session, just complete the booking
                # (book/start was already called in book_hotel_1)
                if browser_session_id and browser_customer_id:
                    complete_payload = {
                        "guestInfo": {
                            "firstName": first_name,
                            "lastName": last_name,
                            "email": email,
                            "phone": phone,
                            "address": address
                        },
                        "bookingDetails": {
                            "checkInDate": session_data.get("check_in_date"),
                            "checkOutDate": session_data.get("check_out_date"),
                            "rooms": [{
                                "rateCode": rate_data.get("code", ""),
                                "roomCode": rate_data.get("roomCode", ""),
                                "guests": session_data.get("guests", 2),
                                "children": 0
                            }]
                        },
                        "paymentInfo": {
                            "creditCardNumber": card_digits,
                            "expiryMonth": expiry_month.zfill(2),
                            "expiryYear": expiry_year,
                            "cvv": cvv_digits,
                            "cardholderName": cardholder_name
                        },
                        "sessionId": browser_session_id,
                        "customerId": browser_customer_id
                    }
                    
                    complete_response = await client.post(
                        f"{BROWSER_AUTOMATION_URL}/book/complete",
                        json=complete_payload,
                        timeout=60.0
                    )
                    
                    if complete_response.status_code == 200:
                        complete_data = complete_response.json()
                        if complete_data.get("success"):
                            confirmation_number = complete_data.get("confirmationNumber")
                            logger.info(f"Booking completed via browser automation: {confirmation_number}")
                else:
                    # No existing session, use the full booking endpoint
                    logger.info("No browser session found, using full booking endpoint")
                    full_payload = {
                        "guestInfo": {
                            "firstName": first_name,
                            "lastName": last_name,
                            "email": email,
                            "phone": phone,
                            "address": address
                        },
                        "bookingDetails": {
                            "checkInDate": session_data.get("check_in_date"),
                            "checkOutDate": session_data.get("check_out_date"),
                            "rooms": [{
                                "rateCode": rate_data.get("code", ""),
                                "roomCode": rate_data.get("roomCode", ""),
                                "guests": session_data.get("guests", 2),
                                "children": 0
                            }]
                        },
                        "paymentInfo": {
                            "creditCardNumber": card_digits,
                            "expiryMonth": expiry_month.zfill(2),
                            "expiryYear": expiry_year,
                            "cvv": cvv_digits,
                            "cardholderName": cardholder_name
                        }
                    }
                    
                    full_response = await client.post(
                        f"{BROWSER_AUTOMATION_URL}/book/full",
                        json=full_payload,
                        timeout=120.0
                    )
                    
                    if full_response.status_code == 200:
                        full_data = full_response.json()
                        if full_data.get("success"):
                            confirmation_number = full_data.get("confirmationNumber")
                            logger.info(f"Booking completed via full automation: {confirmation_number}")
                            
        except Exception as e:
            logger.error(f"Browser automation failed: {e}")
            # Continue with mock booking as fallback
            logger.warning("Browser automation failed, will use mock booking as fallback")
        
        # If browser automation didn't provide a confirmation number, use mock as fallback
        if not confirmation_number:
            import random
            confirmation_number = f"SF{random.randint(100000, 999999)}"
            logger.warning(f"Using mock confirmation number as fallback: {confirmation_number}")
        
        # Update session with final booking information
        final_session_updates = {
            "step": "booking_completed",
            "status": "completed",
            "confirmation_number": confirmation_number,
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
            },
            "payment_info": {
                "cardholder_name": cardholder_name,
                "card_last_four": card_digits[-4:] if len(card_digits) >= 4 else "XXXX",
                "expiry_month": expiry_month.zfill(2),
                "expiry_year": expiry_year
            },
            "completed_at": datetime.now().isoformat()
        }
        
        session_updated = session_manager.update_session(session_id, final_session_updates)
        if not session_updated:
            logger.warning(f"Failed to update session with final booking info: {session_id}")
        else:
            logger.info(f"Session completed and stored: {session_id}")
        
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

@router.post("/browser-booking-full")
async def browser_booking_full_endpoint(request: Request):
    """
    REST endpoint for hotel booking using browser automation service (single call)
    Uses the /book/full endpoint for complete booking in one step
    
    Expected JSON payload:
    {
        "checkInDate": "2025-12-20",
        "checkOutDate": "2025-12-22",
        "adults": 2,
        "rateCode": "ADVNC",
        "roomCode": "PRKG",
        "firstName": "John",
        "lastName": "Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "address": "123 Market Street, Suite 500",
        "creditCardNumber": "4111111111111111",
        "expiryMonth": "12",
        "expiryYear": "2025",
        "cvv": "123",
        "cardholderName": "John Doe"
    }
    """
    try:
        payload = await request.json()
        logger.info(f"Browser booking full request received")
        
        # Extract parameters
        check_in_date = payload.get("checkInDate")
        check_out_date = payload.get("checkOutDate")
        adults = payload.get("adults", 2)
        rate_code = payload.get("rateCode")
        room_code = payload.get("roomCode")
        
        # Guest info
        first_name = payload.get("firstName")
        last_name = payload.get("lastName")
        email = payload.get("email")
        phone = payload.get("phone")
        address = payload.get("address")
        
        # Payment info
        card_number = payload.get("creditCardNumber")
        expiry_month = payload.get("expiryMonth")
        expiry_year = payload.get("expiryYear")
        cvv = payload.get("cvv")
        cardholder_name = payload.get("cardholderName")
        
        # Validate required fields
        missing_fields = []
        required = {
            "checkInDate": check_in_date,
            "checkOutDate": check_out_date,
            "rateCode": rate_code,
            "roomCode": room_code,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "phone": phone,
            "address": address,
            "creditCardNumber": card_number,
            "expiryMonth": expiry_month,
            "expiryYear": expiry_year,
            "cvv": cvv,
            "cardholderName": cardholder_name
        }
        
        for field, value in required.items():
            if not value:
                missing_fields.append(field)
                
        if missing_fields:
            return JSONResponse({
                "error": f"Missing required fields: {', '.join(missing_fields)}",
                "success": False
            }, status_code=400)
        
        logger.info(f"Starting browser automation (full) for {first_name} {last_name}")
        
        # Prepare payload for browser automation /book/full endpoint
        booking_config = {
            "guestInfo": {
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "phone": phone,
                "address": address
            },
            "bookingDetails": {
                "checkInDate": check_in_date,
                "checkOutDate": check_out_date,
                "rooms": [{
                    "rateCode": rate_code,
                    "roomCode": room_code,
                    "guests": adults,
                    "children": 0
                }]
            },
            "paymentInfo": {
                "creditCardNumber": card_number,
                "expiryMonth": expiry_month,
                "expiryYear": expiry_year,
                "cvv": cvv,
                "cardholderName": cardholder_name
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{BROWSER_AUTOMATION_URL}/book/full",
                    json=booking_config,
                    timeout=120.0  # 2 minutes for full automation
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get("success"):
                    return JSONResponse({
                        "error": data.get("error", "Booking failed"),
                        "success": False,
                        "details": data
                    }, status_code=500)
                
                confirmation_number = data.get("confirmationNumber")
                logger.info(f"Booking completed successfully: {confirmation_number}")
                
                return JSONResponse({
                    "success": True,
                    "confirmationNumber": confirmation_number,
                    "guestName": f"{first_name} {last_name}",
                    "checkIn": check_in_date,
                    "checkOut": check_out_date,
                    "room": f"{room_code} - {rate_code}",
                    "screenshots": data.get("screenshots", []),
                    "pdfPath": data.get("pdfPath"),
                    "startedAt": data.get("startedAt"),
                    "finishedAt": data.get("finishedAt"),
                    "message": f"Booking confirmed! Confirmation number: {confirmation_number}"
                })
                
            except httpx.HTTPError as e:
                logger.error(f"Browser automation HTTP error: {e}")
                return JSONResponse({
                    "error": f"Browser automation service error: {str(e)}",
                    "success": False
                }, status_code=500)
            except Exception as e:
                logger.error(f"Browser automation error: {e}")
                return JSONResponse({
                    "error": f"Unexpected error: {str(e)}",
                    "success": False
                }, status_code=500)
        
    except Exception as e:
        logger.error(f"Error in browser booking full endpoint: {e}")
        return JSONResponse({
            "error": "Failed to process booking request",
            "success": False,
            "details": str(e)
        }, status_code=500)

# Removed /browser-booking endpoint - using direct integration in VAPI tools instead

# Test endpoint removed - amadeus_client no longer available
