"""DEV-ONLY import stub for lilith_router.world_context (not the PROD module).

gateway_integration imports ``world_context`` at module level, but every one of its 18 uses is inside a
cognitive-lane branch (planning / ethics / reasoning / cognitive / goals) gated by ``cfg.<lane>_is_active``.
With every lane disabled in the DEV router.yaml, no attribute is ever accessed. If a lane is enabled anyway,
the missing attribute raises inside the existing try/except and the router fails open to the normal path.

The real module (PROD sha256 46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104) is Stage 2 of the
export plan and is REQUIRED before any cognitive lane is enabled on DEV.
"""

DEV_IMPORT_STUB = True
