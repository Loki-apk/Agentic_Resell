"""
ResellWorkflow - Core workflow orchestrator for the resell price analysis pipeline.

This module coordinates the entire analysis process:
1. Phase 1: Image analysis and initial query generation
2. Phase 2: Iterative refinement loop (up to 3 iterations)
   - Query refinement based on feedback
   - Market scraping for similar items
   - Evaluation of search results
   - Price calculation from matched listings
3. Result finalization and output generation

The workflow implements an intelligent feedback loop that improves search results
through multiple iterations until sufficient matching items are found.
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from resell_app.price_calculation import PriceCalculator

# Increase recursion limit to handle deep nested operations in CrewAI
# This prevents RecursionError during complex agent interactions
sys.setrecursionlimit(5000)

class ResellWorkflow:
    """
    Orchestrates the complete resell price analysis workflow.
    
    This class manages the iterative process of:
    - Analyzing product images
    - Generating and refining search queries
    - Triggering market scraping
    - Evaluating search results
    - Calculating price statistics
    - Finalizing recommendations
    
    Attributes:
        app: ResellApp instance containing all crews and agents
        market_search: MarketSearch tool for scraping Kleinanzeigen
        calc: PriceCalculator for computing price statistics
        project_root: Root directory of the project
        out_dir: Output directory for this run's results (timestamped)
        scraper_file: Path to the scraped data JSON file
    """
    
    def __init__(self, app):
        """
        Initialize the workflow with the ResellApp instance.
        
        Args:
            app: ResellApp instance containing crews, agents, and tools
        """
        self.app = app  # Main application instance with all crews
        self.market_search = getattr(app, 'market_search', None)  # Scraping tool
        self.calc = PriceCalculator()  # Price statistics calculator
        
        # Set up project paths using Path for cross-platform compatibility
        # __file__ is src/resell_app/workflow.py
        # project_root is 3 levels up: src/resell_app/workflow.py -> src/resell_app -> src -> root
        project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        
        # Create timestamped output directory for this run's results
        self.out_dir = project_root / "Output_Folder" / f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        
        # Path where scraped Kleinanzeigen data will be stored
        self.scraper_file = project_root / "Kleinanzeigen_Data" / "kleinanzeigen_items.json"
        
        # Debug output to verify correct path resolution
        print(f"[DEBUG] Workflow will look for data at: {self.scraper_file.resolve()}")

    def _save(self, filename, data):
        """
        Save data to a JSON file in the output directory.
        
        Args:
            filename: Name of the file to save (e.g., "image_analysis.json")
            data: Python dict/list to serialize as JSON
        """
        with open(self.out_dir / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _parse(self, raw):
        """
        Parse agent output, handling various formats (JSON strings, markdown-wrapped JSON).
        
        Agent outputs may come wrapped in markdown code blocks (```json ... ```)
        or as plain strings. This method attempts to extract and parse JSON.
        
        Args:
            raw: Raw output from agent (string or dict)
            
        Returns:
            Parsed dict/list if valid JSON, otherwise the original string
        """
        try: 
            # Remove markdown code block markers if present
            cleaned = str(raw).strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned)
        except: 
            # If parsing fails, return as-is (may be plain text response)
            return str(raw).strip()

    def run(self, inputs):
        """
        Execute the complete resell price analysis workflow.
        
        WORKFLOW PHASES:
        ===============
        PHASE 1: Initial Analysis
        - Analyze product images using vision AI
        - Extract product attributes (name, brand, model, condition, etc.)
        - Generate initial search query based on image analysis
        - Save image analysis results
        
        PHASE 2: Iterative Refinement Loop (up to 3 iterations)
        For each iteration:
        1. Generate/refine search query (using feedback from previous iteration)
        2. Run market scraper to find similar items on Kleinanzeigen
        3. Evaluate scraped results for matches
        4. Calculate price statistics from matched items
        5. Check if results are sufficient (>=50% match rate, >=3 matches)
        6. If not sufficient, generate feedback for next iteration
        
        Args:
            inputs: Dict containing:
                - image_urls: List of product image URLs (REQUIRED)
                - topic: General topic context
                - current_year: Current year for temporal context
                - Other metadata and configuration
        
        Returns:
            dict: Final results containing:
                - success: Boolean indicating if sufficient matches were found
                - best_iteration: Iteration number with best results
                - item_description: Extracted product description
                - best_result: Best iteration's complete results
                - history: List of all iteration results
        """
        print(f"{'='*60}\nSTARTING PRODUCT PRICE ANALYSIS\n{'='*60}")
        
        # ========================================
        # PHASE 1: IMAGE ANALYSIS & INITIAL QUERY
        # ========================================
        try:
            # Execute the first crew: Image Analyzer + Query Generator
            # This runs two agents sequentially:
            # 1. Image Analyzer: Analyzes product images to extract attributes
            # 2. Query Generator: Creates German search query based on attributes
            res_p1 = self.app.analysis_and_query_crew().kickoff(inputs={
                **inputs, 
                "iteration": 1,  # First iteration
                "image_analysis": "Context",  # Placeholder, will be replaced
                "feedback": "None"  # No feedback yet
            })
            
            # Extract and parse image analysis results from first task output
            img_analysis = self._parse(res_p1.tasks_output[0].raw)
            
            # Save image analysis for later reference
            self._save("image_analysis.json", img_analysis)
            
        except RecursionError as e:
            # Handle recursion errors gracefully (can occur with complex agent interactions)
            print(f"\n[!] Recursion Error in Image Analysis: {str(e)[:100]}")
            return {
                "success": False, 
                "error": "maximum recursion depth exceeded", 
                "item_description": None, 
                "best_iteration": 0, 
                "best_result": {}, 
                "history": []
            }
        except Exception as e:
            # Handle any other critical errors in Phase 1
            print(f"\n[!] Critical Error in Phase 1: {str(e)[:100]}")
            return {
                "success": False, 
                "error": str(e)[:200], 
                "item_description": None, 
                "best_iteration": 0, 
                "best_result": {}, 
                "history": []
            }
        
        # CHECK FOR IMAGE ANALYSIS ERRORS - STOP IF FOUND
        # If images are inconsistent or invalid, there's no point continuing
        if isinstance(img_analysis, dict) and "error" in img_analysis:
            print(f"\n[!] Image Analysis Failed: {img_analysis.get('error')}")
            print(f"[!] Stopping workflow - inconsistent or invalid images")
            return {
                "success": False, 
                "error": img_analysis.get("error"), 
                "item_description": None, 
                "best_iteration": 0, 
                "best_result": {}, 
                "history": []
            }
        
        # Initialize tracking variables for the iteration loop
        history = []  # Store results from each iteration
        best_res = {"match_percentage": 0}  # Track best result across iterations
        current_query_json = res_p1.tasks_output[1].raw  # Initial query from Phase 1
        feedback = "None"  # No feedback for first iteration
        
        # Accumulator for valid matches across all iterations
        # Using dict to automatically deduplicate by ID
        all_unique_matches = {} 
        
        # ========================================
        # PHASE 2: ITERATIVE REFINEMENT LOOP
        # ========================================
        # Run up to 3 iterations to find sufficient matching items
        for i in range(1, 4): 
            print(f"\n--- Iteration {i} ---")
            
            # ----------------------------------
            # STEP 1: Query Generation/Refinement
            # ----------------------------------
            if i > 1:
                # For iterations 2+, regenerate query based on feedback from previous iteration
                try:
                    res_gen = self.app.query_regeneration_crew().kickoff(inputs={
                        **inputs, 
                        "iteration": i, 
                        "feedback": feedback,  # Feedback from evaluator about previous query
                        "image_analysis": json.dumps(img_analysis)  # Include image analysis context
                    })
                    current_query_json = res_gen.raw
                except RecursionError:
                    print(f"[!] Recursion error in query generation - using previous query")
                    continue  # Skip this iteration, use previous query
                except Exception as e:
                    print(f"[!] Error in query generation: {str(e)[:100]}")
                    continue  # Skip this iteration

            # Parse the query from JSON response
            query_data = self._parse(current_query_json)
            # Extract search query string (handle different response formats)
            query = query_data.get("search_query", str(query_data)) if isinstance(query_data, dict) else str(query_data)
            print(f"Query: {query}")

            # ----------------------------------
            # STEP 2: Run Market Scraper
            # ----------------------------------
            if self.market_search:
                try: 
                    # Scrape Kleinanzeigen for items matching the query
                    # min_items=10: Try to get at least 10 listings for statistical validity
                    result = self.market_search.run(search_query=query, min_items=10)
                    print(f"[Market Search Result] {result}")
                except Exception as e: 
                    print(f"Scraper Error: {e}")

            # ----------------------------------
            # STEP 3: Verify Data & Evaluate
            # ----------------------------------
            # Wait briefly for scraper to finish writing file
            time.sleep(1)
            
            # Check if scraped data file exists
            if not self.scraper_file.exists():
                print(f"[!] Data file not found at: {self.scraper_file.resolve()}")
                print("No data found. Retrying.")
                continue  # Skip to next iteration
            
            # Verify file has content before proceeding
            try:
                with open(self.scraper_file, 'r', encoding='utf-8') as f:
                    scraped_data = json.load(f)
                    # Check if data is empty or invalid
                    if not scraped_data or (isinstance(scraped_data, list) and len(scraped_data) == 0):
                        print(f"[!] Data file is empty at: {self.scraper_file.resolve()}")
                        print("No valid items found. Retrying.")
                        continue  # Skip to next iteration
                    print(f"[✓] Found {len(scraped_data)} items in scraped data")
            except Exception as e:
                print(f"[!] Error reading scraped data: {e}")
                continue  # Skip to next iteration

            # Run evaluation crew to compare scraped items with product image
            try:
                eval_res = self.app.evaluation_crew().kickoff(inputs={
                    **inputs,
                    "image_analysis": json.dumps(img_analysis),  # Product description
                    "search_query": query,  # Current query for context
                    "scraped_data_file": str(self.scraper_file),  # Path to scraped data
                    "feedback": feedback  # Previous feedback (if any)
                })
                
                # Parse evaluation results - agent includes metrics via EvaluationMetricsTool
                eval_data = self._parse(eval_res.raw)
            except RecursionError:
                print(f"[!] Recursion error in evaluation - skipping iteration")
                continue
            except Exception as e:
                print(f"[!] Error in evaluation: {str(e)[:100]}")
                continue
                
            # Ensure eval_data is a dict with expected structure
            if not isinstance(eval_data, dict): 
                eval_data = {"individual_results_evaluation": []}

            # ----------------------------------
            # STEP 4: ACCUMULATE MATCHES & CALCULATE PRICES
            # ----------------------------------
            # Extract matched items from current evaluation
            # is_match or match_status both indicate a positive match
            current_matches = [
                item for item in eval_data.get("individual_results_evaluation", []) 
                if item.get("is_match") or item.get("match_status")
            ]
            
            # Add new matches to cumulative collection (dict auto-deduplicates by ID)
            for m in current_matches: 
                all_unique_matches[str(m.get("id"))] = m
            
            # Calculate price statistics from all accumulated matches across iterations
            stats = self.calc.calculate_from_evaluation({
                "individual_results_evaluation": list(all_unique_matches.values())
            })
            
            # Extract metrics from evaluation response
            # Agent should provide these via EvaluationMetricsTool
            count_positive = eval_data.get("count_positive")  # Number of matched items
            count_negative = eval_data.get("count_negative")  # Number of non-matches
            total_listings = eval_data.get("total_listings")  # Total items evaluated
            match_pct = eval_data.get("match_percentage", 0)  # Percentage of matches
            
            # Fallback: Calculate metrics manually if agent didn't provide them
            if count_positive is None:
                count_positive = len([e for e in eval_data.get("individual_results_evaluation", []) if e.get("is_match")])
            if count_negative is None:
                count_negative = len([e for e in eval_data.get("individual_results_evaluation", []) if not e.get("is_match")])
            if total_listings is None:
                total_listings = count_positive + count_negative
            
            # Display iteration metrics
            print(f"Match: {match_pct}% | Positive: {count_positive} | Negative: {count_negative} | Total: {total_listings}")

            # ----------------------------------
            # STEP 5: Save Results & Prepare Next Iteration
            # ----------------------------------
            
            # Compile complete results for this iteration
            step_res = {
                "iteration": i, 
                "query": query, 
                "evaluation": eval_data, 
                "count_positive": count_positive,
                "count_negative": count_negative,
                "total_listings": total_listings,
                "match_percentage": match_pct, 
                "price_statistics": stats,  # Price ranges and median
            }
            
            # Save iteration results to file
            self._save(f"evaluation_{i}.json", step_res)
            history.append(step_res)

            # Track best iteration (highest match percentage)
            if match_pct > best_res.get("match_percentage", -1): 
                best_res = step_res
                
            # Check if results are sufficient to stop iterating
            # "sufficient" means >=50% match rate AND at least 3 positive matches
            if eval_data.get("overall_sufficiency") == "sufficient": 
                return self._finalize(True, i, best_res, history, img_analysis)
            
            # Extract feedback for next iteration
            # Evaluator suggests query improvements based on current results
            feedback = eval_data.get("query_improvement_feedback", "None")

        # If we've exhausted all 3 iterations without reaching "sufficient" status
        # Return best result found across all iterations
        return self._finalize(False, best_res.get("iteration", 0), best_res, history, img_analysis)

    def _finalize(self, success, iter, best, hist, img_analysis):
        """
        Finalize workflow results and generate output files.
        
        This method:
        1. Compiles final results from best iteration
        2. Extracts product information from image analysis
        3. Extracts price statistics from best iteration
        4. Generates item_price.json summary (both in output dir and project root)
        5. Generates final_result.json with complete workflow data
        
        Args:
            success: Boolean indicating if sufficient matches were found
            iter: Iteration number with best results
            best: Best iteration's complete result data
            hist: List of all iteration results
            img_analysis: Image analysis results from Phase 1
            
        Returns:
            dict: Final consolidated results including:
                - success: Whether sufficient matches were found
                - best_iteration: Iteration with best results
                - item_description: Product description from image
                - best_result: Complete best iteration data
                - history: All iterations' results
        """
        # Compile main results object
        final = {
            "success": success,  # True if sufficient matches found, False if iterations exhausted
            "best_iteration": iter,  # Iteration number with highest match percentage
            "item_description": img_analysis.get("description") if isinstance(img_analysis, dict) else None,
            "best_result": best,  # Complete data from best iteration
            "history": hist  # All iterations for analysis
        }
        
        # Extract product information from image analysis
        # Handle different possible field names in image analysis response
        if isinstance(img_analysis, dict):
            item_name = img_analysis.get("item_name") or img_analysis.get("name") or img_analysis.get("title")
            condition = img_analysis.get("condition")
            description = img_analysis.get("description") or img_analysis.get("item_description")
        else:
            # Fallback if image analysis failed
            item_name = None
            condition = None
            description = None

        # Extract price statistics from best iteration
        price_stats = (best or {}).get("price_statistics") or {}
        # Prefer statistics from matched items; fall back to all items if no matches
        stats_src = price_stats.get("price_statistics_matches") or price_stats.get("price_statistics_all") or {}
        min_v = stats_src.get("min")  # Minimum price found
        max_v = stats_src.get("max")  # Maximum price found
        median = stats_src.get("median")  # Median price (recommended)
        
        # Build price range array [min, max] only if both values exist
        range_v = [min_v, max_v] if min_v is not None and max_v is not None else []

        # Create summary output with key information for end users
        item_price = {
            "item_name": item_name,  # Product name from image
            "condition": condition,  # Condition assessment from image
            "description": description,  # Detailed description from image
            "range": range_v,  # Price range [min, max] in euros
            "median": median  # Recommended price (median of matched items)
        }
        
        # Save summary to output directory
        self._save("item_price.json", item_price)
        
        # Also save summary to project root for easy access
        try:
            with open(self.project_root / "item_price.json", "w", encoding="utf-8") as f:
                json.dump(item_price, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Ignore errors saving to root (e.g., permission issues)
            
        # Save complete final results to output directory
        self._save("final_result.json", final)
        
        return final