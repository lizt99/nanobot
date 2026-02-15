"""Tool management for dynamic extensibility."""

from pathlib import Path
from typing import Any, Callable

from loguru import logger

from nanobot.agent.tools.base import Tool


class ManageToolsTool(Tool):
    """
    Tool for creating and reloading dynamic tools.
    
    Allows the agent to write python code that implements new tools
    and load them into the running process.
    """
    
    def __init__(self, tools_dir: Path, reload_callback: Callable[[], None]):
        self.tools_dir = tools_dir
        self.reload_callback = reload_callback
        # Ensure directory exists
        if not self.tools_dir.exists():
            self.tools_dir.mkdir(parents=True, exist_ok=True)
            # Add __init__.py so it's a package (optional but good practice)
            (self.tools_dir / "__init__.py").touch()
    
    @property
    def name(self) -> str:
        return "manage_tools"
    
    @property
    def description(self) -> str:
        return """Create or reload python tools dynamically.
Use this to extend your capabilities by writing new Python code.
The code must define a class inheriting from `nanobot.agent.tools.base.Tool`.
Example:
```python
from typing import Any
from nanobot.agent.tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"arg": {"type": "string"}}}
    
    async def execute(self, arg: str) -> str:
        return f"Result: {arg}"
```
"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "reload", "list"],
                    "description": "Action to perform."
                },
                "name": {
                    "type": "string",
                    "description": "Name of the tool file (without .py) for 'create' action."
                },
                "code": {
                    "type": "string",
                    "description": "Python source code for 'create' action."
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, action: str, name: str | None = None, code: str | None = None) -> str:
        if action == "create":
            if not name or not code:
                return "Error: 'name' and 'code' are required for create action."
            
            # Sanitize name
            safe_name = "".join(c for c in name if c.isalnum() or c == "_")
            file_path = self.tools_dir / f"{safe_name}.py"
            
            try:
                file_path.write_text(code, encoding="utf-8")
                # Reload immediately
                if self.reload_callback:
                    self.reload_callback()
                return f"Tool '{safe_name}' created at {file_path} and reloaded."
            except Exception as e:
                return f"Error creating tool file: {e}"
                
        elif action == "reload":
            if self.reload_callback:
                try:
                    self.reload_callback()
                    return "Tools reloaded successfully."
                except Exception as e:
                    return f"Error reloading tools: {e}"
            return "Error: No reload callback configured."
            
        elif action == "list":
            files = [f.name for f in self.tools_dir.glob("*.py") if not f.name.startswith("_")]
            return f"Dynamic tool files: {', '.join(files)}"
            
        return f"Unknown action: {action}"
