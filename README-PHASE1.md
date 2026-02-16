# Phase 1: The Seed (Virtual Employee Bootstrap)

This setup allows you to run multiple independent `nanobot` instances ("Virtual Employees") using Docker Compose. Each bot has its own:
*   **Identity (Soul):** Defined in `souls/` directory.
*   **Memory:** Persisted in `data/<name>/memory`.
*   **Workspace:** Persisted in `data/<name>/workspace`.
*   **Telegram Bot:** Configured via `.env`.

## Prerequisites
*   Docker & Docker Compose installed.
*   Two Telegram Bot tokens (one for Bob, one for Alice).
*   OpenRouter API Key.

## Quick Start

1.  **Configure Environment:**
    ```bash
    cp .env.example .env
    # Edit .env and fill in your API keys and Tokens
    vim .env
    ```

2.  **Build Images:**
    ```bash
    docker-compose build
    ```

3.  **Launch Bob & Alice:**
    ```bash
    docker-compose up -d
    ```

4.  **Verify:**
    *   Check logs: `docker-compose logs -f`
    *   Talk to Bob via his Telegram Bot.
    *   Talk to Alice via her Telegram Bot.

## Directory Structure
*   `souls/`: Contains the "Soul" definitions (Markdown files).
    *   `bob.md`: Bob's persona.
    *   `alice.md`: Alice's persona.
*   `data/`: Persistent storage.
    *   `bob/memory/`: Bob's long-term memory.
    *   `alice/memory/`: Alice's long-term memory.
*   `docker-compose.yml`: Service definitions.

## Customization
To create a new bot (e.g., "Charlie"):
1.  Create `souls/charlie.md`.
2.  Add a `charlie` service to `docker-compose.yml` (copy/paste from `bob`).
3.  Add `CHARLIE_TELEGRAM_TOKEN` to `.env`.
4.  Run `docker-compose up -d`.
