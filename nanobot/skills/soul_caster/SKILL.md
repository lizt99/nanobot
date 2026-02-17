---
name: soul-caster
description: Hive Mother's Reproduction. Mint new identities.
tool:
  name: soul_caster
  description: Generate and encrypt new Soul identities (BIP340).
  parameters:
    type: object
    properties:
      action:
        type: string
        enum: [mint_soul, encrypt_soul]
      name:
        type: string
      role:
        type: string
      password:
        type: string
      soul_json:
        type: object
      master_key:
        type: string
    required: [action]
---
