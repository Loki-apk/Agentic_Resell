"""
Custom Tool Template - Example template for creating new CrewAI tools.

This file provides a skeleton/template for creating custom tools that can be
used by agents in the ResellApp system. It demonstrates the basic structure
required for a CrewAI BaseTool.

To create a new tool:
1. Copy this template
2. Update the class name, name, description
3. Define the input schema (args_schema)
4. Implement the _run method with your tool's logic
5. Import and add to crew.py

This particular example is not used in the application - it's just a template.
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field


class MyCustomToolInput(BaseModel):
    """
    Input schema for MyCustomTool.
    
    Define the input parameters your tool needs here.
    Each parameter should have:
    - Type annotation
    - Field with description for the agent
    """
    argument: str = Field(..., description="Description of the argument that tells the agent how to use it.")

class MyCustomTool(BaseTool):
    """
    Example custom tool template.
    
    This is a template showing how to create a custom tool for CrewAI agents.
    Replace this class with your actual tool implementation.
    
    Required attributes:
    - name: Short name for the tool (shown to agents)
    - description: Clear description of what the tool does (helps agents decide when to use it)
    - args_schema: Pydantic model defining input parameters
    - _run: Method that executes the tool's functionality
    """
    name: str = "Name of my tool"
    description: str = (
        "Clear description for what this tool is useful for. "
        "Your agent will need this information to decide when to use it. "
        "Be specific about the tool's purpose and capabilities."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:
        """
        Execute the tool's main functionality.
        
        This method is called when an agent uses the tool.
        
        Args:
            argument: Input parameter(s) as defined in args_schema
            
        Returns:
            String result that will be passed back to the agent
            
        Implementation notes:
        - Keep logic focused and single-purpose
        - Handle errors gracefully
        - Return meaningful results the agent can use
        - Consider returning JSON for structured data
        """
        # Implementation goes here
        # This is just a placeholder example
        return "this is an example of a tool output, ignore it and move along."
