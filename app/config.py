import os
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv, find_dotenv
from requests.auth import HTTPProxyAuth

# Load environment variables (searches parent directories for .env).
load_dotenv(find_dotenv())

# Process-level proxy URL read from environment.
PROXY_URL = os.getenv("PROXY_URL")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
PROXY_VERIFY_SSL = os.getenv("PROXY_VERIFY_SSL", "true").lower() == "true"


def _proxy_url_with_auth() -> str | None:
    """
    Return the proxy URL with embedded credentials when provided.
    """
    if not PROXY_URL:
        return None

    parsed = urlsplit(PROXY_URL)
    if parsed.username:
        return PROXY_URL

    if PROXY_USERNAME and PROXY_PASSWORD:
        host = parsed.hostname or parsed.netloc
        if parsed.port:
            host = f"{host}:{parsed.port}"
        netloc = f"{PROXY_USERNAME}:{PROXY_PASSWORD}@{host}"
        return urlunsplit(
            (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
        )

    return PROXY_URL


def configure_global_proxy() -> None:
    """
    Configure environment variables so HTTP clients (requests, urllib, etc.)
    automatically route traffic through the proxy.
    """
    proxy_url = _proxy_url_with_auth()
    if not proxy_url:
        return

    # Many libraries honor these automatically when trust_env is True.
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ.setdefault("ALL_PROXY", proxy_url)
    # Lowercase variants for clients that expect them.
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url


def get_proxies() -> dict | None:
    """
    Helper for passing an explicit proxies={} mapping when needed.
    """
    proxy_url = _proxy_url_with_auth()
    if not proxy_url:
        return None
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def get_proxy_auth() -> HTTPProxyAuth | None:
    """
    Proxy auth helper for requests clients that require explicit credentials.
    """
    if PROXY_USERNAME and PROXY_PASSWORD:
        return HTTPProxyAuth(PROXY_USERNAME, PROXY_PASSWORD)
    return None


# Backwards compatible alias.
config_global_proxy = configure_global_proxy
