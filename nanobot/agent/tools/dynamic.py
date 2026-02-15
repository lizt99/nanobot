"""Dynamic tool loader for runtime extensibility."""

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Type

from loguru import logger

from nanobot.agent.tools.base import Tool


class DynamicToolLoader:
    """
    Loads tools dynamically from python files in a directory.
    
    Expects files to contain subclasses of Tool.
    """
    
    def __init__(self, tools_dir: Path):
        self.tools_dir = tools_dir
    
    def load_tools(self) -> list[Tool]:
        """
        Scan directory and load all Tool subclasses found in .py files.
        
        Returns:
            List of instantiated tools.
        """
        tools = []
        if not self.tools_dir.exists():
            return tools
        
        for file_path in self.tools_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
                
            try:
                module_name = f"dynamic_tools.{file_path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    continue
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Find Tool subclasses
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, Tool)
                        and obj is not Tool
                        and obj.__module__ == module_name
                    ):
                        try:
                            # Instantiate tool (assume no-arg constructor for now)
                            tool_instance = obj()
                            tools.append(tool_instance)
                            logger.info(f"Loaded dynamic tool: {tool_instance.name} from {file_path.name}")
                        except Exception as e:
                            logger.error(f"Failed to instantiate tool {name} from {file_path}: {e}")
                            
            except Exception as e:
                logger.error(f"Failed to load module {file_path}: {e}")
                
        return tools
