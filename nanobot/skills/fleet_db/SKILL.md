---
name: fleet-db
description: Hive Mother's Database. Tracks agent state (heartbeat, tasks) via SQLite.
tool:
  name: fleet_db
  description: Manage the fleet database (agents, tasks).
  parameters:
    type: object
    properties:
      action:
        type: string
        enum: [register_agent, update_heartbeat, create_task, get_pending_tasks, complete_task]
      name:
        type: string
      pubkey:
        type: string
      role:
        type: string
      status:
        type: string
      command:
        type: string
      task_id:
        type: integer
      result:
        type: string
    required: [action]
---
