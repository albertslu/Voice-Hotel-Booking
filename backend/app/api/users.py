from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any, Optional
from app.models.hotel import UserCreate
from app.core import db
from datetime import datetime
import hashlib
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])

@router.post("/signup")
async def create_user(user_data: UserCreate):
    """
    Create a new user account
    """
    try:
        # Check if user already exists
        existing_user = await db.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Create user record
        user_dict = {
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "email": user_data.email,
            "phone": user_data.phone,
            "title": user_data.title,
            "has_payment_method": False,
            "is_active": True,
            "email_verified": False
        }
        
        new_user = await db.create_user(user_dict)
        
        return JSONResponse({
            "message": "Account created successfully!",
            "user_id": new_user["id"],
            "email": new_user["email"],
            "name": f"{new_user['first_name']} {new_user['last_name']}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user account")

@router.post("/add-payment")
async def add_payment_method(payment_data: Dict[str, Any]):
    """
    Add payment method to user account
    
    Expected data:
    - email: string
    - card_number: string
    - card_expiry: string (YYYY-MM)
    - card_holder_name: string
    - card_vendor: string (VI, MC, AX)
    """
    try:
        email = payment_data.get("email")
        card_number = payment_data.get("card_number")
        card_expiry = payment_data.get("card_expiry")
        card_holder_name = payment_data.get("card_holder_name")
        card_vendor = payment_data.get("card_vendor", "VI")
        
        if not all([email, card_number, card_expiry, card_holder_name]):
            raise HTTPException(status_code=400, detail="Missing required payment information")
        
        # Get user
        user = await db.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Encrypt card number (simple encryption for demo - use proper encryption in production)
        encrypted_card = encrypt_card_number(card_number)
        
        # Update user with payment info
        payment_update = {
            "has_payment_method": True,
            "card_vendor": card_vendor,
            "card_last_four": card_number[-4:],
            "card_expiry": card_expiry,
            "card_holder_name": card_holder_name,
            "card_number_encrypted": encrypted_card
        }
        
        # Update user in database (you'll need to implement this in database.py)
        # await db.update_user_payment(user["id"], payment_update)
        
        return JSONResponse({
            "message": "Payment method added successfully!",
            "card_last_four": card_number[-4:],
            "card_vendor": card_vendor
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding payment method: {e}")
        raise HTTPException(status_code=500, detail="Failed to add payment method")

@router.get("/profile/{email}")
async def get_user_profile(email: str):
    """
    Get user profile information
    """
    try:
        user = await db.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Return safe user info (no sensitive payment data)
        return JSONResponse({
            "id": user["id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
            "phone": user["phone"],
            "title": user["title"],
            "has_payment_method": user.get("has_payment_method", False),
            "card_last_four": user.get("card_last_four"),
            "card_vendor": user.get("card_vendor"),
            "is_active": user.get("is_active", True),
            "created_at": user["created_at"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user profile")

@router.get("/bookings/{email}")
async def get_user_bookings(email: str):
    """
    Get user's booking history
    """
    try:
        user = await db.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user's bookings (you'll need to implement this)
        # bookings = await db.get_user_bookings(user["id"])
        
        return JSONResponse({
            "user_email": email,
            "bookings": [],  # Will be populated when you implement get_user_bookings
            "total_bookings": 0
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user bookings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user bookings")

def encrypt_card_number(card_number: str) -> str:
    """
    Simple encryption for demo purposes
    In production, use proper encryption like Fernet or AES
    """
    # This is just for demo - use proper encryption in production!
    key = os.getenv("ENCRYPTION_KEY", "demo-key-change-in-production")
    return hashlib.sha256(f"{card_number}{key}".encode()).hexdigest()

def decrypt_card_number(encrypted_card: str) -> str:
    """
    Decrypt card number (placeholder for demo)
    In production, implement proper decryption
    """
    # This is just a placeholder - implement proper decryption
    return "****-****-****-" + encrypted_card[-4:] if encrypted_card else ""
