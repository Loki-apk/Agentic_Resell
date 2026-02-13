"""
Main entry point for the Resell App application.

This file provides the command-line interface for running the resell price prediction system.

It includes functions for:
- Normal execution: Analyzing product images and predicting resale prices
- Training: Training the AI agents with feedback
- Testing: Testing the crew's performance
- Replay: Replaying past executions for debugging
- Trigger-based execution: Running with external trigger payloads

The application uses CrewAI framework to orchestrate multiple AI agents that work together
to analyze product images, search for similar items, and calculate suggested prices.
"""

#!/usr/bin/env python
import sys
import warnings
from datetime import datetime
from pathlib import Path
from resell_app.crew import ResellApp

# Suppress syntax warnings from pysbd library to keep console output clean
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """
    Run the full resell price analysis pipeline.
    
    This is the main execution function that:
    1. Accepts product image URLs as input (IMPORTANT: URLs should be provided)
    2. Analyzes the images to extract product details
    3. Generates search queries for similar items
    4. Scrapes Kleinanzeigen marketplace for comparable listings
    5. Evaluates matches and calculates price statistics
    6. Returns suggested resale price with min/max range
    
    Returns:
        dict: Complete analysis results including price recommendations
    """
    # Prepare input configuration for the agent pipeline
    # IMPORTANT: image_urls should contain valid URLs to product images
    inputs = {
        'topic': 'AI LLMs',  # General topic context (not critical for analysis)
        'current_year': str(datetime.now().year),  # Current year for temporal context
        # CRITICAL: image_urls must be valid URLs pointing to product images
        # These example URLs point to Kleinanzeigen image CDN
        "image_urls": [
            'https://img.kleinanzeigen.de/api/v1/prod-ads/images/78/7879ca33-17cf-493a-b697-a309552f0cd6?rule=$_59.AUTO',
            'https://img.kleinanzeigen.de/api/v1/prod-ads/images/77/77654454-b98c-492e-ad7b-8f4c214e98a5?rule=$_59.AUTO',
            'https://img.kleinanzeigen.de/api/v1/prod-ads/images/f5/f50d145d-f10f-43e6-b745-3c7d5539b5f3?rule=$_59.AUTO'
        ],
        # Default values required by the task templates in tasks.yaml
        'iteration': 1,  # Starting iteration number
        'feedback': 'None',  # Initial feedback (used in refinement iterations)
        'image_analysis': 'Context',  # Placeholder for image analysis results
        'scraped_data_file': str(
            Path(__file__).parent.parent.parent / "Kleinanzeigen_Data" / "kleinanzeigen_items.json"
        )  # Path to scraped data
    }
    
    try:
        # Execute the complete pipeline: image analysis → query generation → scraping → evaluation → pricing
        result = ResellApp().run_full_pipeline(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the pipeline: {e}")


def train():
    """
    Train the AI agents for improved performance over multiple iterations.
    
    Training allows the agents to learn from feedback and improve their decision-making.
    
    This function requires command-line arguments:
    - sys.argv[1]: Number of training iterations (int)
    - sys.argv[2]: Filename to save training results
    
    Usage:
        python -m resell_app.main train <iterations> <filename>
    """
    # Prepare training dataset with sample product images
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year),
        # Training uses a single sample image URL for consistency
        "image_urls": [
            'https://img.kleinanzeigen.de/api/v1/prod-ads/images/7c/7cd7b918-4651-4376-b020-6a2f79c37f51?rule=$_59.AUTO'
        ],
        # Defaults required by task templates
        'iteration': 1,
        'feedback': 'None',
        'image_analysis': 'Context',
        'scraped_data_file': str(
            Path(__file__).parent.parent.parent / "Kleinanzeigen_Data" / "kleinanzeigen_items.json"
        )
    }
    
    try:
        # Execute training with specified iterations and save results to file
        ResellApp().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay a previous crew execution from a specific task for debugging purposes.
    
    This is useful for:
    - Debugging failed executions
    - Understanding agent decision-making
    - Testing changes to specific tasks
    
    Requires command-line argument:
    - sys.argv[1]: Task ID to replay from
    
    Usage:
        python -m resell_app.main replay <task_id>
    """
    try:
        # Replay execution starting from the specified task
        ResellApp().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """
    Test the crew's performance and evaluate results using a specified LLM.
    
    Testing runs the crew multiple times and evaluates performance metrics:
    - Accuracy of image analysis
    - Quality of search queries
    - Match percentage in results
    - Price prediction accuracy
    
    Requires command-line arguments:
    - sys.argv[1]: Number of test iterations (int)
    - sys.argv[2]: LLM model to use for evaluation
    
    Usage:
        python -m resell_app.main test <iterations> <llm_model>
    """
    # Prepare test dataset with sample images
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year),
        # Test uses a single known sample for consistent evaluation
        "image_urls": [
            'https://img.kleinanzeigen.de/api/v1/prod-ads/images/7c/7cd7b918-4651-4376-b020-6a2f79c37f51?rule=$_59.AUTO'
        ],
        # Defaults required by task templates
        'iteration': 1,
        'feedback': 'None',
        'image_analysis': 'Context',
        'scraped_data_file': str(
            Path(__file__).parent.parent.parent / "Kleinanzeigen_Data" / "kleinanzeigen_items.json"
        )
    }
    
    try:
        # Run test iterations and evaluate using specified LLM
        ResellApp().crew().test(
            n_iterations=int(sys.argv[1]),
            openai_model_name=sys.argv[2],
            inputs=inputs
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def trigger():
    """
    Run the crew with an external trigger payload (for integration with other systems).
    
    This function enables the resell app to be triggered by external systems
    (e.g., webhooks, APIs, automation platforms) by accepting a JSON payload.
    
    The trigger payload can contain:
    - Image URLs
    - Product information
    - Configuration parameters
    - Any custom metadata
    
    Requires command-line argument:
    - sys.argv[1]: JSON string containing the trigger payload
    
    Usage:
        python -m resell_app.main trigger '{"image_urls": [...], "metadata": {...}}'
    """
    import json
    
    # Validate that a trigger payload was provided
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")
    
    # Parse the JSON payload from command-line argument
    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")
    
    # Prepare inputs with the trigger payload
    # The empty strings will be populated from the trigger payload if available
    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",  # Can be populated from trigger payload
        "current_year": "",  # Can be populated from trigger payload
        "image_urls": ""  # IMPORTANT: Should be provided in trigger payload as URLs
    }
    
    try:
        # Execute the full pipeline with the trigger-provided inputs
        result = ResellApp().run_full_pipeline(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the pipeline with trigger: {e}")