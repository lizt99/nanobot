from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

# --- AIEOS v1.1 Standard Schema ---

class AIEOSNames(BaseModel):
    first: str
    nickname: Optional[str] = None

class AIEOSIdentity(BaseModel):
    names: AIEOSNames
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

class AIEOSPsychology(BaseModel):
    traits: Optional[List[str]] = None
    neural_matrix: Optional[Dict[str, Any]] = None # e.g. {"creativity": 0.8}

class AIEOSCapabilities(BaseModel):
    skills: List[str] = Field(default_factory=list, description="List of skill names to enable")
    tools: Optional[List[str]] = None

class AIEOSMotivations(BaseModel):
    core_drive: Optional[str] = None
    goals: Optional[List[str]] = None

# --- Custom Connectivity Fields ---

class TelegramConfig(BaseModel):
    token: str
    enabled: bool = True

class NostrConfig(BaseModel):
    public_key: Optional[str] = None
    private_key: Optional[str] = None
    relays: Optional[List[str]] = None

class LLMConfig(BaseModel):
    model: Optional[str] = None
    providers: Optional[Dict[str, Any]] = None

class AgentConnectivity(BaseModel):
    telegram: TelegramConfig # Mandatory
    nostr: Optional[NostrConfig] = None
    llm: Optional[LLMConfig] = None

class AIEOSContent(BaseModel):
    """
    Standard AIEOS (AI Entity Object Specification) Schema.
    Enforces structure for Soul definition.
    """
    spec_version: str = "1.1"
    identity: AIEOSIdentity
    psychology: Optional[AIEOSPsychology] = None
    capabilities: Optional[AIEOSCapabilities] = None
    motivations: Optional[AIEOSMotivations] = None
    history: Optional[Dict[str, Any]] = None # occupation etc
    linguistics: Optional[Dict[str, Any]] = None
    
    # Custom Extension for Agent Platform
    connectivity: Optional[AgentConnectivity] = None

# --- API Request/Response Schemas ---

class AgentBase(BaseModel):
    name: str
    # Enforce AIEOS structure, but allow None for raw agents
    aieos_content: Optional[AIEOSContent] = None 
    runtime_config: Optional[Dict[str, Any]] = None

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    status: Optional[str] = None
    container_id: Optional[str] = None

class AgentResponse(AgentBase):
    id: str
    status: str
    container_id: Optional[str] = None
    created_at: Any
    updated_at: Optional[Any] = None

    class Config:
        from_attributes = True
