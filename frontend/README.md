# Voice Hotel Booking - Frontend

A React TypeScript frontend for the Voice Hotel Booking system. Users can sign up and add their payment information to enable voice-based hotel bookings.

## Features

- **User Registration**: Collect personal information required for hotel bookings
- **Payment Setup**: Securely store encrypted payment information
- **Responsive Design**: Works on desktop and mobile devices
- **Form Validation**: Client-side validation for all inputs
- **API Integration**: Connects to FastAPI backend

## Required Information

The signup form collects all information needed for Amadeus hotel bookings:

### Personal Information
- Title (Mr./Mrs./Ms.)
- First Name
- Last Name  
- Email Address
- Phone Number

### Payment Information
- Cardholder Name
- Card Number (with formatting)
- Expiry Date (MM/YY format)
- Card Type (Visa/Mastercard/Amex)

## How It Works

1. **User signs up** with personal and payment information
2. **Backend stores** encrypted payment details in Supabase
3. **User calls** VAPI voice assistant
4. **Voice booking** uses stored profile for instant bookings

## Development

```bash
# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build
```

## Environment Variables

Create a `.env` file:

```
REACT_APP_API_URL=https://api.hotelbooking.buzz
REACT_APP_PHONE_NUMBER=+1 (555) HOTEL-1
```

## Voice Booking Flow

After signup, users can book hotels by voice:

1. Call the voice assistant number
2. Say: "Book a hotel in [city] for [dates]"
3. Provide email when asked
4. Confirm booking - payment happens automatically!

## Security

- Payment information is encrypted before storage
- Only last 4 digits of card shown in UI
- HTTPS-only communication with backend
- No sensitive data stored in browser