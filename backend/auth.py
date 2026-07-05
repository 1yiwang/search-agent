"""API auth tokens for personal deployment (Step 31)."""
import hashlib
import hmac
import time

from config import config


def issue_token(ttl_seconds: int | None = None) -> str:
    """Issue HMAC token valid for ttl_seconds."""
    if ttl_seconds is None:
        ttl_seconds = config.api_token_ttl_seconds
    exp = int(time.time()) + ttl_seconds
    payload = str(exp)
    sig = hmac.new(
        config.api_auth_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str) -> bool:
    """Verify token signature and expiry."""
    if not token or not config.api_auth_secret:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    payload, sig = parts
    try:
        exp = int(payload)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    expected = hmac.new(
        config.api_auth_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def verify_site_password(password: str) -> bool:
    if not config.site_password:
        return True
    return hmac.compare_digest(password, config.site_password)
