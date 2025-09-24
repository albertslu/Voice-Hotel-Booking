#!/usr/bin/env python3
"""
Test script to verify Redis session management is working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.session_manager import session_manager
import json

def test_session_management():
    """Test Redis session management functionality"""
    print("🔧 Testing Redis Session Management...")
    
    # Test 1: Create a session
    session_id = "test_booking_123456"
    initial_data = {
        "check_in_date": "2025-01-15",
        "check_out_date": "2025-01-16",
        "guests": 2,
        "occasion": "romance",
        "step": "search_completed"
    }
    
    print(f"📝 Creating session: {session_id}")
    success = session_manager.create_session(session_id, initial_data)
    print(f"✅ Session created: {success}")
    
    if not success:
        print("❌ Failed to create session")
        return False
    
    # Test 2: Retrieve the session
    print(f"📖 Retrieving session: {session_id}")
    session_data = session_manager.get_session(session_id)
    print(f"✅ Session retrieved: {session_data is not None}")
    
    if session_data:
        print(f"📊 Session data: {json.dumps(session_data, indent=2)}")
    else:
        print("❌ Failed to retrieve session")
        return False
    
    # Test 3: Update the session
    print(f"🔄 Updating session with room selection...")
    updates = {
        "step": "room_selected",
        "room_choice": 1,
        "selected_room": {
            "room_name": "King Suite",
            "price_before_tax": 450
        }
    }
    
    success = session_manager.update_session(session_id, updates)
    print(f"✅ Session updated: {success}")
    
    # Test 4: Retrieve updated session
    print(f"📖 Retrieving updated session...")
    updated_data = session_manager.get_session(session_id)
    if updated_data:
        print(f"📊 Updated session: {json.dumps(updated_data, indent=2)}")
        print(f"✅ Room choice: {updated_data.get('room_choice')}")
        print(f"✅ Step: {updated_data.get('step')}")
    
    # Test 5: Get session progress
    print(f"📈 Getting session progress...")
    progress = session_manager.get_session_progress(session_id)
    print(f"📊 Progress: {json.dumps(progress, indent=2)}")
    
    # Test 6: Clean up
    print(f"🗑️ Cleaning up test session...")
    success = session_manager.delete_session(session_id)
    print(f"✅ Session deleted: {success}")
    
    print("🎉 All tests completed successfully!")
    return True

if __name__ == "__main__":
    try:
        test_session_management()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
