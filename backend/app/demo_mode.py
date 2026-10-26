"""Small runtime configuration helper for the optional presentation mode."""

import os


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "false").strip().casefold() in {"1", "true", "yes", "on"}
