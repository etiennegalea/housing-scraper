import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path first to prioritize local modules
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

try:
    from funda_scraper_wrapper import FundaScraper, preprocess
    print("Successfully imported FundaScraper and preprocess from src/funda_scraper_wrapper.py")
except ImportError as e:
    print(f"Error importing: {e}")
    sys.exit(1)

def test_preprocessing():
    print("\n--- Testing Preprocessing Functions ---")
    
    # Test clean_price
    price_tests = [
        ("€ 1.250 p.m.", 1250),
        ("€ 450.000 k.k.", 450000),
        ("na", 0),
        (None, 0)
    ]
    for input_val, expected in price_tests:
        result = preprocess.clean_price(input_val)
        print(f"clean_price('{input_val}') -> {result} (Expected: {expected})")
        assert result == expected

    # Test find_n_room
    room_tests = [
        ("3 kamers", 3),
        ("5 kamers (3 slaapkamers)", 5),
        ("na", 0)
    ]
    for input_val, expected in room_tests:
        result = preprocess.find_n_room(input_val)
        print(f"find_n_room('{input_val}') -> {result} (Expected: {expected})")
        assert result == expected

    # Test find_n_bedroom
    bedroom_tests = [
        ("3 kamers (2 slaapkamers)", 2),
        ("2 slaapkamers", 2),
        ("na", 0)
    ]
    for input_val, expected in bedroom_tests:
        result = preprocess.find_n_bedroom(input_val)
        print(f"find_n_bedroom('{input_val}') -> {result} (Expected: {expected})")
        assert result == expected

    # Test clean_energy_label
    energy_tests = [
        ("Energielabel A+++", "A+++"),
        ("B", "B"),
        ("na", "na")
    ]
    for input_val, expected in energy_tests:
        result = preprocess.clean_energy_label(input_val)
        print(f"clean_energy_label('{input_val}') -> {result} (Expected: {expected})")
        assert result == expected

    print("Preprocessing tests passed!")

def test_scraper_wrapper():
    print("\n--- Testing Scraper Wrapper (Initialization) ---")
    try:
        # Mocking the base class would be complex without mock library, 
        # but we can try to initialize it and see if it handles n_pages.
        # This will fail if the actual funda_scraper library is not installed.
        scraper = FundaScraper(area="amsterdam", want_to="rent", n_pages=2)
        print(f"Successfully initialized FundaScraper wrapper with n_pages.")
        # We don't run scraper.run() here to avoid actual web requests in a test script 
        # unless intended, and we might lack dependencies.
    except Exception as e:
        print(f"Scraper initialization failed (possibly due to missing base library): {e}")

if __name__ == "__main__":
    test_preprocessing()
    test_scraper_wrapper()
