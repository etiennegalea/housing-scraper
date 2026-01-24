import re
import pandas as pd
from datetime import datetime
from funda_scraper import FundaScraper as BaseFundaScraper

class FundaScraper(BaseFundaScraper):
    """
    A wrapper around the base FundaScraper to ensure compatibility with the existing codebase.
    """
    def __init__(self, *args, **kwargs):
        # The library uses 'number_of_pages' instead of 'n_pages' in some versions,
        # but ymere_scraper.py calls it with n_pages. Let's handle both.
        if 'n_pages' in kwargs and 'number_of_pages' not in kwargs:
            kwargs['number_of_pages'] = kwargs.pop('n_pages')
        super().__init__(*args, **kwargs)

class preprocess:
    """
    Preprocessing utility functions for Funda data.
    """
    
    @staticmethod
    def clean_price(price_str):
        """Extract numerical price from string like '€ 1.250 p.m.' or '€ 450.000 k.k.'"""
        if pd.isna(price_str) or price_str == "na":
            return 0
        try:
            # Remove non-numeric characters except for the decimal point if it exists
            # In Dutch, thousands separator is '.' and decimal is ','
            # Usually prices in Funda are integer-like in the display string
            clean_str = re.sub(r'[^\d]', '', str(price_str))
            return int(clean_str) if clean_str else 0
        except ValueError:
            return 0

    @staticmethod
    def find_n_room(room_str):
        """Extract number of rooms from string like '3 kamers'"""
        if pd.isna(room_str) or room_str == "na":
            return 0
        try:
            match = re.search(r'(\d+)', str(room_str))
            return int(match.group(1)) if match else 0
        except (ValueError, AttributeError):
            return 0

    @staticmethod
    def find_n_bedroom(room_str):
        """Extract number of bedrooms. Usually formatted as '3 kamers (2 slaapkamers)'"""
        if pd.isna(room_str) or room_str == "na":
            return 0
        try:
            match = re.search(r'\((\d+)\s+slaapkamer', str(room_str))
            if match:
                return int(match.group(1))
            # Fallback for simple '2 slaapkamers'
            match = re.search(r'(\d+)\s+slaapkamer', str(room_str))
            return int(match.group(1)) if match else 0
        except (ValueError, AttributeError):
            return 0

    @staticmethod
    def find_n_bathroom(bathroom_str):
        """Extract number of bathrooms from string"""
        if pd.isna(bathroom_str) or bathroom_str == "na":
            return 0
        try:
            match = re.search(r'(\d+)', str(bathroom_str))
            return int(match.group(1)) if match else 0
        except (ValueError, AttributeError):
            return 0

    @staticmethod
    def clean_energy_label(label_str):
        """Clean energy label string, e.g., 'A+++' or 'B'"""
        if pd.isna(label_str) or label_str == "na":
            return "na"
        # Often it comes as 'A' or 'Energielabel A'
        match = re.search(r'([A-G][\+]{0,3})', str(label_str), re.IGNORECASE)
        return match.group(1).upper() if match else str(label_str).strip()

    @staticmethod
    def clean_living_area(area_str):
        """Extract living area numerical value"""
        if pd.isna(area_str) or area_str == "na":
            return 0
        try:
            clean_str = re.sub(r'[^\d]', '', str(area_str))
            return int(clean_str) if clean_str else 0
        except ValueError:
            return 0
