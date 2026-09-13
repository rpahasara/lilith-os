# LILITH Core API

The LILITH Core API is the current FastAPI backend for LILITH.

It provides durable state and backend capabilities including career intelligence,
tasks, goals, world-model state, memory-backed views, system health, and governed
interaction with the Hermes runtime.

## Architecture boundary

LILITH and Hermes are separate systems.

- LILITH owns identity, durable state, goals, policy, verification, cognition,
  continuity, and presence.
- Hermes provides runtime and execution capabilities.
- This API may integrate with Hermes, but Hermes is not LILITH.

## Runtime configuration

The service supports the following environment variables:

- `LILITH_HOME` - LILITH runtime user home directory.
- `HERMES_HOME` - Hermes runtime directory.
- `LILITH_DATA_DIR` - directory containing LILITH runtime data.
- `LILITH_DB_PATH` - path to the primary LILITH SQLite database.
- `WORLD_MAINT_INTERVAL_SEC` - world-model maintenance interval.

Production secrets and runtime state must not be committed to Git.

The following remain deployment/runtime concerns:

- `.env`
- SQLite databases
- WAL/SHM files
- authority keys
- OAuth credentials and tokens
- Hermes runtime state
- logs
- backups
- Python virtual environments

## Current production defaults

When no overrides are supplied, the current runtime layout resolves from the
runtime user home directory and Hermes directory.

The production GCP VM currently runs the API through systemd with Uvicorn.

## Local development

Create a virtual environment:

    python -m venv .venv

Install dependencies:

    python -m pip install -r requirements.txt

Run the API:

    uvicorn app:app --reload --port 8765

## Tests

The imported Goal / Executive System tests use a temporary SQLite database and
do not require the production LILITH database.

Run:

    python -m unittest discover -s tests -p "test_*.py" -v

## Source of truth

Git is the canonical source for backend code.

GCP is a deployment target and runtime environment, not the canonical source
repository.
