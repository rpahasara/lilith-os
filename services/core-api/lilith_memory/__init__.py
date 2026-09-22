"""Deployable, Git-governed Slice 15 canonical-memory runtime.

Importing this package never migrates a database, enables a capability, or
opens a production data path.  Schema changes are explicit operations in
``canonical_migration`` and production activation requires governed config.
"""

__all__ = (
    "backup",
    "canonical_authority",
    "canonical_contracts",
    "canonical_migration",
    "canonical_store",
    "config",
    "learning_v2",
    "memory_v2",
    "registry_loader",
)
