from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.sql import func
from app.db.database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="stopped")
    container_id = Column(String, nullable=True)
    
    # AIEOS (Identity/Config) stored as JSON
    aieos_content = Column(JSON, nullable=True)
    
    # Runtime Config (tokens, ports, etc.)
    runtime_config = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
