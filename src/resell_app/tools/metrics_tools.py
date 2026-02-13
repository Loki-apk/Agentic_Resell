"""
Evaluation Metrics Tool - Calculate search quality metrics for evaluated listings.

This tool processes evaluation results from the search_list_evaluator agent
and computes key metrics:
- Count of positive matches (items that match the product)
- Count of negative matches (items that don't match)
- Match percentage
- Overall sufficiency assessment

Sufficiency criteria:
- Match percentage >= 50%
- At least 3 positive matches

Note: This tool is intentionally separate from price calculation logic.
It only evaluates search quality, not pricing accuracy.
"""

import json
from typing import List, Dict, Union, Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class MetricsToolInput(BaseModel):
    """Input schema for EvaluationMetricsTool."""
    evaluations: Union[List[Dict], str] = Field(
        ..., 
        description="List of evaluated items or JSON string. Each item should have 'is_match' or 'match_status' field."
    )

class EvaluationMetricsTool(BaseTool):
    """
    Tool for computing search evaluation metrics.

    This tool calculates quality metrics for search results:
    - Positive/negative match counts
    - Match percentage
    - Sufficiency assessment (is this good enough?)
    
    Used by the search_list_evaluator agent to quantify result quality
    and determine if more iterations are needed.
    
    Intentionally does NOT include price benchmarking or accuracy calculations.
    """
    name: str = "Evaluation Metrics Calculator"
    description: str = (
        "Compute search-evaluation metrics (match counts, percentages, sufficiency) for a list of evaluated results."
    )
    args_schema: Type[BaseModel] = MetricsToolInput

    def _run(self, evaluations: Union[List[Dict], str]) -> str:
        """
        Calculate evaluation metrics from a list of evaluated items.
        
        Args:
            evaluations: List of dicts or JSON string containing evaluated items.
                        Each item should have 'is_match' or 'match_status' field.
        
        Returns:
            JSON string with structure:
            {
                "metric_type": "search_quality",
                "count_positive": N,
                "count_negative": M,
                "match_percentage": X.XX,
                "total_listings": T,
                "overall_sufficiency": "sufficient" | "not sufficient"
            }
        """
        # ==========================================
        # STEP 1: PARSE INPUT
        # ==========================================
        if isinstance(evaluations, str):
            try:
                items = json.loads(evaluations)
            except Exception:
                return json.dumps({"error": "Input must be a valid JSON list."})
        else:
            items = evaluations

        # Validate input is non-empty list
        if not isinstance(items, list) or not items:
            return json.dumps({"error": "Empty dataset provided."})

        # ==========================================
        # STEP 2: COUNT MATCHES
        # ==========================================
        # Count items marked as matches (check both field names for compatibility)
        pos = sum(
            1 for i in items 
            if isinstance(i, dict) and (i.get("is_match") is True or i.get("match_status") is True)
        )
        
        total = len(items)
        
        # Calculate match percentage
        pct = round((pos / total * 100), 2) if total > 0 else 0.0

        # ==========================================
        # STEP 3: ASSESS SUFFICIENCY
        # ==========================================
        # Project rule: Results are "sufficient" if:
        # - Match percentage >= 50% AND
        # - At least 3 positive matches
        # This ensures both quality (percentage) and quantity (absolute count)
        is_sufficient = (pct >= 50 and pos >= 3)

        # ==========================================
        # STEP 4: BUILD RESULT
        # ==========================================
        result = {
            "metric_type": "search_quality",  # Identifies this as search quality metrics
            "count_positive": pos,  # Number of matching items
            "count_negative": total - pos,  # Number of non-matching items
            "match_percentage": pct,  # Percentage of matches
            "total_listings": total,  # Total items evaluated
            "overall_sufficiency": "sufficient" if is_sufficient else "not sufficient"  # Stop iterating?
        }
        
        return json.dumps(result, indent=2)