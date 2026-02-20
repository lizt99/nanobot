import docker
import json
from typing import Dict
from app.core.config import settings
from app.services.orchestrator import Orchestrator

# Try to import BIP340 utils (must be available in PYTHONPATH)
try:
    from nanobot.utils.bip340 import generate_keypair
except ImportError:
    generate_keypair = None

class DockerOrchestrator(Orchestrator):
    def __init__(self):
        self.client = docker.from_env()

    def start_agent(self, agent_id: str, name: str, aieos: Dict, config: Dict) -> Dict:
        """
        Starts a Docker container for the agent.
        Returns Dict with container_id and generated metadata.
        """
        # Prepare Environment Variables
        env_vars = {
            "NANOBOT_NAME": name.capitalize(),
            "NANOBOT_SOUL_ID": agent_id,
            "NANOBOT_AIEOS_JSON": json.dumps(aieos) if aieos else "",
            # Channels
            "NANOBOT_CHANNELS__TELEGRAM__ENABLED": str(config.get("telegram_enabled", "false")).lower(),
            "NANOBOT_CHANNELS__TELEGRAM__TOKEN": config.get("telegram_token", ""),
            "NANOBOT_CHANNELS__NOSTR__ENABLED": "true",
            "NANOBOT_CHANNELS__NOSTR__RELAY_URL": settings.NOSTR_RELAY_URL,
            # Defaults
            "NANOBOT_AGENTS__DEFAULTS__MODEL": config.get("model", "msp_gemini/gemini-3-pro-preview"),
        }
        
        metadata = {}
        
        # Identity Injection (Nostr Keypair)
        # If user didn't provide a key, generate one so we know who they are.
        if generate_keypair and "nostr_private_key" not in config:
            priv, pub = generate_keypair()
            env_vars["NANOBOT_CHANNELS__NOSTR__PRIVATE_KEY"] = priv
            env_vars["NANOBOT_CHANNELS__NOSTR__PUBLIC_KEY"] = pub
            metadata["nostr_public_key"] = pub
        
        # Add custom providers if present
        if "providers" in config:
            for provider, values in config["providers"].items():
                for k, v in values.items():
                    env_key = f"NANOBOT_PROVIDERS__{provider.upper()}__{k.upper()}"
                    env_vars[env_key] = str(v)
            
            # Special handling for OpenAI Base URL (LiteLLM requires OPENAI_API_BASE env var)
            if "openai" in config["providers"] and "base_url" in config["providers"]["openai"]:
                env_vars["OPENAI_API_BASE"] = str(config["providers"]["openai"]["base_url"])

        # Allow explicit env var injection
        if "env" in config:
            for k, v in config["env"].items():
                env_vars[k] = str(v)

        try:
            # Check if container exists
            try:
                existing = self.client.containers.get(agent_id)
                existing.remove(force=True)
            except docker.errors.NotFound:
                pass

            container = self.client.containers.run(
                image=settings.AGENT_IMAGE,
                name=agent_id,
                detach=True,
                network=settings.DOCKER_NETWORK,
                restart_policy={"Name": "unless-stopped"},
                environment=env_vars,
                command=f'nanobot gateway --port {config.get("port", "18793")}'
            )
            return {
                "container_id": container.id,
                "metadata": metadata
            }
        except Exception as e:
            raise RuntimeError(f"Failed to start container: {str(e)}")

    def stop_agent(self, agent_id: str):
        try:
            container = self.client.containers.get(agent_id)
            container.stop()
        except docker.errors.NotFound:
            pass
        except Exception as e:
            raise RuntimeError(f"Failed to stop container: {str(e)}")

    def remove_agent(self, agent_id: str):
        try:
            container = self.client.containers.get(agent_id)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            raise RuntimeError(f"Failed to remove container: {str(e)}")

    def get_status(self, agent_id: str) -> str:
        try:
            container = self.client.containers.get(agent_id)
            return container.status
        except docker.errors.NotFound:
            return "stopped"
