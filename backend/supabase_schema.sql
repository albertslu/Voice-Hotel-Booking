-- Supabase Schema for Voice Hotel Booking System
-- Run this in your Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    title VARCHAR(10) CHECK (title IN ('MR', 'MRS', 'MS')),
    
    -- Payment information (encrypted)
    has_payment_method BOOLEAN DEFAULT FALSE,
    card_vendor VARCHAR(10), -- VI, MC, AX
    card_last_four VARCHAR(4),
    card_expiry VARCHAR(7), -- YYYY-MM format
    card_holder_name VARCHAR(255),
    card_number_encrypted TEXT, -- Encrypted full card number
    
    -- Profile settings
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Hotels table
CREATE TABLE IF NOT EXISTS hotels (
    id SERIAL PRIMARY KEY,
    amadeus_hotel_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    amenities JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Bookings table
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    hotel_id INTEGER REFERENCES hotels(id) ON DELETE CASCADE,
    amadeus_offer_id VARCHAR(100) NOT NULL,
    amadeus_order_id VARCHAR(100),
    room_type VARCHAR(100),
    price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    check_in_date DATE NOT NULL,
    check_out_date DATE NOT NULL,
    guests_count INTEGER NOT NULL DEFAULT 1,
    booking_status VARCHAR(20) DEFAULT 'PENDING' CHECK (booking_status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED')),
    booking_reference VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_dates CHECK (check_out_date > check_in_date),
    CONSTRAINT positive_price CHECK (price > 0),
    CONSTRAINT positive_guests CHECK (guests_count > 0)
);

-- VAPI Call Logs table (for tracking voice interactions)
CREATE TABLE IF NOT EXISTS vapi_call_logs (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    call_duration INTEGER, -- in seconds
    transcript TEXT,
    booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
    call_status VARCHAR(20) DEFAULT 'COMPLETED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Payment Information table (for storing encrypted payment details)
CREATE TABLE IF NOT EXISTS payment_info (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER REFERENCES bookings(id) ON DELETE CASCADE,
    payment_method VARCHAR(20) DEFAULT 'CREDIT_CARD',
    card_vendor VARCHAR(10), -- VI, MC, AX
    card_last_four VARCHAR(4),
    card_expiry_month INTEGER,
    card_expiry_year INTEGER,
    cardholder_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_hotels_amadeus_id ON hotels(amadeus_hotel_id);
CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_hotel_id ON bookings(hotel_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(booking_status);
CREATE INDEX IF NOT EXISTS idx_bookings_dates ON bookings(check_in_date, check_out_date);
CREATE INDEX IF NOT EXISTS idx_vapi_calls_call_id ON vapi_call_logs(call_id);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_hotels_updated_at BEFORE UPDATE ON hotels FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_bookings_updated_at BEFORE UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotels ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE vapi_call_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_info ENABLE ROW LEVEL SECURITY;

-- Basic RLS policies (adjust based on your authentication needs)
CREATE POLICY "Users can view their own data" ON users FOR SELECT USING (true);
CREATE POLICY "Hotels are viewable by everyone" ON hotels FOR SELECT USING (true);
CREATE POLICY "Bookings are viewable by everyone" ON bookings FOR SELECT USING (true);
CREATE POLICY "VAPI logs are viewable by everyone" ON vapi_call_logs FOR SELECT USING (true);
CREATE POLICY "Payment info is viewable by everyone" ON payment_info FOR SELECT USING (true);

-- Insert policies for service role
CREATE POLICY "Service role can insert users" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "Service role can insert hotels" ON hotels FOR INSERT WITH CHECK (true);
CREATE POLICY "Service role can insert bookings" ON bookings FOR INSERT WITH CHECK (true);
CREATE POLICY "Service role can insert vapi logs" ON vapi_call_logs FOR INSERT WITH CHECK (true);
CREATE POLICY "Service role can insert payment info" ON payment_info FOR INSERT WITH CHECK (true);

-- Update policies for service role
CREATE POLICY "Service role can update users" ON users FOR UPDATE USING (true);
CREATE POLICY "Service role can update hotels" ON hotels FOR UPDATE USING (true);
CREATE POLICY "Service role can update bookings" ON bookings FOR UPDATE USING (true);
CREATE POLICY "Service role can update vapi logs" ON vapi_call_logs FOR UPDATE USING (true);
CREATE POLICY "Service role can update payment info" ON payment_info FOR UPDATE USING (true);

-- Sample data for testing (optional)
INSERT INTO users (first_name, last_name, email, phone, title) VALUES
('John', 'Doe', 'john.doe@example.com', '+1234567890', 'MR'),
('Jane', 'Smith', 'jane.smith@example.com', '+1987654321', 'MS')
ON CONFLICT (email) DO NOTHING;

INSERT INTO hotels (amadeus_hotel_id, name, address, latitude, longitude) VALUES
('HOTEL001', 'Grand Plaza Hotel', '123 Main St, New York, NY', 40.7589, -73.9851),
('HOTEL002', 'Seaside Resort', '456 Beach Ave, Miami, FL', 25.7617, -80.1918)
ON CONFLICT (amadeus_hotel_id) DO NOTHING;
