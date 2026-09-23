"""Isolated, synthetic-only Slice 15B2b-B1b-1 broker contracts.

This package has no socket, HTTP server, deployment entry point, or production
authority initializer. The governed ``lilith_memory`` package is a runtime
dependency, not the model-facing Core API process.
"""

__all__ = ("request", "protocol", "state", "core")
