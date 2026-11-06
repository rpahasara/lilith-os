"""LILITH Conversation Intelligence Router V2.

External, self-contained router that sits at the Hermes gateway turn-builder
seam and routes *social* conversation to the Groq social brain while leaving
technical/work turns on the native gpt-5.6-sol path. See ``gateway_integration``
for the single entry point the core calls.
"""

from __future__ import annotations

__all__ = ["gateway_integration", "classifier", "policy", "config", "state"]
__version__ = "2.0.0"
