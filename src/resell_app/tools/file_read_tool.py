"""
UTF8 File Read Tool - Read scraped Kleinanzeigen data from JSON file.

This tool allows agents to access the scraped marketplace data stored
in kleinanzeigen_items.json. It provides graceful error handling and
returns empty arrays instead of errors to prevent agent failures.

Features:
- Reads UTF-8 encoded JSON files
- Configurable file path (defaults to Kleinanzeigen_Data/kleinanzeigen_items.json)
- Graceful error handling (returns [] on errors)
- Path resolution from project root
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from pathlib import Path
import json

class UTF8FileReadInput(BaseModel):
    """
    Input schema for UTF8FileReadTool.
    
    Note: The 'request' field is a dummy parameter to satisfy CrewAI's
    tool input validation. Agents should pass 'read' for this field.
    """
    request: str = Field(
        default="read", 
        description="Action to perform. Always use 'read'."
    )
    file_path: str = Field(
        default="",
        description="Optional absolute path to a JSON file. If empty, uses default kleinanzeigen_items.json path."
    )

class UTF8FileReadTool(BaseTool):
    """
    Tool for reading the scraped Kleinanzeigen data JSON file.
    
    This tool is used by the search_list_evaluator agent to read the
    scraped marketplace data for evaluation. It's designed to be fault-tolerant,
    returning empty arrays on errors rather than raising exceptions.
    
    Default file location: <project_root>/Kleinanzeigen_Data/kleinanzeigen_items.json
    """
    name: str = "Read Local Database"
    description: str = "Reads the local kleinanzeigen_items.json database file containing scraped listings. Input 'read' to execute."
    args_schema: Type[BaseModel] = UTF8FileReadInput
    
    def _run(self, request: str = "read", file_path: str = "") -> str:
        """
        Read and return the contents of the scraped data JSON file.
        
        Args:
            request: Action to perform (always "read")
            file_path: Optional custom file path. If empty, uses default location.
        
        Returns:
            JSON string containing scraped listings array, or "[]" on error.
            
        Error handling:
            Returns empty array "[]" on any error to prevent agent failures.
            This allows the workflow to continue gracefully even if no data exists.
        """
        try:
            # ==========================================
            # STEP 1: RESOLVE FILE PATH
            # ==========================================
            if file_path:
                # Use provided path if available
                resolved_path = Path(file_path)
            else:
                # Calculate default path from project structure
                # __file__ is src/resell_app/tools/file_read_tool.py
                # Project root is 4 levels up: tools -> resell_app -> src -> root
                project_root = Path(__file__).parent.parent.parent.parent
                resolved_path = project_root / "Kleinanzeigen_Data" / "kleinanzeigen_items.json"
            
            # ==========================================
            # STEP 2: CHECK FILE EXISTS
            # ==========================================
            if not resolved_path.exists():
                print(f"[ReadTool] File not found: {resolved_path}")
                return "[]"  # Return empty array - agent can handle this gracefully
            
            # ==========================================
            # STEP 3: READ AND PARSE JSON
            # ==========================================
            with open(resolved_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return json.dumps(data)  # Return as JSON string
                
        except FileNotFoundError:
            # File doesn't exist - return empty array for consistency
            return "[]"
        except json.JSONDecodeError:
            # File exists but is invalid JSON - return empty array
            print(f"[ReadTool] Invalid JSON in file")
            return "[]"
        except Exception as e:
            # Any other error - log and return empty array
            print(f"[ReadTool] Error reading file: {e}")
            return "[]"