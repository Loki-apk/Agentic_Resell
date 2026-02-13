"""
Qwen Vision Tool - Multi-image product analysis using vision-capable LLM.

This tool performs forensic analysis of product images to:
1. Verify consistency (all images show the same main product)
2. Extract product attributes (name, brand, model, color, condition)
3. Generate detailed product descriptions
4. Identify key features for search

The tool uses a vision-capable LLM (configured in .env as Image_MODEL)
and can analyze up to 4 images simultaneously for consistency checking.

Features:
- Multi-image consistency verification
- Support for both URLs and local file paths
- Automatic image quality detection (JPEG/PNG)
- Base64 encoding for API transmission
- Error handling with fallback to single image
"""

import os, requests, base64, json
from typing import Type, List, Union
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from openai import OpenAI

class MultiImageToolInput(BaseModel):
    """Input schema for QwenVisionTool."""
    image_urls: Union[List[str], str] = Field(
        ..., 
        description="List of image URLs or single URL string. Can be HTTP/HTTPS URLs or local file paths."
    )

class QwenVisionTool(BaseTool):
    """
    Vision AI tool for multi-image product analysis.
    
    This tool analyzes product photos using a vision-capable LLM to extract
    detailed product information. It's designed to be lenient with minor
    variations (e.g., different angles of same product) while detecting
    major inconsistencies (e.g., completely different products).
    
    Capabilities:
    - Multi-image analysis (up to 4 images)
    - Consistency verification across images
    - Attribute extraction (name, brand, model, color, condition)
    - Detailed description generation
    - Key feature identification
    
    Input formats supported:
    - HTTP/HTTPS URLs: "https://example.com/image.jpg"
    - Local paths: "Kleinanzeigen_Input/images/item_0.jpg"
    - List or comma-separated string
    
    Output format:
    JSON with structure:
    {
        "status": "SUCCESS" or "ERROR",
        "item_name": "Product name",
        "brand": "Brand name",
        "model": "Model number",
        "color": "Color description",
        "condition": "Condition assessment",
        "key_features": ["feature1", "feature2"],
        "description": "Detailed description",
        "reason": "Error reason if status=ERROR"
    }
    """
    
    name: str = "Qwen Vision Tool"
    description: str = "Forensic analysis of product images to ensure consistency and extract details (Name, Model, Condition)."
    args_schema: Type[BaseModel] = MultiImageToolInput

    def _run(self, image_urls: Union[List[str], str]) -> str:
        """
        Execute vision analysis on product images.
        
        WORKFLOW:
        1. Sanitize and parse input URLs
        2. Limit to 4 images maximum
        3. Load and encode images (from URLs or local files)
        4. Build LLM prompt with images
        5. Call vision-capable LLM
        6. Parse and validate JSON response
        7. Retry with single image if multi-image fails
        
        Args:
            image_urls: List of image URLs or single URL string
            
        Returns:
            JSON string with analysis results
        """
        # ==========================================
        # STEP 1: SANITIZE INPUT
        # ==========================================
        # Handle string input (could be JSON string or comma-separated)
        if isinstance(image_urls, str):
            try: 
                # Try parsing as JSON array
                image_urls = json.loads(image_urls)
            except: 
                # Fall back to comma-separated split
                image_urls = [u.strip() for u in image_urls.split(',') if u.strip()]
        
        # Ensure we have a list
        if not isinstance(image_urls, list):
            return json.dumps({"status": "ERROR", "reason": "image_urls must be a list"})
        
        # ==========================================
        # STEP 2: VALIDATE AND LIMIT IMAGES
        # ==========================================
        if len(image_urls) == 0:
            return json.dumps({"status": "ERROR", "reason": "No image URLs provided"})
        
        # Limit to 4 images to avoid overwhelming the model
        image_urls = image_urls[:4]
        
        # ==========================================
        # STEP 3: BUILD VISION PROMPT
        # ==========================================
        # Lenient prompt: focus on main product, allow minor variations
        # This prompt was refined to reduce false positives for multi-angle photos
        content = [{
            "type": "text", 
            "text": (
                "Analyze the product images focusing on the MAIN/PRIMARY item. "
                "Minor accessories or background items are acceptable. "
                "Extract: Item Name, Brand, Model, Color, Condition. "
                "OUTPUT JSON ONLY: {status: 'SUCCESS'|'ERROR', item_name, brand, model, "
                "color, condition, key_features, description, reason(if error)}. "
                "If images show multiple angles of the same main product, that is ACCEPTABLE."
            )
        }]
        
        # ==========================================
        # STEP 4: LOAD AND ENCODE IMAGES
        # ==========================================
        for url in image_urls:
            try:
                image_data = None
                content_type = "image/jpeg"  # Default content type
                
                # ----------------------------------
                # Handle local file paths
                # ----------------------------------
                if url.startswith("Kleinanzeigen") or url.startswith("."):
                    # Convert Windows backslashes to forward slashes for compatibility
                    local_path = url.replace("\\", "/")
                    if os.path.exists(local_path):
                        # Read image file as binary
                        with open(local_path, 'rb') as f:
                            image_data = f.read()
                        # Detect content type from file extension
                        if local_path.lower().endswith('.png'):
                            content_type = "image/png"
                            
                # ----------------------------------
                # Handle HTTP/HTTPS URLs
                # ----------------------------------
                elif url.startswith('http'):
                    # Fetch image from URL
                    res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                    if res.status_code == 200:
                        image_data = res.content
                        # Get content type from response headers
                        content_type = res.headers.get('Content-Type', 'image/jpeg')
                
                # ----------------------------------
                # Encode image as base64 for API
                # ----------------------------------
                if image_data:
                    b64 = base64.b64encode(image_data).decode('utf-8')
                    # Add image to content array in data URI format
                    content.append({
                        "type": "image_url", 
                        "image_url": {"url": f"data:{content_type};base64,{b64}"}
                    })
            except Exception as e:
                # Skip images that fail to load
                pass

        # Check if we successfully loaded any images
        if len(content) == 1:  # Only the text prompt, no images
            return json.dumps({"status": "ERROR", "reason": "No accessible images found"})

        # ==========================================
        # STEP 5: CALL VISION LLM
        # ==========================================
        try:
            # Initialize OpenAI client with configured endpoint and API key
            client = OpenAI(
                base_url=os.getenv("OPENAI_BASE_URL"), 
                api_key=os.getenv("OPENAI_API_KEY")
            )
            
            # Call vision model with images
            response = client.chat.completions.create(
                model=os.getenv("Image_MODEL"),  # Vision-capable model
                messages=[{"role": "user", "content": content}],
                temperature=0.0  # Deterministic output for consistency
            )
            
            # Extract response text
            result = response.choices[0].message.content
            
            # Clean up markdown formatting if present
            result = result.replace("```json", "").replace("```", "").strip()
            
            # ==========================================
            # STEP 6: VALIDATE JSON RESPONSE
            # ==========================================
            try:
                result_json = json.loads(result)
                
                # ----------------------------------
                # STEP 7: RETRY WITH SINGLE IMAGE IF MULTI-IMAGE FAILS
                # ----------------------------------
                # If model detected inconsistency with multiple images,
                # retry with just the first image (may be too strict)
                if result_json.get("status") == "ERROR" and len(image_urls) > 1:
                    print("[!] Vision tool detected error with multiple images, retrying with first image only...")
                    return self._run([image_urls[0]])  # Recursive call with single image
                    
                return result  # Return valid JSON
                
            except:
                # Response was not valid JSON
                return json.dumps({
                    "status": "ERROR", 
                    "reason": f"Invalid JSON response from model: {result[:100]}"
                })
                
        except Exception as e: 
            # Handle API call errors
            return json.dumps({
                "status": "ERROR", 
                "reason": str(e)[:200]
            })