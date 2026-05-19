import os


def use_nzo_fallback_only() -> bool:
    """
    Source selection for NOGA-backed endpoints.

    Default (False): try NOGA first and use NZO only if NOGA fails. NOGA is
    reachable again from the (Israeli) production server, while the NZO
    mirror's domain no longer resolves — so NOGA is the live source and NZO
    is the automatic fallback if NOGA ever goes down. This is self-healing:
    whichever source is up gets used, NOGA preferred.

    Set NOGA_USE_NZO_FALLBACK_ONLY=true to force NZO-only (skip NOGA
    entirely) — only useful if NOGA is down AND NZO is back up.
    """
    value = os.getenv("NOGA_USE_NZO_FALLBACK_ONLY", "false").strip().lower()
    return value not in {"0", "false", "no", "off"}
