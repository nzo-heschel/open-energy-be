import os


def use_nzo_fallback_only() -> bool:
    """
    Treat NZO as the source of truth for NOGA-backed endpoints by default.

    Set NOGA_USE_NZO_FALLBACK_ONLY=false to restore the old behavior where
    primary NOGA is tried first and NZO is used only after NOGA fails.
    """
    value = os.getenv("NOGA_USE_NZO_FALLBACK_ONLY", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}
