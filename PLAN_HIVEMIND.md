# Plan: Hive Mind Architecture (Secure Agent API Layer)

## 🎯 Objective
Transition from a monolithic "Sol manages Docker" model to a secure, decoupled **Agent API Proxy** architecture.
Sol will no longer have direct access to `docker.sock`. Instead, it will command a privileged `agent-api` service via HTTP with API Key authentication.

## 🏗 Architecture Changes

### 1. New Service: `agent_platform` (The Proxy)
A standalone FastAPI service that acts as the **infrastructure controller**.
*   **Role:** The only container with `/var/run/docker.sock` mounted.
*   **Tech Stack:** Python 3.12, FastAPI, Pydantic, Docker SDK (or CLI wrapper).
*   **Security:**
    *   **Auth:** Bearer Token (API Key) validation on all endpoints.
    *   **Isolation:** Runs in its own container, separate from agent logic.
*   **Extensibility:**
    *   Uses an `Orchestrator` interface.
    *   **Current Implementation:** `DockerOrchestrator`.
    *   **Future:** `K8sOrchestrator` (AKS).

### 2. Nanobot/Sol (The Agent)
*   **Deprecation:** Remove local `agent_manager` skill (which uses `subprocess.run(["docker"...])`).
*   **New Skill:** `RemoteAgentManager` (or refactored `AgentManager`).
    *   **Logic:** Sends HTTP requests to `http://agent-api:8000`.
    *   **Config:** Needs `AGENT_API_URL` and `AGENT_API_KEY`.
*   **Security:** **Remove** `/var/run/docker.sock` mount from `sol` container in `docker-compose.yml`.

## 📂 Proposed Directory Structure

```text
nanobot/
├── agent_platform/           # [NEW] The API Proxy Layer
│   ├── app/
│   │   ├── core/
│   │   │   ├── auth.py       # API Key validation
│   │   │   └── config.py     # Env vars (API_KEY, etc)
│   │   ├── routers/
│   │   │   └── agents.py     # Endpoints: /agents/spawn, /list, etc.
│   │   ├── services/
│   │   │   ├── orchestrator.py # Abstract Base Class
│   │   │   └── docker_ops.py   # Docker implementation (Moved from Sol)
│   │   └── main.py
│   ├── Dockerfile            # Specific for this service
│   └── requirements.txt      # fastapi, uvicorn, docker, pydantic
├── nanobot/
│   ├── skills/
│   │   ├── agent_manager/    # [REFACTOR] Becomes an HTTP Client
│   │   │   ├── tool.py
│   │   │   └── client.py     # Wrapper for API calls
│   │   └── ...
├── deployment/
│   └── docker-compose.yml    # [UPDATE] Add agent-api, secure Sol
└── ...
```

## 📝 Execution Plan

### Phase 1: Scaffold `agent_platform`
1.  Create `agent_platform` directory.
2.  Define `Orchestrator` interface (Abstract Base Class) to satisfy the "future AKS compatibility" requirement.
3.  Port logic from `nanobot/skills/agent_manager/tool.py` into `agent_platform/app/services/docker_ops.py`.

### Phase 2: Implement API & Auth
1.  Create FastAPI app in `agent_platform/app/main.py`.
2.  Implement `X-API-Key` or Bearer Token middleware.
3.  Expose endpoints:
    *   `POST /v1/agents` (Create/Run)
    *   `GET /v1/agents` (List)
    *   `DELETE /v1/agents/{id}` (Remove)
    *   `POST /v1/agents/{id}/action` (Start/Stop)

### Phase 3: Refactor Sol (The Client)
1.  Rewrite `nanobot/skills/agent_manager/tool.py` to use `requests` (or `httpx`) to talk to the new API.
2.  Remove all local Docker CLI calls from the skill.

### Phase 4: Deployment Config
1.  Update `deployment/docker-compose.yml`:
    *   Add `agent-api` service (mount `docker.sock` here).
    *   Remove `docker.sock` from `sol`.
    *   Inject `AGENT_API_KEY` into both services (via `.env`).

## ⚠️ Key Considerations
*   **Networking:** `sol` and `agent-api` must be on the same Docker network (`hive-net`).
*   **Persistence:** Where does `agent_platform` store state? (Currently, Sol uses FS `workspace/fleet`). The `agent_platform` should probably manage its own state or rely on Docker tags/labels as the source of truth to remain stateless. **Recommendation: Use Docker Labels to store metadata (Agent Name, Owner) to stay stateless.**
