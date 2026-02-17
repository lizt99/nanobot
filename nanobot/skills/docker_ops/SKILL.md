---
name: docker-ops
description: Hive Mother's Hands. Spawn and manage containers.
tool:
  name: docker_ops
  description: Manage Docker containers (spawn, kill, logs).
  parameters:
    type: object
    properties:
      action:
        type: string
        enum: [list_containers, inspect_container, spawn_container, stop_container, get_logs]
      name:
        type: string
      image:
        type: string
      env_vars:
        type: object
      tail:
        type: integer
      all:
        type: boolean
    required: [action]
---
