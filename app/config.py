import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables (searches parent directories for .env).
load_dotenv(find_dotenv())

# Process-level proxy URL read from environment.
PROXY_URL = os.getenv("PROXY_URL")


def configure_global_proxy() -> None:
    """
    Configure environment variables so HTTP clients (requests, urllib, etc.)
    automatically route traffic through the proxy.
    """
    if not PROXY_URL:
        return

    # Many libraries honor these automatically when trust_env is True.
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ.setdefault("ALL_PROXY", PROXY_URL)
    # Lowercase variants for clients that expect them.
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL


def get_proxies() -> dict | None:
    """
    Helper for passing an explicit proxies={} mapping when needed.
    """
    if not PROXY_URL:
        return None
    return {
        "http": PROXY_URL,
        "https": PROXY_URL,
    }


# Backwards compatible alias.
config_global_proxy = configure_global_proxy
