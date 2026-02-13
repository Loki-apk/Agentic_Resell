"""
MarketSearch - Web scraper for Kleinanzeigen.de marketplace.

This module implements a lightweight web scraper that:
1. Searches Kleinanzeigen for items matching a query
2. Extracts listing details (title, price, description, images)
3. Saves results to JSON file (no local image downloads)

Scraping approach:
- Uses requests + BeautifulSoup (no Selenium/browser)
- Respects rate limits with random delays
- Handles pagination to collect sufficient listings
- Extracts remote image URLs (does not download images)

Important notes:
- Conservative scraping limits to avoid abuse
- User-Agent header mimics browser behavior
- Results saved to Kleinanzeigen_Data/kleinanzeigen_items.json
"""

import os, time, random, json, requests
from pathlib import Path
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import Field
from typing import Dict, Any


class MarketSearch(BaseTool):
    """
    Kleinanzeigen.de Scraper Tool - Search and extract item details.

    This tool performs lightweight web scraping of Kleinanzeigen marketplace:
    - Searches for items matching a query
    - Collects listing URLs from search results pages
    - Extracts detailed information from each listing
    - Saves data to JSON file (does NOT download images)
    
    Features:
    - Pagination support (up to max_pages)
    - Random delays to avoid rate limiting
    - User-Agent spoofing for browser-like requests
    - Atomic file writing (temp file + rename)
    - Graceful error handling for failed listings
    
    Limitations:
    - Simple HTTP requests only (no JavaScript execution)
    - Conservative limits to prevent abuse
    - No image downloading (only collects URLs)
    """

    name: str = "Market_Search"
    description: str = "Search and scrape item details from Kleinanzeigen.de (JSON Only)."
    output_folder: str = Field(default="Kleinanzeigen_Data", description="Folder to save results")

    # Kleinanzeigen base URL
    BASE_URL: str = "https://www.kleinanzeigen.de"
    
    # HTTP headers to mimic browser requests and avoid blocking
    HEADERS: dict = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de,en-US;q=0.7,en;q=0.3",  # German preferred language
    }

    def _run(self, search_query: str = "elektronik", min_items: int = 20) -> str:
        """
        Execute the scraping process.
        
        WORKFLOW:
        1. Setup output folder
        2. Collect listing URLs from search results pages (with pagination)
        3. Extract details from each listing page
        4. Save results to JSON file (atomic write)
        
        Args:
            search_query: German search term (e.g., "smartphone samsung", "fahrrad")
            min_items: Minimum number of items to collect (will try to reach this number)
            
        Returns:
            Success/error message string
        """
        # ==========================================
        # STEP 1: SETUP OUTPUT FOLDER
        # ==========================================
        # Use absolute path for consistency across different execution contexts
        # __file__ is src/resell_app/market_search.py
        # project root is 3 levels up
        abs_output_folder = Path(__file__).parent.parent.parent / self.output_folder
        print(f"DEBUG: __file__ = {__file__}")
        print(f"DEBUG: abs_output_folder = {abs_output_folder}")

        # Create folder if it doesn't exist
        abs_output_folder.mkdir(parents=True, exist_ok=True)

        # ==========================================
        # STEP 2: INITIALIZATION
        # ==========================================
        # Ensure we request at least 5 items
        min_items = max(5, min_items)
        dataset = []  # Will store all extracted listings
        item_links = set()  # Set to automatically deduplicate URLs

        try:
            print(f"--- Scraping '{search_query}' (Target: {min_items}) ---")

            # ==========================================
            # STEP 3: COLLECT LISTING URLS (WITH PAGINATION)
            # ==========================================
            page = 1  # Start at first page
            max_pages = 10  # Safety limit to prevent infinite scraping
            
            # Loop through search result pages until we have enough links
            while len(item_links) < min_items and page <= max_pages:
                # Construct search URL with pagination
                # Kleinanzeigen URL format: /s-{query}/k0?page={N}
                url = f"{self.BASE_URL}/s-{search_query.replace(' ', '-')}/k0?page={page}"

                try:
                    # Fetch search results page
                    resp = requests.get(url, headers=self.HEADERS, timeout=10)
                    if resp.status_code != 200:
                        print(f"DEBUG: Page {page} returned status {resp.status_code}")
                        break  # Stop if we get error response

                    # Parse HTML
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # Find all listing cards (each search result is an <article class="aditem">)
                    articles = soup.select('article.aditem')

                    if not articles:
                        print(f"DEBUG: No articles found on page {page}")
                        break  # No more results, stop pagination

                    # Extract links from each article
                    for art in articles:
                        # Find the main link within the article
                        link_tag = art.select_one('.aditem-main a')
                        if link_tag and link_tag.get('href'):
                            # Construct full URL
                            full_link = self.BASE_URL + link_tag['href']
                            # Filter for actual item pages (not category pages)
                            if '/s-anzeige/' in full_link:
                                item_links.add(full_link)
                                # Stop if we've reached target
                                if len(item_links) >= min_items:
                                    break

                    print(f"DEBUG: Page {page} - Total links: {len(item_links)}")

                    # Exit if we have enough links
                    if len(item_links) >= min_items:
                        break

                    # Move to next page
                    page += 1
                    
                    # Random delay between page requests (1-2 seconds)
                    time.sleep(random.uniform(1.0, 2.0))

                except Exception as e:
                    print(f"DEBUG: Error on page {page}: {type(e).__name__}")
                    break  # Stop pagination on error

            print(f"Collected {len(item_links)} links. Starting extraction...")

            # ==========================================
            # STEP 4: EXTRACT DETAILS FROM EACH LISTING
            # ==========================================
            # Limit to requested number of items
            target_links = list(item_links)[:min_items]

            for i, link in enumerate(target_links):
                try:
                    # Fetch listing detail page
                    resp = requests.get(link, headers=self.HEADERS, timeout=10)
                    if resp.status_code != 200:
                        continue  # Skip this listing if request fails

                    # Parse listing page HTML
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # Extract unique ID from URL (last segment after dash)
                    item_id = link.split('/')[-1].split('-')[-1] if '-' in link else f"item_{i}"

                    # ----------------------------------
                    # Extract Title
                    # ----------------------------------
                    title_elem = soup.select_one('#viewad-title')
                    if not title_elem:
                        print(f"DEBUG: Failed to find title for {link} - Skipping.")
                        continue  # Skip listings without titles

                    title_text = title_elem.text.strip()

                    # ----------------------------------
                    # Extract Price
                    # ----------------------------------
                    price_elem = soup.select_one('#viewad-price')
                    price_text = price_elem.text.strip() if price_elem else "N/A"

                    # ----------------------------------
                    # Extract Description
                    # ----------------------------------
                    desc_elem = soup.select_one('#viewad-description-text')
                    description_text = desc_elem.get_text(separator="\n").strip() if desc_elem else ""

                    # ----------------------------------
                    # Extract Image URLs (DO NOT DOWNLOAD)
                    # ----------------------------------
                    imgs = []
                    
                    # Try to find images in gallery
                    for img in soup.select('.galleryimage-element img'):
                        src = img.get('data-src') or img.get('src')  # Try both attributes
                        if src:
                            imgs.append(src)

                    # Fallback: try main image if no gallery images found
                    if not imgs:
                        main_img = soup.select_one('#viewad-image')
                        if main_img:
                            src = main_img.get('src')
                            if src:
                                imgs.append(src)

                    # ----------------------------------
                    # Process Image URLs (upgrade quality, deduplicate)
                    # ----------------------------------
                    remote_image_urls = []
                    for url in set(imgs):  # set() removes duplicates
                        if url:
                            # Upgrade to higher quality version (replace thumbnail with full size)
                            # $_35.JPG = small thumbnail, $_57.JPG = medium, $_59.JPG = large
                            hq_url = url.replace("$_35.JPG", "$_59.JPG").replace("$_57.JPG", "$_59.JPG")
                            remote_image_urls.append(hq_url)

                    # ----------------------------------
                    # Save Item to Dataset
                    # ----------------------------------
                    dataset.append({
                        "id": item_id,  # Unique identifier
                        "title": title_text,  # Listing title
                        "price": price_text,  # Price string (e.g., "120 €", "VB")
                        "description": description_text,  # Full description text
                        "url": link,  # Link to original listing
                        "local_images": [],  # No local downloads
                        "remote_images": remote_image_urls  # List of image URLs
                    })
                    
                    print(f"[{i+1}/{len(target_links)}] Extracted: {item_id}")

                    # Random delay between item requests (0.5-1.5 seconds)
                    time.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    print(f"Error processing {link}: {e}")
                    # Continue to next item on error

            # ==========================================
            # STEP 5: SAVE JSON (ATOMIC WRITE)
            # ==========================================
            # Use atomic write pattern: write to temp file, then rename
            # This prevents corruption if script is interrupted during write
            json_file = abs_output_folder / "kleinanzeigen_items.json"
            tmp_file = abs_output_folder / "kleinanzeigen_items.tmp.json"
            
            # Write to temporary file
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(dataset, f, indent=4, ensure_ascii=False)
            
            # Atomically replace old file with new file
            tmp_file.replace(json_file)

            return f"Successfully scraped {len(dataset)} items. JSON saved to {abs_output_folder}"

        except Exception as e:
            return f"Error: {str(e)}"

    # Backwards-compatible wrapper method
    def run(self, search_query: str = "elektronik", min_items: int = 20) -> str:
        """
        Public interface for running the scraper.
        
        This method maintains backwards compatibility and provides
        a cleaner API for external callers.
        
        Args:
            search_query: German search term
            min_items: Minimum items to collect
            
        Returns:
            Status message string
        """
        return self._run(search_query=search_query, min_items=min_items)
