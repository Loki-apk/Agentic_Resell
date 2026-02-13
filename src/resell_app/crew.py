"""
ResellApp Crew - Multi-Agent AI System for Resell Price Prediction

This module defines the AI agent architecture using CrewAI framework.
It coordinates multiple specialized agents that work together to:
1. Analyze product images
2. Generate search queries
3. Evaluate search results
4. Calculate price recommendations

The crew uses a combination of vision and text-based LLMs, along with
custom tools for market scraping, file reading, and metrics calculation.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from resell_app.tools.vision_tool import QwenVisionTool
from resell_app.tools.metrics_tools import EvaluationMetricsTool
from resell_app.tools.file_read_tool import UTF8FileReadTool
from resell_app.market_search import MarketSearch

# Load environment variables from .env file
# Required variables: OPENAI_BASE_URL, OPENAI_API_KEY, Image_MODEL, MODEL
load_dotenv()

# ===========================================
# LLM CONFIGURATION
# ===========================================
# Base configuration for all LLM connections
BASE_CFG = {
    "base_url": os.getenv("OPENAI_BASE_URL"),  # API endpoint URL
    "api_key": os.getenv("OPENAI_API_KEY")     # API authentication key
}

# Vision LLM for image analysis (temperature=0.0 for deterministic results)
VIS_LLM = LLM(model=os.getenv("Image_MODEL"), temperature=0.0, **BASE_CFG)

# Text LLM for query generation and evaluation (temperature=0.1 for slightly creative but focused output)
TXT_LLM = LLM(model=os.getenv("MODEL"), temperature=0.1, **BASE_CFG)

@CrewBase
class ResellApp:
    """
    Main ResellApp crew class defining all agents, tasks, and workflows.
    
    This class uses CrewAI decorators (@agent, @task, @crew) to define
    the multi-agent system architecture. It coordinates:
    
    AGENTS:
    - Image Analyzer: Analyzes product photos using vision AI
    - Query Generator: Creates German search queries
    - List Evaluator: Evaluates and ranks search results
    
    TOOLS:
    - Vision Tool: Multi-image analysis with consistency checking
    - Metrics Tool: Calculate match percentages and sufficiency
    - File Reader: Read scraped Kleinanzeigen data
    - Market Search: Scrape Kleinanzeigen marketplace
    
    CREWS (Workflows):
    - Analysis & Query: Phase 1 workflow (image → query)
    - Query Regeneration: Refine queries based on feedback
    - Evaluation: Evaluate scraped results against product
    """
    
    # ===========================================
    # TOOL INITIALIZATION
    # ===========================================
    # Vision tool for analyzing product images
    vision_tool = QwenVisionTool()
    
    # Metrics tool for calculating search quality metrics
    metrics_tool = EvaluationMetricsTool()
    
    # Project root path for file operations
    _project_root = Path(__file__).parent.parent.parent
    
    # File reader tool configured to read scraped Kleinanzeigen data
    file_reader_tool = UTF8FileReadTool(
        file_path=str(_project_root / "Kleinanzeigen_Data" / "kleinanzeigen_items.json")
    )

    # Market search/scraper integration for Kleinanzeigen
    market_search = MarketSearch()


    # ===========================================
    # AGENT DEFINITIONS
    # ===========================================
    
    @agent
    def image_analyzer(self) -> Agent:
        """
        Image Analyzer Agent - Analyzes product photos using vision AI.
        
        Responsibilities:
        - Extract product attributes (name, brand, model, color, condition)
        - Verify image consistency (all images show same product)
        - Generate detailed product description
        - Identify key features for search
        
        Tools: QwenVisionTool (multi-image vision analysis)
        LLM: Vision-capable model (configured in .env as Image_MODEL)
        Config: agents.yaml -> image_analyzer section
        """
        return Agent(
            config=self.agents_config["image_analyzer"],
            verbose=True,  # Print agent reasoning and actions
            cache=False,   # Don't cache results (images may be different each run)
            tools=[self.vision_tool],
            llm=VIS_LLM
        )
    
    @agent
    def search_query_generator(self) -> Agent:
        """
        Search Query Generator Agent - Creates German search queries for Kleinanzeigen.
        
        Responsibilities:
        - Generate effective German search queries from product attributes
        - Incorporate feedback from previous iterations
        - Optimize queries for Kleinanzeigen search behavior
        - Balance specificity and breadth
        
        Tools: None (pure text reasoning)
        LLM: Text model (configured in .env as MODEL)
        Config: agents.yaml -> search_query_generator section
        """
        return Agent(
            config=self.agents_config["search_query_generator"],
            verbose=True,
            cache=False,
            llm=TXT_LLM
        )
    
    @agent
    def search_list_evaluator(self) -> Agent:
        """
        Search List Evaluator Agent - Evaluates scraped listings for match quality.
        
        Responsibilities:
        - Compare scraped listings against product description
        - Classify each listing as match/non-match
        - Calculate match percentage and sufficiency metrics
        - Generate feedback for query improvement
        - Identify price outliers
        
        Tools: 
        - UTF8FileReadTool: Read scraped data from JSON
        - EvaluationMetricsTool: Calculate match statistics
        
        LLM: Text model (configured in .env as MODEL)
        Config: agents.yaml -> search_list_evaluator section
        """
        return Agent(
            config=self.agents_config["search_list_evaluator"],
            verbose=True,
            cache=False,
            tools=[self.file_reader_tool, self.metrics_tool],
            llm=TXT_LLM
        )
    
    # ===========================================
    # TASK DEFINITIONS
    # ===========================================
    
    @task
    def image_analysis_task(self) -> Task:
        """
        Image Analysis Task - Analyze product images and extract attributes.
        
        Input: image_urls (list of URLs)
        Output: JSON with product attributes
        Agent: image_analyzer
        Output File: image_analysis.json
        
        Expected output structure:
        {
            "status": "SUCCESS",
            "item_name": "...",
            "brand": "...",
            "model": "...",
            "color": "...",
            "condition": "...",
            "description": "..."
        }
        """
        return Task(
            config=self.tasks_config["image_analysis_task"],
            agent=self.image_analyzer(),
            output_file="image_analysis.json"
        )
    
    @task
    def generate_query_task(self) -> Task:
        """
        Query Generation Task - Create German search query from product attributes.
        
        Input: image_analysis (from previous task), iteration, feedback
        Output: JSON with search query
        Agent: search_query_generator
        Output File: search_query.json
        
        Expected output structure:
        {
            "search_query": "german search terms",
            "reasoning": "..."
        }
        """
        return Task(
            config=self.tasks_config["generate_query_task"],
            agent=self.search_query_generator(),
            output_file="search_query.json"
        )
    
    @task
    def evaluate_list_task(self) -> Task:
        """
        Evaluation Task - Evaluate scraped listings for matches and calculate metrics.
        
        Input: image_analysis, search_query, scraped_data_file
        Output: JSON with evaluations and metrics
        Agent: search_list_evaluator
        Output File: query_evaluation.json
        Execution: Synchronous (async_execution=False)
        
        Expected output structure:
        {
            "individual_results_evaluation": [{"id": ..., "is_match": true/false, ...}, ...],
            "count_positive": N,
            "count_negative": M,
            "match_percentage": X.X,
            "overall_sufficiency": "sufficient"/"not sufficient",
            "query_improvement_feedback": "..."
        }
        """
        return Task(
            config=self.tasks_config["evaluate_list_task"],
            agent=self.search_list_evaluator(),
            output_file="query_evaluation.json",
            async_execution=False  # Must complete before next step
        )
    
   
    # ===========================================
    # CREW DEFINITIONS (WORKFLOWS)
    # ===========================================
    
    @crew
    def analysis_and_query_crew(self) -> Crew:
        """
        Phase 1 Crew - Image Analysis + Initial Query Generation.
        
        This crew runs the first phase of the workflow:
        1. Analyze product images to extract attributes
        2. Generate initial German search query based on attributes
        
        Agents: image_analyzer, search_query_generator (sequential)
        Tasks: image_analysis_task, generate_query_task
        Process: Sequential (tasks run one after another)
        
        Returns results for both tasks that workflow uses to proceed.
        """
        return Crew(
            agents=[self.image_analyzer(), self.search_query_generator()],
            tasks=[self.image_analysis_task(), self.generate_query_task()],
            process=Process.sequential,
            verbose=True 
        )
    
    @crew
    def query_regeneration_crew(self) -> Crew:
        """
        Query Regeneration Crew - Refine search query based on feedback.
        
        This crew runs in iterations 2+ to improve the search query:
        - Takes feedback from evaluator about previous results
        - Generates improved query to find better matches
        
        Agents: search_query_generator
        Tasks: generate_query_task
        Process: Sequential (single task)
        
        Used in the iterative refinement loop of Phase 2.
        """
        return Crew(
            agents=[self.search_query_generator()],
            tasks=[self.generate_query_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def evaluation_crew(self) -> Crew:
        """
        Evaluation Crew - Evaluate scraped listings and calculate metrics.
        
        This crew analyzes scraped marketplace data:
        - Compares each listing to the product description
        - Classifies listings as matches or non-matches
        - Calculates match percentage and sufficiency
        - Generates feedback for query improvement
        
        Agents: search_list_evaluator
        Tasks: evaluate_list_task
        Process: Sequential (single task)
        
        Runs after each scraping operation in Phase 2.
        """
        return Crew(
            agents=[self.search_list_evaluator()],
            tasks=[self.evaluate_list_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def crew(self) -> Crew:
        """
        Top-level crew for CLI compatibility.
        
        This crew is used by CrewAI's CLI commands (train, test, replay).
        It includes all agents and tasks defined in this class.
        
        For normal execution, use run_full_pipeline() which orchestrates
        the specialized crews (analysis_and_query_crew, evaluation_crew, etc.)
        in the proper workflow sequence.
        """
        return Crew(
            agents=self.agents,  # All agents defined with @agent decorator
            tasks=self.tasks,    # All tasks defined with @task decorator
            process=Process.sequential,
            verbose=True,
        )

    def run_full_pipeline(self, inputs: dict):
        """
        Execute the complete resell price analysis pipeline.
        
        This is the main entry point for running the full workflow.
        It delegates to ResellWorkflow class which orchestrates:
        - Phase 1: Image analysis and query generation
        - Phase 2: Iterative scraping, evaluation, and refinement
        - Finalization: Price calculation and output generation
        
        Args:
            inputs: Dict with image_urls and configuration
            
        Returns:
            Final results dict with price recommendations
        """
        from resell_app.workflow import ResellWorkflow
        return ResellWorkflow(self).run(inputs)

