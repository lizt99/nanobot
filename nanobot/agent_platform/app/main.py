from fastapi import FastAPI
from app.routers import agents
from app.db.database import Base, engine

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nanobot Agent Platform API")

app.include_router(agents.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
