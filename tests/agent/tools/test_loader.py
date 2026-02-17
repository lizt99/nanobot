import sys
import pytest
from pathlib import Path
import importlib.util
import types
from abc import ABC, abstractmethod
from typing import Any

# Mock Base Tool class
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    @property
    @abstractmethod
    def description(self) -> str: pass
    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]: pass
    @abstractmethod
    async def execute(self, **kwargs: Any) -> str: pass

    def validate_params(self, params): return []
    def to_schema(self): return {}

# Helper to load the loader module bypassing package imports
def load_loader_module():
    # Attempt to locate the loader file
    # Assuming CWD is 'nanobot/' (repo root)
    loader_path = Path("nanobot/agent/tools/loader.py")
    if not loader_path.exists():
        # Fallback if CWD is workspace root
        loader_path = Path("nanobot/nanobot/agent/tools/loader.py")
    
    if not loader_path.exists():
        raise ImportError("loader.py not found")
        
    spec = importlib.util.spec_from_file_location("nanobot.agent.tools.loader", loader_path)
    if not spec or not spec.loader:
        raise ImportError("Could not create spec for loader.py")
        
    module = importlib.util.module_from_spec(spec)
    
    # Inject dependencies into sys.modules
    # 1. Mock 'nanobot'
    if "nanobot" not in sys.modules:
        sys.modules["nanobot"] = types.ModuleType("nanobot")
    
    # 2. Mock 'nanobot.agent'
    if "nanobot.agent" not in sys.modules:
        sys.modules["nanobot.agent"] = types.ModuleType("nanobot.agent")
        
    # 3. Mock 'nanobot.agent.tools'
    if "nanobot.agent.tools" not in sys.modules:
        sys.modules["nanobot.agent.tools"] = types.ModuleType("nanobot.agent.tools")

    # 4. Mock 'nanobot.agent.tools.base'
    mock_base = types.ModuleType("nanobot.agent.tools.base")
    mock_base.Tool = Tool
    sys.modules["nanobot.agent.tools.base"] = mock_base
    
    # Execute module
    sys.modules["nanobot.agent.tools.loader"] = module
    spec.loader.exec_module(module)
    return module

def test_load_skill_from_directory(tmp_path):
    try:
        loader_module = load_loader_module()
    except ImportError:
        pytest.fail("ImportError: loader.py not found or failed to load")

    LocalSkillLoader = loader_module.LocalSkillLoader
    
    # Create a dummy skill
    skill_dir = tmp_path / "skills" / "dummy"
    skill_dir.mkdir(parents=True)
    
    # Create tool.py for the skill
    # Note: The skill will import 'nanobot.agent.tools.base', which is mocked in sys.modules
    (skill_dir / "tool.py").write_text("""
from nanobot.agent.tools.base import Tool

class DummyTool(Tool):
    @property
    def name(self): return "dummy"
    @property
    def description(self): return "desc"
    @property
    def parameters(self): return {}
    async def execute(self, **kwargs): return "ok"
""")
    
    loader = LocalSkillLoader(tmp_path)
    tools = loader.load_all()
    assert len(tools) == 1
    assert tools[0].name == "dummy"

def test_load_from_package_dir(tmp_path):
    # Setup
    try:
        loader_module = load_loader_module()
    except ImportError:
        pytest.fail("ImportError: loader.py not found or failed to load")
        
    LocalSkillLoader = loader_module.LocalSkillLoader
    
    # Create a fake package directory
    pkg_dir = tmp_path / "site-packages" / "nanobot" / "skills"
    pkg_dir.mkdir(parents=True)
    
    # Create a fake built-in skill
    skill_dir = pkg_dir / "builtin_skill"
    skill_dir.mkdir()
    (skill_dir / "tool.py").write_text("""
from nanobot.agent.tools.base import Tool

class BuiltinTool(Tool):
    @property
    def name(self): return "builtin"
    @property
    def description(self): return "desc"
    @property
    def parameters(self): return {}
    async def execute(self, **kwargs): return "ok"
""")
    (skill_dir / "SKILL.md").write_text("# Builtin Skill")

    # Mock nanobot.skills module
    mock_skills = types.ModuleType("nanobot.skills")
    mock_skills.__file__ = str(pkg_dir / "__init__.py")
    sys.modules["nanobot.skills"] = mock_skills
    
    # Attach to parent package to fix import
    if "nanobot" in sys.modules:
        sys.modules["nanobot"].skills = mock_skills
    
    # Initialize loader with an empty workspace
    empty_workspace = tmp_path / "workspace"
    empty_workspace.mkdir()
    loader = LocalSkillLoader(empty_workspace)
    
    # This should find the built-in skill
    try:
        tools = loader.load_all()
        tool_names = [t.name for t in tools]
        assert "builtin" in tool_names
    finally:
        # Cleanup mock
        if "nanobot.skills" in sys.modules:
            del sys.modules["nanobot.skills"]
