"""Skill creation tool for experience consolidation."""

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class CreateSkillTool(Tool):
    """
    Tool for creating new skills (SOPs) based on successful execution.
    
    Allows the agent to consolidate its experience into reusable SKILL.md files.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.skills_dir = workspace / "skills"
        
        # Ensure directory exists
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def name(self) -> str:
        return "create_skill"
    
    @property
    def description(self) -> str:
        return """Create a new skill (SOP) based on your experience.
Use this to save a successful sequence of actions or a solution to a problem
so you can reuse it later. The content should be a clear Markdown guide.

Example Content:
# Skill: Check IP
To check your public IP address, run the following command:
`exec(command="curl ifconfig.me")`
"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the skill (e.g., 'check-ip'). use kebab-case."
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content describing the skill (SOP)."
                }
            },
            "required": ["name", "content"]
        }
    
    async def execute(self, name: str, content: str) -> str:
        # Sanitize name
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
        skill_dir = self.skills_dir / safe_name
        
        try:
            skill_dir.mkdir(exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(content, encoding="utf-8")
            return f"Skill '{safe_name}' created successfully at {skill_file}."
        except Exception as e:
            return f"Error creating skill: {e}"
