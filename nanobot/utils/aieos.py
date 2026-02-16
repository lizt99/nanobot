import json
from pathlib import Path
from typing import Any, Dict

class AIEOSLoader:
    """
    Loader for AIEOS (AI Entity Object Specification) identities.
    Parses AIEOS JSON and converts it into a system prompt compatible format.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def load_identity(self) -> dict | None:
        """Load AIEOS identity data from environment variables or file."""
        import os
        
        # 1. Try Inline JSON content
        if content := os.environ.get("NANOBOT_AIEOS_JSON"):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

        # 2. Try File Path
        path_str = os.environ.get("NANOBOT_AIEOS_PATH")
        if path_str:
            path = Path(path_str)
            # Resolve relative to workspace if not absolute
            if not path.is_absolute():
                path = self.workspace / path
            
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
        
        return None

    def get_prompt(self) -> str | None:
        """Get formatted system prompt from loaded identity."""
        data = self.load_identity()
        if not data:
            return None
        return self._format_to_prompt(data)

    def get_skills(self) -> list[str]:
        """Extract skill names from AIEOS capabilities."""
        data = self.load_identity()
        if not data:
            return []
        
        skills = []
        capabilities = data.get("capabilities", {})
        
        # 1. Direct skills list (AIEOS v1.1)
        # e.g. "skills": ["python", "web-search"]
        for skill in capabilities.get("skills", []):
            # Normalize skill name: "Web Research" -> "web-research"
            normalized = skill.lower().replace(" ", "-")
            skills.append(normalized)
            
        # 2. Tools list (AIEOS v1.1)
        # e.g. "tools": ["browser", "shell"]
        for tool in capabilities.get("tools", []):
            normalized = tool.lower().replace(" ", "-")
            skills.append(normalized)
            
        return skills

    def get_config_overrides(self) -> dict[str, Any]:
        """Extract configuration overrides (temperature, etc.) from psychology."""
        data = self.load_identity()
        if not data:
            return {}
            
        overrides = {}
        psych = data.get("psychology", {})
        matrix = psych.get("neural_matrix", {})
        
        # Map creativity -> temperature
        if "creativity" in matrix:
            # creativity 0.0-1.0 -> temperature 0.0-1.0
            overrides["temperature"] = float(matrix["creativity"])
            
        return overrides

    def _format_to_prompt(self, data: Dict[str, Any]) -> str:
        """Convert AIEOS JSON data into a markdown system prompt."""
        parts = []

        # 1. Identity (Name, Role)
        identity = data.get("identity", {})
        names = identity.get("names", {})
        fullname = names.get("first", "Nanobot")
        if names.get("nickname"):
            fullname += f" ({names['nickname']})"
        
        parts.append(f"# Identity: {fullname}")
        
        if identity.get("bio"):
            parts.append(f"**Bio:** {identity['bio']}")
            
        # 2. Role / Occupation
        history = data.get("history", {})
        if history.get("occupation"):
            parts.append(f"**Role:** {history['occupation']}")

        # 3. Psychology (Personality, Traits)
        psych = data.get("psychology", {})
        if psych.get("traits"):
            traits = psych["traits"]
            if isinstance(traits, dict):
                traits_str = ", ".join(f"{k}: {v}" for k, v in traits.items())
                parts.append(f"**Traits:** {traits_str}")
            elif isinstance(traits, list):
                parts.append(f"**Traits:** {', '.join(traits)}")
        
        if psych.get("moral_compass"):
             parts.append(f"**Alignment:** {psych['moral_compass'].get('alignment', 'Neutral')}")

        # 4. Directives / Motivations
        motivations = data.get("motivations", {})
        if motivations.get("core_drive"):
            parts.append(f"\n## Core Drive\n{motivations['core_drive']}")
        
        if motivations.get("goals"):
            goals = motivations["goals"]
            if isinstance(goals, list):
                parts.append("\n## Goals")
                for goal in goals:
                    parts.append(f"- {goal}")

        # 5. Linguistics (Style)
        linguistics = data.get("linguistics", {})
        if linguistics.get("style"):
            parts.append(f"\n## Communication Style\n{linguistics['style']}")
        elif linguistics.get("text_style"):
             # AIEOS v1.1 style
             style = linguistics["text_style"]
             parts.append(f"\n## Communication Style")
             if style.get("tone"):
                 parts.append(f"- Tone: {style['tone']}")
             if style.get("formality"):
                 parts.append(f"- Formality: {style['formality']}")

        # 6. Capabilities / Skills (Mention them in prompt too)
        capabilities = data.get("capabilities", {})
        if capabilities.get("skills"):
            parts.append("\n## Expertise")
            for skill in capabilities["skills"]:
                parts.append(f"- {skill}")

        return "\n\n".join(parts)
