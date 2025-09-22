#!/usr/bin/env python3
"""
LUMA Hotels Direct Booking Scraper
Scrapes rates directly from LUMA Hotels booking page and formats them similar to Amadeus export
Usage: python luma_scraper.py [check_in] [check_out] [adults] [rooms] [output_file]
Example: python luma_scraper.py 2025-11-11 2025-11-13 2 1 luma_direct_rates.txt
"""

import asyncio
import sys
import os
import json
import argparse
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright
import logging

# Add the backend directory to Python path for flexible imports
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LumaHotelScraper:
    def __init__(self):
        self.base_url = "https://www.lumahotels.com/book"
        self.hotel_name = "LUMA Hotel San Francisco"
        self.hotel_code = "35419"
        
    def build_booking_url(self, check_in: str, check_out: str, adults: int = 2, rooms: int = 1, currency: str = "USD"):
        """Build the LUMA booking URL with parameters"""
        params = {
            'adults': adults,
            'children': 0,
            'clientId': 'luma',
            'currency': currency,
            'endDate': check_out,
            'exactMatchOnly': 'false',
            'hotelCode': self.hotel_code,
            'hotelProvider': 1,
            'numRooms': rooms,
            'primaryLangId': 'en',
            'promoCode': 'DIRECT',
            'sortPriceOrder': 'low',
            'startDate': check_in,
            'theme': 'lumasf'
        }
        
        return f"{self.base_url}?{urlencode(params)}"
    
    async def scrape_rates(self, check_in: str, check_out: str, adults: int = 2, rooms: int = 1, currency: str = "USD"):
        """Scrape hotel rates from LUMA booking page"""
        url = self.build_booking_url(check_in, check_out, adults, rooms, currency)
        logger.info(f"Scraping URL: {url}")
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # Navigate to booking page
                await page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Wait for rates to load
                logger.info("Waiting for rates to load...")
                await page.wait_for_timeout(3000)  # Initial wait
                
                # Try to wait for specific LUMA booking elements
                try:
                    # Wait for the booking interface to load
                    await page.wait_for_selector('div, section, article', timeout=15000)
                    logger.info("Page elements loaded")
                    
                    # Additional wait for dynamic content
                    await page.wait_for_timeout(5000)
                    
                    # Try to find rate-specific elements
                    rate_selectors = [
                        '[data-testid*="rate"]',
                        '[data-testid*="room"]', 
                        '[data-testid*="price"]',
                        '.rate', '.room', '.price',
                        '[class*="rate"]', '[class*="room"]', '[class*="price"]',
                        'button[class*="select"]', 'div[class*="offer"]'
                    ]
                    
                    for selector in rate_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=2000)
                            logger.info(f"Found elements with selector: {selector}")
                            break
                        except:
                            continue
                            
                except Exception as e:
                    logger.warning(f"Timeout waiting for elements: {e}")
                
                # Scroll to load more content
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                
                # Get page content
                content = await page.content()
                
                # Extract rates using multiple strategies
                rates = await self.extract_rates_from_page(page, content)
                
                return rates
                
            except Exception as e:
                logger.error(f"Error scraping rates: {e}")
                return []
            finally:
                await browser.close()
    
    async def extract_rates_from_page(self, page, content):
        """Extract rate information from the page using multiple strategies"""
        rates = []
        
        # Strategy 1: Look for structured rate data in JavaScript
        js_rates = await self.extract_from_javascript(page)
        if js_rates:
            rates.extend(js_rates)
        
        # Strategy 2: Look for rate elements in DOM
        dom_rates = await self.extract_from_dom(page)
        if dom_rates:
            rates.extend(dom_rates)
        
        # Strategy 3: Parse from text content
        text_rates = self.extract_from_text(content)
        if text_rates:
            rates.extend(text_rates)
        
        # Remove duplicates and sort by price
        unique_rates = []
        seen_rates = set()
        
        for rate in rates:
            rate_key = (rate.get('room_type', ''), rate.get('total_price', 0))
            if rate_key not in seen_rates:
                seen_rates.add(rate_key)
                unique_rates.append(rate)
        
        # Sort by price
        unique_rates.sort(key=lambda x: float(str(x.get('total_price', 0)).replace('$', '').replace(',', '')) if x.get('total_price') else 0)
        
        return unique_rates
    
    async def extract_from_javascript(self, page):
        """Extract rates from JavaScript variables or API calls"""
        rates = []
        
        try:
            # Look for common JavaScript variables that might contain rate data
            js_data = await page.evaluate("""
                () => {
                    const data = {};
                    
                    // Check for common variable names
                    if (typeof window.rateData !== 'undefined') data.rateData = window.rateData;
                    if (typeof window.roomRates !== 'undefined') data.roomRates = window.roomRates;
                    if (typeof window.hotelData !== 'undefined') data.hotelData = window.hotelData;
                    if (typeof window.bookingData !== 'undefined') data.bookingData = window.bookingData;
                    
                    // Check for React/Vue data
                    const scripts = Array.from(document.querySelectorAll('script'));
                    for (const script of scripts) {
                        const text = script.textContent || '';
                        if (text.includes('rate') && text.includes('price')) {
                            try {
                                const matches = text.match(/\\{[^{}]*"rate"[^{}]*\\}/g);
                                if (matches) data.scriptData = matches;
                            } catch (e) {}
                        }
                    }
                    
                    return data;
                }
            """)
            
            # Process the extracted JavaScript data
            if js_data:
                logger.info(f"Found JavaScript data: {list(js_data.keys())}")
                # Process the data to extract rates
                # This would need to be customized based on the actual data structure
                
        except Exception as e:
            logger.warning(f"Error extracting from JavaScript: {e}")
        
        return rates
    
    async def extract_from_dom(self, page):
        """Extract rates from DOM elements"""
        rates = []
        
        try:
            # Get all text content first to analyze structure
            all_text = await page.evaluate("document.body.innerText")
            logger.info(f"Page text length: {len(all_text)} characters")
            
            # Enhanced selectors for hotel booking sites
            selectors = [
                # Generic booking selectors
                '[data-testid*="rate"]', '[data-testid*="room"]', '[data-testid*="price"]',
                '[data-testid*="offer"]', '[data-testid*="booking"]',
                
                # Class-based selectors
                '.rate-card', '.room-rate', '.room-option', '.booking-option', '.price-card',
                '.room-card', '.offer-card', '.rate-option', '.booking-card',
                
                # Generic class patterns
                '[class*="rate"]', '[class*="room"]', '[class*="price"]', '[class*="offer"]',
                '[class*="booking"]', '[class*="select"]', '[class*="choose"]',
                
                # Button and interactive elements
                'button', 'a[href*="book"]', 'div[role="button"]',
                
                # Container elements that might hold rates
                'section', 'article', 'div[class*="container"]', 'div[class*="content"]'
            ]
            
            found_rates = []
            
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if not elements:
                        continue
                        
                    logger.info(f"Analyzing {len(elements)} elements with selector: {selector}")
                    
                    for i, element in enumerate(elements):
                        try:
                            # Get element details
                            text = await element.text_content()
                            if not text or len(text.strip()) < 3:
                                continue
                                
                            # Look for price patterns
                            price_patterns = [
                                r'\$(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',  # $123.45 or $1,234.56
                                r'(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|dollars?)',  # 123.45 USD
                                r'(?:USD|dollars?)\s*(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)'   # USD 123.45
                            ]
                            
                            for pattern in price_patterns:
                                price_matches = re.findall(pattern, text, re.IGNORECASE)
                                for price_str in price_matches:
                                    try:
                                        price_value = float(price_str.replace(',', ''))
                                        # Filter for reasonable hotel prices
                                        if 50 <= price_value <= 5000:
                                            rate_info = {
                                                'room_type': self.extract_room_type(text),
                                                'total_price': f'${price_value:.0f}',
                                                'price_per_night': f'${price_value:.0f}',
                                                'description': text.strip()[:200],
                                                'source': f'dom_extraction_{selector[:20]}',
                                                'element_index': i,
                                                'raw_text': text.strip()[:100]
                                            }
                                            
                                            # Try to extract more details
                                            rate_info.update(self.extract_additional_details(text))
                                            found_rates.append(rate_info)
                                            
                                    except ValueError:
                                        continue
                                        
                        except Exception as e:
                            logger.warning(f"Error processing element {i}: {e}")
                            continue
                    
                    # If we found good rates with this selector, we can continue to next
                    if found_rates:
                        logger.info(f"Found {len(found_rates)} rates with selector: {selector}")
                        
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue
            
            # Remove duplicates based on price and description similarity
            unique_rates = []
            seen_prices = set()
            
            for rate in found_rates:
                price_key = rate.get('total_price', '')
                desc_key = rate.get('description', '')[:50]  # First 50 chars for similarity
                
                rate_signature = (price_key, desc_key)
                if rate_signature not in seen_prices:
                    seen_prices.add(rate_signature)
                    unique_rates.append(rate)
            
            logger.info(f"Found {len(unique_rates)} unique rates after deduplication")
            return unique_rates
            
        except Exception as e:
            logger.error(f"Error extracting from DOM: {e}")
            return []
    
    def extract_from_text(self, content):
        """Extract rates from raw text content"""
        rates = []
        
        try:
            # Look for price patterns in the entire page content
            price_patterns = [
                r'\$\d{1,4}(?:,\d{3})*(?:\.\d{2})?',  # $123.45 or $1,234.56
                r'USD\s*\d{1,4}(?:,\d{3})*(?:\.\d{2})?',  # USD 123.45
                r'\d{1,4}(?:,\d{3})*(?:\.\d{2})?\s*USD'   # 123.45 USD
            ]
            
            all_prices = []
            for pattern in price_patterns:
                matches = re.findall(pattern, content)
                all_prices.extend(matches)
            
            # Remove duplicates and filter reasonable hotel prices
            unique_prices = list(set(all_prices))
            hotel_prices = []
            
            for price in unique_prices:
                # Extract numeric value
                numeric_price = float(re.sub(r'[^\d.]', '', price))
                # Filter for reasonable hotel prices (between $50 and $2000 per night)
                if 50 <= numeric_price <= 2000:
                    hotel_prices.append(price)
            
            # Create rate objects for found prices
            for i, price in enumerate(hotel_prices[:20]):  # Limit to 20 rates
                rate_info = {
                    'offer_id': f'DIRECT_{i+1:03d}',
                    'room_type': 'UNKNOWN',
                    'room_code': 'DIRECT',
                    'bed_configuration': 'Unknown',
                    'rate_code': 'DIRECT',
                    'total_price': price,
                    'price_per_night': price,  # Assuming single night for now
                    'refundable': 'Unknown',
                    'description': f'Direct booking rate - {price}',
                    'source': 'text_extraction'
                }
                rates.append(rate_info)
                
        except Exception as e:
            logger.warning(f"Error extracting from text: {e}")
        
        return rates
    
    def extract_room_type(self, text):
        """Extract room type from text"""
        text_lower = text.lower()
        
        if 'deluxe' in text_lower:
            return 'DELUXE_ROOM'
        elif 'suite' in text_lower:
            return 'SUITE'
        elif 'standard' in text_lower:
            return 'STANDARD_ROOM'
        elif 'premium' in text_lower:
            return 'PREMIUM_ROOM'
        elif 'king' in text_lower:
            return 'KING_ROOM'
        elif 'queen' in text_lower:
            return 'QUEEN_ROOM'
        elif 'twin' in text_lower:
            return 'TWIN_ROOM'
        else:
            return 'UNKNOWN_ROOM'
    
    def extract_additional_details(self, text):
        """Extract additional details from text"""
        details = {}
        text_lower = text.lower()
        
        # Extract bed configuration
        if 'king' in text_lower:
            details['bed_configuration'] = '1 King'
        elif 'queen' in text_lower:
            if '2' in text or 'two' in text_lower:
                details['bed_configuration'] = '2 Queen'
            else:
                details['bed_configuration'] = '1 Queen'
        elif 'twin' in text_lower:
            details['bed_configuration'] = '2 Twin'
        else:
            details['bed_configuration'] = 'Unknown'
        
        # Extract rate codes
        rate_codes = []
        if 'aaa' in text_lower:
            rate_codes.append('AAA')
        if 'senior' in text_lower:
            rate_codes.append('SNR')
        if 'advance' in text_lower:
            rate_codes.append('ADV')
        if 'non-refundable' in text_lower or 'nonrefundable' in text_lower:
            rate_codes.append('NRF')
        if 'flexible' in text_lower:
            rate_codes.append('FLX')
        
        details['rate_code'] = '/'.join(rate_codes) if rate_codes else 'DIRECT'
        
        # Extract refundability
        if 'non-refundable' in text_lower or 'nonrefundable' in text_lower:
            details['refundable'] = 'No'
        elif 'refundable' in text_lower or 'flexible' in text_lower:
            details['refundable'] = 'Yes'
        else:
            details['refundable'] = 'Unknown'
        
        # Extract amenities/features
        amenities = []
        if 'wifi' in text_lower:
            amenities.append('WiFi')
        if 'breakfast' in text_lower:
            amenities.append('Breakfast')
        if 'parking' in text_lower:
            amenities.append('Parking')
        if 'spa' in text_lower:
            amenities.append('Spa')
        if 'gym' in text_lower or 'fitness' in text_lower:
            amenities.append('Fitness')
        
        if amenities:
            details['amenities'] = ', '.join(amenities)
        
        return details
    
    def format_rates_output(self, rates, check_in, check_out, adults, rooms, currency):
        """Format rates in the same style as Amadeus export"""
        output_lines = []
        
        # Header
        output_lines.append("HOTEL RATES EXPORT")
        output_lines.append("=" * 80)
        output_lines.append(f"Hotel: {self.hotel_name}")
        output_lines.append(f"Hotel Code: {self.hotel_code}")
        output_lines.append(f"Check-in: {check_in}")
        output_lines.append(f"Check-out: {check_out}")
        output_lines.append(f"Adults: {adults}")
        output_lines.append(f"Rooms: {rooms}")
        output_lines.append(f"Currency: {currency}")
        output_lines.append(f"Total Offers: {len(rates)}")
        output_lines.append(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"Source: Direct LUMA Hotels Booking Page")
        output_lines.append("")
        output_lines.append("ROOM OFFERS")
        output_lines.append("=" * 80)
        output_lines.append("")
        
        # Rates
        for i, rate in enumerate(rates, 1):
            output_lines.append(f"OFFER #{i}")
            output_lines.append("-" * 40)
            output_lines.append(f"Offer ID: {rate.get('offer_id', f'DIRECT_{i:03d}')}")
            output_lines.append(f"Room Type: {rate.get('room_type', 'UNKNOWN')}")
            output_lines.append(f"Room Code: {rate.get('room_code', 'DIRECT')}")
            output_lines.append(f"Bed Configuration: {rate.get('bed_configuration', 'Unknown')}")
            output_lines.append(f"Rate Code: {rate.get('rate_code', 'DIRECT')}")
            output_lines.append(f"Total Price: {rate.get('total_price', 'N/A')}")
            output_lines.append(f"Price Per Night: {rate.get('price_per_night', rate.get('total_price', 'N/A'))}")
            output_lines.append(f"Refundable: {rate.get('refundable', 'Unknown')}")
            
            if rate.get('cancellation_deadline'):
                output_lines.append(f"Cancellation Deadline: {rate['cancellation_deadline']}")
            
            if rate.get('amenities'):
                output_lines.append(f"Amenities: {rate['amenities']}")
            
            if rate.get('description'):
                desc = rate['description'].replace('\n', ' ').strip()
                output_lines.append(f"Description: {desc}")
            
            if rate.get('raw_text') and rate.get('raw_text') != rate.get('description'):
                raw = rate['raw_text'].replace('\n', ' ').strip()
                output_lines.append(f"Raw Text: {raw}")
            
            output_lines.append(f"Source: {rate.get('source', 'direct_scraping')}")
            output_lines.append("")
        
        return '\n'.join(output_lines)

async def scrape_luma_rates(check_in: str, check_out: str, adults: int = 2, rooms: int = 1, 
                           currency: str = "USD", output_file: str = "luma_direct_rates.txt"):
    """Main function to scrape LUMA rates and save to file"""
    
    print(f"🏨 Scraping LUMA Hotel San Francisco rates")
    print(f"📅 Dates: {check_in} to {check_out}")
    print(f"👥 Adults: {adults}, Rooms: {rooms}")
    print(f"💰 Currency: {currency}")
    print(f"📄 Output file: {output_file}")
    print("=" * 60)
    
    scraper = LumaHotelScraper()
    
    try:
        # Scrape rates
        rates = await scraper.scrape_rates(check_in, check_out, adults, rooms, currency)
        
        if not rates:
            print("❌ No rates found")
            return []
        
        print(f"✅ Found {len(rates)} rates")
        
        # Format output
        formatted_output = scraper.format_rates_output(rates, check_in, check_out, adults, rooms, currency)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_output)
        
        print(f"✅ Rates exported to {output_file}")
        
        # Also create JSON version
        json_filename = output_file.replace('.txt', '.json')
        export_data = {
            "hotel_name": scraper.hotel_name,
            "hotel_code": scraper.hotel_code,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "rooms": rooms,
            "currency": currency,
            "total_offers": len(rates),
            "export_date": datetime.now().isoformat(),
            "source": "direct_luma_scraping",
            "offers": rates
        }
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Also exported JSON version to {json_filename}")
        
        return rates
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Scrape hotel rates from LUMA Hotels direct booking page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python luma_scraper.py 2025-11-11 2025-11-13 2 1 luma_direct_rates.txt
  python luma_scraper.py 2025-12-01 2025-12-03 1 2 luma_holiday_rates.txt
        """
    )
    
    parser.add_argument("check_in", help="Check-in date (YYYY-MM-DD)")
    parser.add_argument("check_out", help="Check-out date (YYYY-MM-DD)")
    parser.add_argument("adults", type=int, help="Number of adults")
    parser.add_argument("rooms", type=int, help="Number of rooms")
    parser.add_argument("output_file", help="Output filename (e.g., rates.txt)")
    parser.add_argument("--currency", default="USD", help="Currency code (default: USD)")
    
    return parser.parse_args()

async def main():
    """Main function with command line argument parsing"""
    args = parse_args()
    
    await scrape_luma_rates(
        check_in=args.check_in,
        check_out=args.check_out,
        adults=args.adults,
        rooms=args.rooms,
        currency=args.currency,
        output_file=args.output_file
    )

if __name__ == "__main__":
    asyncio.run(main())
