"""
Session Manager for Voice Hotel Booking

Handles Redis-based session storage for maintaining booking flow context
across multiple VAPI function calls.
"""

import json
import redis
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class BookingSessionManager:
    """Manages booking sessions using Redis for persistence"""
    
    def __init__(self):
        """Initialize Redis connection"""
        try:
            if settings.redis_url:
                self.redis_client = redis.from_url(settings.redis_url)
            else:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password,
                    decode_responses=True
                )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def create_session(self, session_id: str, initial_data: Dict[str, Any] = None) -> bool:
        """
        Create a new booking session
        
        Args:
            session_id: Unique session identifier
            initial_data: Initial session data
            
        Returns:
            bool: True if session created successfully
        """
        try:
            session_data = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "status": "active",
                "step": "initial",
                **(initial_data or {})
            }
            
            # Store session with 24-hour expiration
            key = f"booking_session:{session_id}"
            self.redis_client.setex(
                key, 
                timedelta(hours=24), 
                json.dumps(session_data)
            )
            
            logger.info(f"Created booking session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict containing session data or None if not found
        """
        try:
            key = f"booking_session:{session_id}"
            data = self.redis_client.get(key)
            
            if data:
                session_data = json.loads(data)
                logger.debug(f"Retrieved session: {session_id}")
                return session_data
            else:
                logger.warning(f"Session not found: {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session data
        
        Args:
            session_id: Session identifier
            updates: Data to update
            
        Returns:
            bool: True if updated successfully
        """
        try:
            # Get existing session
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"Cannot update non-existent session: {session_id}")
                return False
            
            # Update data
            session_data.update(updates)
            session_data["updated_at"] = datetime.now().isoformat()
            
            # Save back to Redis
            key = f"booking_session:{session_id}"
            self.redis_client.setex(
                key,
                timedelta(hours=24),
                json.dumps(session_data)
            )
            
            logger.info(f"Updated session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            key = f"booking_session:{session_id}"
            result = self.redis_client.delete(key)
            
            if result:
                logger.info(f"Deleted session: {session_id}")
                return True
            else:
                logger.warning(f"Session not found for deletion: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def extend_session(self, session_id: str, hours: int = 24) -> bool:
        """
        Extend session expiration
        
        Args:
            session_id: Session identifier
            hours: Hours to extend
            
        Returns:
            bool: True if extended successfully
        """
        try:
            key = f"booking_session:{session_id}"
            result = self.redis_client.expire(key, timedelta(hours=hours))
            
            if result:
                logger.info(f"Extended session {session_id} by {hours} hours")
                return True
            else:
                logger.warning(f"Session not found for extension: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to extend session {session_id}: {e}")
            return False
    
    def get_session_field(self, session_id: str, field: str) -> Any:
        """
        Get a specific field from session data
        
        Args:
            session_id: Session identifier
            field: Field name to retrieve
            
        Returns:
            Field value or None if not found
        """
        session_data = self.get_session(session_id)
        if session_data:
            return session_data.get(field)
        return None
    
    def set_session_field(self, session_id: str, field: str, value: Any) -> bool:
        """
        Set a specific field in session data
        
        Args:
            session_id: Session identifier
            field: Field name to set
            value: Value to set
            
        Returns:
            bool: True if set successfully
        """
        return self.update_session(session_id, {field: value})
    
    def is_session_complete(self, session_id: str) -> bool:
        """
        Check if booking session has all required information
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session is complete
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        # Required fields for complete booking
        required_fields = [
            "check_in_date",
            "check_out_date", 
            "guests",
            "guest_name",
            "room_selection"
        ]
        
        return all(session_data.get(field) for field in required_fields)
    
    def get_session_progress(self, session_id: str) -> Dict[str, Any]:
        """
        Get booking progress information
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with progress information
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return {"exists": False}
        
        # Check what information we have
        progress = {
            "exists": True,
            "session_id": session_id,
            "step": session_data.get("step", "initial"),
            "status": session_data.get("status", "active"),
            "has_dates": bool(session_data.get("check_in_date") and session_data.get("check_out_date")),
            "has_guests": bool(session_data.get("guests")),
            "has_occasion": bool(session_data.get("occasion")),
            "has_name": bool(session_data.get("guest_name")),
            "has_room_selection": bool(session_data.get("room_selection")),
            "has_guest_info": bool(session_data.get("guest_info")),
            "has_payment_info": bool(session_data.get("payment_info")),
            "created_at": session_data.get("created_at"),
            "updated_at": session_data.get("updated_at")
        }
        
        return progress


# Global session manager instance
session_manager = BookingSessionManager()
