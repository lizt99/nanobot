from typing import Dict, Any, List, Optional
import docker
import os

class DockerOpsTool:
    """
    Tool for managing Docker containers.
    """
    
    def __init__(self):
        self.client = docker.from_env()
        self.LABEL_KEY = "com.mspbots.nanobot"
        self.LABEL_VALUE = "true"
        self.ALLOWED_IMAGES_PREFIXES = ["nanobot-", "ghcr.io/astral-sh/uv"]

    def execute(self, action: str, **kwargs) -> Any:
        """
        Execute a Docker operation.
        
        Args:
            action: The action to perform (list_containers, inspect_container, spawn_container, stop_container, get_logs)
            **kwargs: Arguments for the specific action
        """
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
        
        Args:
            name: Container name
            image: Image to use (must start with allowed prefixes)
            env_vars: Environment variables
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
                detach=True
            )
            return {
                "id": container.short_id,
                "name": container.name,
                "status": "started"
            }
        except docker.errors.APIError as e:
            raise RuntimeError(f"Failed to spawn container: {str(e)}")

    def _stop_container(self, name: str) -> Dict[str, str]:
        """
        Stop a container.
        """
        # Security check: Self-preservation
        if name == "nanobot-sol":
            raise ValueError("Cannot stop 'nanobot-sol' (Self-preservation).")
            
        container = self._get_container(name)
        container.stop()
        return {"status": "stopped", "name": name}

    def _get_logs(self, name: str, tail: int = 100) -> str:
        """Get logs from a container."""
        container = self._get_container(name)
        # logs returns bytes, decode to string
        return container.logs(tail=tail).decode('utf-8')

    def _get_container(self, name: str):
        """Helper to get a container and verify ownership label."""
        try:
            container = self.client.containers.get(name)
        except docker.errors.NotFound:
            raise ValueError(f"Container '{name}' not found.")
            
        # Security check: Verify label
        labels = container.labels or {}
        if labels.get(self.LABEL_KEY) != self.LABEL_VALUE:
            raise PermissionError(f"Access denied: Container '{name}' is not managed by Nanobot.")
            
        return container
