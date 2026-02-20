from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class AgentBase(BaseModel):
    name: str
    aieos_content: Optional[Dict[str, Any]] = None
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
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
