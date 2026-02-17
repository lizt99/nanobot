import importlib.util
import sys
from pathlib import Path
from typing import Any, List, Optional
from loguru import logger
from nanobot.agent.tools.base import Tool

class LocalSkillLoader:
    def __init__(self, workspace: Path):
        self.workspace_skills = workspace / "skills"
        # Determine package skills dir
        try:
            import nanobot.skills
            self.package_skills = Path(nanobot.skills.__file__).parent
        except (ImportError, AttributeError):
            self.package_skills = None

    def load_all(self) -> List[Tool]:
        tools = []
        
        # Load from Package (Built-in)
        if self.package_skills and self.package_skills.exists():
            tools.extend(self._load_from_dir(self.package_skills))
            
        # Load from Workspace (User)
        if self.workspace_skills.exists():
            tools.extend(self._load_from_dir(self.workspace_skills))
            
        return tools

    def _load_from_dir(self, directory: Path) -> List[Tool]:
        tools = []
        for item in directory.iterdir():
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
