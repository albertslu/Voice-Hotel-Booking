#!/usr/bin/env python3
"""
Export hotel rates from Amadeus API to file
Usage: python export_rates.py [hotel_id] [hotel_name] [check_in] [check_out] [output_file]
Example: python export_rates.py BTSFOLHS "LUMA Hotel San Francisco" 2025-11-11 2025-11-13 luma_rates.txt
"""

import asyncio
import sys
import os
import json
import argparse
from datetime import datetime

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from amadeus_hotel_client import AmadeusHotelClient

async def export_hotel_rates(
    hotel_id: str, 
    hotel_name: str, 
    check_in: str, 
    check_out: str, 
    filename: str,
    adults: int = 2,
    rooms: int = 1,
    currency: str = "USD",
    best_rate_only: bool = False,
    country: str = None,
    price_range: str = None,
    board_type: str = None
):
    """Export all hotel rates to a file"""
    
    print(f"🏨 Exporting rates for {hotel_name}")
    print(f"📅 Dates: {check_in} to {check_out}")
    print(f"👥 Adults: {adults}, Rooms: {rooms}")
    print(f"💰 Currency: {currency}")
    print(f"📄 Output file: {filename}")
    print("=" * 60)
    
    # Create Amadeus client instance
    client = AmadeusHotelClient()
    
    # Get hotel offers
    offers_data = await client.get_hotel_offers(
        hotel_id=hotel_id,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        rooms=rooms,
        currency=currency,
        best_rate_only=best_rate_only,
        country_of_residence=country,
        price_range=price_range,
        board_type=board_type
    )
    
    # Format offers
    offers = client.format_hotel_offers(offers_data)
    
    if not offers:
        print("❌ No offers found")
        return
    
    # Create output content
    output_lines = []
    output_lines.append(f"HOTEL RATES EXPORT")
    output_lines.append(f"=" * 80)
    output_lines.append(f"Hotel: {hotel_name}")
    output_lines.append(f"Hotel ID: {hotel_id}")
    output_lines.append(f"Check-in: {check_in}")
    output_lines.append(f"Check-out: {check_out}")
    output_lines.append(f"Adults: {adults}")
    output_lines.append(f"Rooms: {rooms}")
    output_lines.append(f"Currency: {currency}")
    output_lines.append(f"Total Offers: {len(offers)}")
    output_lines.append(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append("")
    output_lines.append("ROOM OFFERS")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # Sort offers by price
    offers_sorted = sorted(offers, key=lambda x: float(x['total_price']) if x['total_price'] else 0)
    
    for i, offer in enumerate(offers_sorted, 1):
        output_lines.append(f"OFFER #{i}")
        output_lines.append(f"-" * 40)
        output_lines.append(f"Offer ID: {offer['offer_id']}")
        output_lines.append(f"Room Type: {offer['room_type']}")
        output_lines.append(f"Room Code: {offer['room_code']}")
        output_lines.append(f"Bed Configuration: {offer['beds']} {offer['bed_type']}")
        output_lines.append(f"Rate Code: {offer['rate_code']}")
        output_lines.append(f"Total Price: {offer['currency']} {offer['total_price']}")
        output_lines.append(f"Price Per Night: {offer['currency']} {offer['avg_per_night']}")
        output_lines.append(f"Refundable: {'Yes' if offer['refundable'] else 'No'}")
        
        if offer['cancellation_deadline']:
            output_lines.append(f"Cancellation Deadline: {offer['cancellation_deadline']}")
        
        if offer['description']:
            # Clean up description
            desc = offer['description'].replace('\n', ' ').strip()
            output_lines.append(f"Description: {desc}")
        
        output_lines.append("")
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"✅ Exported {len(offers)} offers to {filename}")
    
    # Also create a JSON version
    json_filename = filename.replace('.txt', '.json')
    export_data = {
        "hotel_name": hotel_name,
        "hotel_id": hotel_id,
        "check_in": check_in,
        "check_out": check_out,
        "adults": adults,
        "rooms": rooms,
        "currency": currency,
        "total_offers": len(offers),
        "export_date": datetime.now().isoformat(),
        "offers": offers_sorted
    }
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Also exported JSON version to {json_filename}")
    
    return offers_sorted

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Export hotel rates from Amadeus API to file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_rates.py BTSFOLHS "LUMA Hotel San Francisco" 2025-11-11 2025-11-13 luma_rates.txt
  python export_rates.py DPSFODSJ "SF Proper Hotel" 2025-12-01 2025-12-03 proper_rates.txt --adults 1 --rooms 2
        """
    )
    
    parser.add_argument("hotel_id", help="Amadeus hotel ID (e.g., BTSFOLHS)")
    parser.add_argument("hotel_name", help="Hotel name for display")
    parser.add_argument("check_in", help="Check-in date (YYYY-MM-DD)")
    parser.add_argument("check_out", help="Check-out date (YYYY-MM-DD)")
    parser.add_argument("output_file", help="Output filename (e.g., rates.txt)")
    
    parser.add_argument("--adults", type=int, default=2, help="Number of adults (default: 2)")
    parser.add_argument("--rooms", type=int, default=1, help="Number of rooms (default: 1)")
    parser.add_argument("--currency", default="USD", help="Currency code (default: USD)")
    parser.add_argument("--best-rate-only", action="store_true", help="Get only the best rate per room type")
    parser.add_argument("--country", help="Country of residence (ISO 3166-1, e.g., US)")
    parser.add_argument("--price-range", help="Price range filter (e.g., 100-500 or -300 or 200-)")
    parser.add_argument("--board-type", choices=["ROOM_ONLY", "BREAKFAST", "HALF_BOARD", "FULL_BOARD", "ALL_INCLUSIVE"], 
                       help="Meal plan type")
    
    return parser.parse_args()

async def main():
    """Main function with command line argument parsing"""
    args = parse_args()
    
    try:
        await export_hotel_rates(
            hotel_id=args.hotel_id,
            hotel_name=args.hotel_name,
            check_in=args.check_in,
            check_out=args.check_out,
            filename=args.output_file,
            adults=args.adults,
            rooms=args.rooms,
            currency=args.currency,
            best_rate_only=args.best_rate_only,
            country=args.country,
            price_range=args.price_range,
            board_type=args.board_type
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
