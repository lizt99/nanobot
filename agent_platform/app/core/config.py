from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_KEY: str = "sk-secure-key-123456"
    DATABASE_URL: str = "sqlite:///./agents.db"
    DOCKER_NETWORK: str = "hive-net"
    AGENT_IMAGE: str = "deployment-sol"
    NOSTR_RELAY_URL: str = "ws://nostr-relay:8080"
    
    class Config:
        env_file = ".env"

settings = Settings()
