import importlib.util
import sys
from pathlib import Path
from typing import Any, List, Optional
from loguru import logger
from nanobot.agent.tools.base import Tool

class LocalSkillLoader:
    def __init__(self, workspace: Path):
        self.skills_dir = workspace / "skills"

    def load_all(self) -> List[Tool]:
        tools = []
        if not self.skills_dir.exists():
            return []
            
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                tool = self._load_skill(item)
                if tool:
                    tools.append(tool)
        return tools

    def _load_skill(self, skill_path: Path) -> Optional[Tool]:
        tool_file = skill_path / "tool.py"
        if not tool_file.exists():
            return None
            
        try:
            # Dynamic import
            spec = importlib.util.spec_from_file_location(f"skills.{skill_path.name}", tool_file)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Find tool class
            for name, obj in vars(module).items():
                if isinstance(obj, type) and issubclass(obj, Tool) and obj is not Tool:
                    return obj()
        except Exception as e:
            logger.error(f"Failed to load skill {skill_path.name}: {e}")
        return None
