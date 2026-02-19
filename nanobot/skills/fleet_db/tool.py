import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Optional

from nanobot.agent.tools.base import Tool

class FleetDBTool(Tool):
    """
    Tool for managing the Hive Mother's fleet database.
    Tracks agents, their status, and assigns tasks.
    """

    def __init__(self):
        # Default to workspace/fleet.db if not set
        self.db_path = os.environ.get("FLEET_DB_PATH", "/root/.nanobot/workspace/fleet/fleet.db")
        self._init_db()

    def _get_connection(self):
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                pubkey TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                status TEXT,
                last_seen TIMESTAMP
            )
        """)
        
        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_pubkey TEXT,
                command TEXT,
                status TEXT,
                result TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY(agent_pubkey) REFERENCES agents(pubkey)
            )
        """)
        
        conn.commit()
        conn.close()

    @property
    def name(self) -> str:
        return "fleet_db"

    @property
    def description(self) -> str:
        return "Manage the fleet of agents: register, heartbeat, tasks."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["register_agent", "update_heartbeat", "create_task", "get_pending_tasks", "complete_task"],
                    "description": "The action to perform"
                },
                "name": {"type": "string"},
                "pubkey": {"type": "string"},
                "role": {"type": "string"},
                "status": {"type": "string"},
                "agent_pubkey": {"type": "string"},
                "command": {"type": "string"},
                "task_id": {"type": "integer"},
                "result": {"type": "string"}
            },
            "required": ["action"]
        }

    def register_agent(self, name: str, pubkey: str, role: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        # Check if exists to determine insert or update logic if needed, 
        # but REPLACE INTO or INSERT OR REPLACE is easier for "Insert/Update"
        cursor.execute("""
            INSERT INTO agents (pubkey, name, role, status, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(pubkey) DO UPDATE SET
                name=excluded.name,
                role=excluded.role,
                status=excluded.status,
                last_seen=excluded.last_seen
        """, (pubkey, name, role, "online", now))
        
        conn.commit()
        conn.close()
        return f"Agent {name} ({pubkey}) registered."

    def update_heartbeat(self, pubkey: str, status: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        cursor.execute("""
            UPDATE agents 
            SET status = ?, last_seen = ?
            WHERE pubkey = ?
        """, (status, now, pubkey))
        
        if cursor.rowcount == 0:
            # Maybe implicit registration or error? 
            # Requirements say "Update last_seen and status".
            # If agent not found, we probably shouldn't crash but maybe return warning.
            pass
            
        conn.commit()
        conn.close()
        return f"Heartbeat updated for {pubkey}."

    def create_task(self, agent_pubkey: str, command: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        cursor.execute("""
            INSERT INTO tasks (agent_pubkey, command, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (agent_pubkey, command, "pending", now, now))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def get_pending_tasks(self, agent_pubkey: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE agent_pubkey = ? AND status = 'pending'
        """, (agent_pubkey,))
        
        rows = cursor.fetchall()
        tasks = [dict(row) for row in rows]
        conn.close()
        return tasks

    def complete_task(self, task_id: int, result: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        cursor.execute("""
            UPDATE tasks
            SET status = ?, result = ?, updated_at = ?
            WHERE id = ?
        """, ("completed", result, now, task_id))
        
        conn.commit()
        conn.close()
        return f"Task {task_id} completed."

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "register_agent":
            return self.register_agent(
                name=kwargs.get("name"), 
                pubkey=kwargs.get("pubkey"), 
                role=kwargs.get("role")
            )
        elif action == "update_heartbeat":
            return self.update_heartbeat(
                pubkey=kwargs.get("pubkey"), 
                status=kwargs.get("status")
            )
        elif action == "create_task":
            tid = self.create_task(
                agent_pubkey=kwargs.get("agent_pubkey"), 
                command=kwargs.get("command")
            )
            return str(tid)
        elif action == "get_pending_tasks":
            tasks = self.get_pending_tasks(
                agent_pubkey=kwargs.get("agent_pubkey")
            )
            return json.dumps(tasks, default=str)
        elif action == "complete_task":
            return self.complete_task(
                task_id=kwargs.get("task_id"), 
                result=kwargs.get("result")
            )
        else:
            return f"Unknown action: {action}"