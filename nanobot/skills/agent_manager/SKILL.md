---
name: agent-manager
description: Manage the lifecycle of fleet agents (create, start, stop, remove, list) using standardized deployment scripts.
tool:
  name: agent_manager
  description: Create and manage fleet agents.
  parameters:
    type: object
    properties:
      action:
        type: string
        enum: [create, start, stop, remove, list, status]
      name:
        type: string
        description: The name of the agent (e.g., 'bob').
      telegram_token:
        type: string
        description: The Telegram Bot Token for the agent (required for 'create').
      model:
        type: string
        description: LLM Model override (optional, defaults to system default).
    required: [action]
---