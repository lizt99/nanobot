from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.auth import get_api_key
from app.db.database import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentResponse
from app.services.docker_ops import DockerOrchestrator

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(get_api_key)]
)

orchestrator = DockerOrchestrator()

@router.post("/", response_model=AgentResponse)
def create_agent(agent_in: AgentCreate, db: Session = Depends(get_db)):
    # Check if exists
    existing = db.query(Agent).filter(Agent.name == agent_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent with this name already exists")
    
    agent_id = str(uuid.uuid4())
    # Use name as container ID for simplicity/readability, or use UUID. 
    # Let's use name.lower() as the consistent ID for Docker
    docker_id = agent_in.name.lower()

    new_agent = Agent(
        id=docker_id, # Using name as ID for consistency with previous system
        name=agent_in.name,
        aieos_content=agent_in.aieos_content,
        runtime_config=agent_in.runtime_config,
        status="provisioning"
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    
    # Start Container
    try:
        result = orchestrator.start_agent(
            docker_id, 
            agent_in.name, 
            agent_in.aieos_content or {}, 
            agent_in.runtime_config or {}
        )
        new_agent.container_id = result.get("container_id")
        # Merge metadata into runtime_config if present
        if "metadata" in result and result["metadata"]:
            current_config = dict(new_agent.runtime_config) if new_agent.runtime_config else {}
            current_config.update(result["metadata"])
            new_agent.runtime_config = current_config
            
        new_agent.status = "running"
        db.commit()
    except Exception as e:
        new_agent.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
        
    return new_agent

@router.get("/", response_model=List[AgentResponse])
def list_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).all()
    # Sync status
    for agent in agents:
        current_status = orchestrator.get_status(agent.id)
        if current_status != agent.status:
            agent.status = current_status
            db.add(agent)
    db.commit()
    return agents

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    orchestrator.remove_agent(agent.id)
    db.delete(agent)
    db.commit()
    return {"detail": "Agent deleted"}

@router.post("/{agent_id}/stop")
def stop_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    orchestrator.stop_agent(agent.id)
    agent.status = "stopped"
    db.commit()
    return {"detail": "Agent stopped"}

@router.post("/{agent_id}/start")
def start_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    result = orchestrator.start_agent(
        agent.id, 
        agent.name, 
        agent.aieos_content, 
        agent.runtime_config
    )
    
    # Update config with new metadata (like ephemeral ports or fresh keys if rotated)
    if "metadata" in result and result["metadata"]:
        current_config = dict(agent.runtime_config) if agent.runtime_config else {}
        current_config.update(result["metadata"])
        agent.runtime_config = current_config

    agent.status = "running"
    db.commit()
    return {"detail": "Agent started"}
