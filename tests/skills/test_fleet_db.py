import sys
from unittest.mock import MagicMock

# Mock the base tool to avoid importing the whole agent package which requires Python 3.11
class MockTool:
    def __init__(self):
        pass
    
    @property
    def name(self):
        return "mock_tool"

# Setup mocks before importing the actual tool
mock_agent = MagicMock()
sys.modules["nanobot.agent"] = mock_agent
sys.modules["nanobot.agent.tools"] = MagicMock()
sys.modules["nanobot.agent.tools.base"] = MagicMock(Tool=MockTool)

import pytest
import sqlite3
import os
from nanobot.skills.fleet_db.tool import FleetDBTool

def test_fleet_db_schema(tmp_path):
    db_path = tmp_path / "fleet.db"
    # Ensure tool uses the provided db_path
    os.environ["FLEET_DB_PATH"] = str(db_path)
    
    # Tool should initialize DB on instantiation or first use
    tool = FleetDBTool()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
    assert cursor.fetchone() is not None
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    assert cursor.fetchone() is not None
    conn.close()

def test_agent_lifecycle(tmp_path):
    db_path = tmp_path / "fleet_lifecycle.db"
    os.environ["FLEET_DB_PATH"] = str(db_path)
    tool = FleetDBTool()
    
    # 1. Register
    tool.register_agent(name="TestBot", pubkey="pub123", role="worker")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, role, status FROM agents WHERE pubkey='pub123'")
    row = cursor.fetchone()
    assert row == ("TestBot", "worker", "online") # Assuming default status 'online' or similar
    
    # 2. Update Heartbeat
    tool.update_heartbeat(pubkey="pub123", status="busy")
    cursor.execute("SELECT status, last_seen FROM agents WHERE pubkey='pub123'")
    status, last_seen = cursor.fetchone()
    assert status == "busy"
    assert last_seen is not None
    conn.close()

def test_task_lifecycle(tmp_path):
    db_path = tmp_path / "fleet_tasks.db"
    os.environ["FLEET_DB_PATH"] = str(db_path)
    tool = FleetDBTool()
    
    tool.register_agent(name="WorkerBot", pubkey="pub456", role="worker")
    
    # 1. Create Task
    tool.create_task(agent_pubkey="pub456", command="echo hello")
    
    # 2. Get Pending Tasks
    tasks = tool.get_pending_tasks(agent_pubkey="pub456")
    assert len(tasks) == 1
    task_id = tasks[0]['id']
    assert tasks[0]['command'] == "echo hello"
    
    # 3. Complete Task
    tool.complete_task(task_id=task_id, result="hello")
    
    # Verify no longer pending
    tasks_after = tool.get_pending_tasks(agent_pubkey="pub456")
    assert len(tasks_after) == 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status, result FROM tasks WHERE id=?", (task_id,))
    status, result = cursor.fetchone()
    assert status == "completed"
    assert result == "hello"
    conn.close()
