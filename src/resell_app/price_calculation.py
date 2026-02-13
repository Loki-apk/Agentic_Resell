"""
Price Calculation Utilities - Extract and analyze pricing data from evaluation results.

This module provides robust price parsing and statistical analysis:
- Parses various German price formats (e.g., "120 €", "199 € VB", "1.234,56 €")
- Handles German number formatting (dot for thousands, comma for decimal)
- Calculates min/max/median statistics
- Separates statistics for matched items vs all items

The PriceCalculator is designed to be conservative and handle common edge cases
like "VB" (Verhandlungsbasis = negotiable), whitespace, currency symbols, etc.
"""

from typing import Iterable, Dict, Any, List
import re
import statistics

# Regex pattern to extract numeric parts from price strings
# Matches sequences of digits, dots, and commas
_PRICE_RE = re.compile(r"[\d\.,]+")


def _parse_price(price_str: str) -> float:
    """
    Parse a German price string into a float value.
    
    Handles various formats commonly found on Kleinanzeigen:
    - "120 €" -> 120.0
    - "199 € VB" -> 199.0 (VB = Verhandlungsbasis = negotiable)
    - "1.234,56 €" -> 1234.56 (German format: dot thousands, comma decimal)
    - "1,234.56" -> 1234.56 (US format: comma thousands, dot decimal)
    - "1234" -> 1234.0
    
    Args:
        price_str: Price string to parse
        
    Returns:
        Parsed price as float
        
    Raises:
        ValueError: If string cannot be parsed as a price
    """
    # Validate input
    if not price_str or not isinstance(price_str, str):
        raise ValueError("invalid price")
    
    s = price_str.strip()
    
    # Remove common non-numeric tokens
    s = s.replace('\u20ac', '')  # Unicode euro sign
    s = s.replace('€', '')  # Regular euro sign
    s = s.replace('VB', '')  # VB = negotiable
    s = s.replace('\xa0', '')  # Non-breaking space
    s = s.strip()

    # Extract numeric part using regex
    m = _PRICE_RE.search(s)
    if not m:
        raise ValueError("no numeric part")
    num = m.group(0)

    # Handle German number format: 1.234,56 (dot thousands, comma decimal)
    if '.' in num and ',' in num:
        num = num.replace('.', '')  # Remove thousands separator
        num = num.replace(',', '.')  # Convert decimal separator to dot
    # If only comma present, treat as decimal separator
    elif ',' in num and '.' not in num:
        num = num.replace(',', '.')
    # else: keep as-is (either dot decimal or plain integer)

    # Convert to float
    try:
        return float(num)
    except Exception:
        raise ValueError("could not parse")


class PriceCalculator:
    """
    Price statistics calculator for evaluation results.
    
    This class processes evaluation payloads containing listings with prices
    and computes useful statistics for price recommendations.
    
    Features:
    - Robust price parsing (handles German and US formats)
    - Separate statistics for matched items vs all items
    - Min/max/median calculations
    - Graceful handling of unparseable prices
    """

    def __init__(self):
        """Initialize the price calculator."""
        pass

    def calculate_from_evaluation(self, evaluation_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute price statistics from an evaluation payload.
        
        Processes a list of evaluated listings and extracts price statistics.
        Calculates separate statistics for:
        1. All items with parseable prices
        2. Only items marked as matches (is_match=True)
        
        Args:
            evaluation_payload: Dict containing:
                - individual_results_evaluation: List of evaluated items
                  Each item should have:
                  - price or price_str: Price string
                  - is_match: Boolean indicating if item matches product (optional)
                  
        Returns:
            Dict with structure:
            {
                "count_prices_parsed": Number of successfully parsed prices,
                "count_listings": Total number of listings in input,
                "price_statistics_all": {
                    "min": Minimum price across all items,
                    "max": Maximum price across all items,
                    "median": Median price across all items
                } or None if no prices,
                "price_statistics_matches": {
                    "min": Minimum price for matched items only,
                    "max": Maximum price for matched items only,
                    "median": Median price for matched items only
                } or None if no matched prices
            }
        """
        # Extract list of items from payload
        items = evaluation_payload.get('individual_results_evaluation', []) or []

        # Initialize price collections
        prices: List[float] = []  # All parseable prices
        prices_from_matches: List[float] = []  # Prices from matched items only
        parsed_count = 0  # Track how many prices we successfully parsed

        # Process each item
        for it in items:
            # Try to get price string (check both possible field names)
            price_str = it.get('price') or it.get('price_str') or ''
            try:
                # Attempt to parse price
                p = _parse_price(str(price_str))
                prices.append(p)
                parsed_count += 1
                
                # If item is marked as a match, also add to match prices
                if it.get('is_match') is True:
                    prices_from_matches.append(p)
            except Exception:
                # Skip items with unparseable prices
                continue

        # Initialize statistics structure
        stats: Dict[str, Any] = {
            'count_prices_parsed': parsed_count,
            'count_listings': len(items),
            'price_statistics_all': None,
            'price_statistics_matches': None,
        }

        # Calculate statistics for all items (if any prices were parsed)
        if prices:
            stats['price_statistics_all'] = {
                'min': round(min(prices), 2),
                'max': round(max(prices), 2),
                'median': round(statistics.median(prices), 2)
            }

        # Calculate statistics for matched items only (if any match prices exist)
        if prices_from_matches:
            stats['price_statistics_matches'] = {
                'min': round(min(prices_from_matches), 2),
                'max': round(max(prices_from_matches), 2),
                'median': round(statistics.median(prices_from_matches), 2)
            }

        return stats