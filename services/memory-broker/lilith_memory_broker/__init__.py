"""Isolated, synthetic-only Memory Broker contracts and DEV runtime candidate.

The B1b-2a adapter accepts only an inherited AF_UNIX listener; it never binds
or installs one. There is no HTTP server or production authority initializer.
The governed ``lilith_memory`` contract package is a dependency, not the
model-facing Core API process.
"""

__all__ = ("request", "protocol", "state", "core", "dev_config", "dev_proof", "dev_state", "synthetic_evidence", "dev_core", "server")
