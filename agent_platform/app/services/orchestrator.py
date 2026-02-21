from abc import ABC, abstractmethod
from typing import Dict, Optional

class Orchestrator(ABC):
    """
    Abstract interface for managing agent containers/pods.
    Implementations: DockerOrchestrator, K8sOrchestrator (future).
    """

    @abstractmethod
    def start_agent(self, agent_id: str, name: str, aieos: Dict, config: Dict) -> Dict:
        """
        Start an agent instance.
        :param agent_id: Unique identifier for the agent (container name/pod name).
        :param name: Display name or logical name.
        :param aieos: AIEOS configuration dictionary (identity).
        :param config: Runtime configuration (env vars, resources).
        :return: Dict containing 'container_id' and optional 'metadata'.
        """
        pass

    @abstractmethod
    def stop_agent(self, agent_id: str):
        """Stop a running agent instance."""
        pass

    @abstractmethod
    def remove_agent(self, agent_id: str):
        """Remove an agent instance (and its resources)."""
        pass

    @abstractmethod
    def get_status(self, agent_id: str) -> str:
        """Get the current status (running, stopped, etc.)."""
        pass
