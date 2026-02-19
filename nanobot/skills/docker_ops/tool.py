from typing import Dict, Any, List, Optional
import docker
import os
from nanobot.agent.tools.base import Tool

class DockerOpsTool(Tool):
    """
    Tool for managing Docker containers.
    """
    @property
    def name(self) -> str:
        return "docker_ops"

    @property
    def description(self) -> str:
        return "Manage Docker containers (spawn, kill, remove, logs)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_containers", "inspect_container", "spawn_container", "stop_container", "remove_container", "get_logs"]
                },
                "name": {"type": "string"},
                "image": {"type": "string"},
                "env_vars": {"type": "object"},
                "tail": {"type": "integer"},
                "all": {"type": "boolean"},
                "force": {"type": "boolean"}
            },
            "required": ["action"]
        }
    
    def __init__(self):
        self.client = docker.from_env()
        self.LABEL_KEY = "com.mspbots.nanobot"
        self.LABEL_VALUE = "true"
        self.ALLOWED_IMAGES_PREFIXES = ["nanobot-", "ghcr.io/astral-sh/uv", "deployment-"]

    def execute(self, action: str, **kwargs) -> Any:
        method_name = f"_{action}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _list_containers(self, all: bool = False) -> List[Dict[str, Any]]:
        """List containers with the nanobot label."""
        filters = {"label": [f"{self.LABEL_KEY}={self.LABEL_VALUE}"]}
        containers = self.client.containers.list(all=all, filters=filters)
        
        return [
            {
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.id,
            }
            for c in containers
        ]

    def _inspect_container(self, name: str) -> Dict[str, Any]:
        """Inspect a specific container."""
        container = self._get_container(name)
        return container.attrs

    def _spawn_container(self, name: str, image: str, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Spawn a new container.
        """
        # Security check: Image allowance
        if not any(image.startswith(prefix) for prefix in self.ALLOWED_IMAGES_PREFIXES):
            raise ValueError(f"Image '{image}' is not allowed. Must start with one of: {self.ALLOWED_IMAGES_PREFIXES}")

        # Prepare labels
        labels = {self.LABEL_KEY: self.LABEL_VALUE}
        
        try:
            container = self.client.containers.run(
                image,
                name=name,
                environment=env_vars or {},
                labels=labels,
                detach=True,
                network_mode="bridge" # Use default bridge or specify network if needed
            )
            # Try to connect to network if running in compose
            # (Simplification: relying on default network behavior for now)
            
            return {
                "id": container.short_id,
                "name": container.name,
                "status": "started"
            }
        except docker.errors.APIError as e:
            raise RuntimeError(f"Failed to spawn container: {str(e)}")

    def _stop_container(self, name: str) -> Dict[str, str]:
        """Stop a container."""
        if name == "nanobot-sol" or name == "deployment-sol-1":
            raise ValueError("Cannot stop 'Sol' (Self-preservation).")
            
        container = self._get_container(name)
        container.stop()
        return {"status": "stopped", "name": name}

    def _remove_container(self, name: str, force: bool = False) -> Dict[str, str]:
        """Remove a container."""
        if name == "nanobot-sol" or name == "deployment-sol-1":
            raise ValueError("Cannot remove 'Sol' (Self-preservation).")
            
        # Get container (even if stopped, it might not have label readable if inspected via name? No, get(name) works)
        # However, _get_container checks labels.
        container = self._get_container(name)
        container.remove(force=force)
        return {"status": "removed", "name": name}

    def _get_logs(self, name: str, tail: int = 100) -> str:
        """Get logs from a container."""
        container = self._get_container(name)
        return container.logs(tail=tail).decode('utf-8')

    def _get_container(self, name: str):
        """Helper to get a container and verify ownership label."""
        try:
            container = self.client.containers.get(name)
        except docker.errors.NotFound:
            raise ValueError(f"Container '{name}' not found.")
            
        # Security check: Verify label
        labels = container.labels or {}
        # Relax label check slightly to allow adopting containers if needed, 
        # OR ensure Sol always adds labels.
        if labels.get(self.LABEL_KEY) != self.LABEL_VALUE:
             # Fallback: if name starts with nanobot-, allow it?
             # No, strictly managed.
             pass
             # For 'alice' created by Sol previously, it should have the label.
             # If 'alice' was created manually without label, Sol can't touch it.
             # We will assume Sol created it.
             
        if labels.get(self.LABEL_KEY) != self.LABEL_VALUE:
             raise PermissionError(f"Access denied: Container '{name}' is not managed by Nanobot (missing label).")
            
        return container
