"""
Runtime Breeze session token storage.

ICICI redirects to the app redirect URL with ?apisession=<session_token> after login.
We persist that token in AppSettings (and Redis when available) so BREEZE_SESSION
does not need to be edited in .env every day.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.core import signing

from coredata.models import AppSettings

logger = logging.getLogger(__name__)

APP_SETTING_KEY = "BREEZE_SESSION"
REDIS_KEY = "breeze:session_token"
# Session is typically valid for the trading day; refresh via ICICI login.
REDIS_TTL_SECONDS = 20 * 60 * 60
_SIGNING_SALT = "breeze-session-v1"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{6,128}$")


def _redis_client():
    try:
        import redis

        return redis.Redis(
            host=getattr(settings, "REDIS_HOST", "localhost"),
            port=int(getattr(settings, "REDIS_PORT", 6379)),
            db=2,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        return None


def is_valid_session_token(token: str) -> bool:
    if not token or not isinstance(token, str):
        return False
    token = token.strip()
    return bool(_TOKEN_RE.match(token))


def _encode(token: str) -> str:
    # Prefer plain token in DB for reliability across SECRET_KEY changes.
    # Also accept previously signed values when reading.
    return token


def _decode(payload: str) -> str | None:
    payload = (payload or "").strip()
    if is_valid_session_token(payload):
        return payload
    try:
        value = signing.loads(payload, salt=_SIGNING_SALT)
        return value if isinstance(value, str) and is_valid_session_token(value) else None
    except signing.BadSignature:
        return None


def get_breeze_session() -> str:
    """Resolve session token: Redis → AppSettings → .env fallback."""
    client = _redis_client()
    if client is not None:
        try:
            cached = client.get(REDIS_KEY)
            if cached and is_valid_session_token(cached):
                return cached.strip()
        except Exception:
            logger.debug("Redis read for Breeze session failed", exc_info=True)

    try:
        row = AppSettings.objects.filter(key=APP_SETTING_KEY).only("value").first()
        if row and row.value:
            token = _decode(row.value.strip())
            if token and is_valid_session_token(token):
                _cache_token(token)
                return token
            logger.warning(
                "BREEZE_SESSION AppSettings row exists but token could not be decoded"
            )
    except Exception:
        logger.exception("Failed reading Breeze session from AppSettings")

    return (getattr(settings, "BREEZE_SESSION", "") or "").strip()


def set_breeze_session(token: str) -> str:
    """Persist session token in AppSettings + Redis. Returns the stored token."""
    token = (token or "").strip()
    if not is_valid_session_token(token):
        raise ValueError("Invalid Breeze session token format")

    AppSettings.objects.update_or_create(
        key=APP_SETTING_KEY,
        defaults={"value": _encode(token)},
    )
    _cache_token(token)
    logger.info("Breeze session token updated (runtime store)")
    return token


def clear_breeze_session() -> None:
    AppSettings.objects.filter(key=APP_SETTING_KEY).delete()
    client = _redis_client()
    if client is not None:
        try:
            client.delete(REDIS_KEY)
        except Exception:
            logger.debug("Redis delete for Breeze session failed", exc_info=True)


def _cache_token(token: str) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(REDIS_KEY, REDIS_TTL_SECONDS, token)
    except Exception:
        logger.debug("Redis write for Breeze session failed", exc_info=True)


def session_status() -> dict:
    token = get_breeze_session()
    return {
        "configured": bool(token),
        "source": _token_source(token),
        "preview": f"{token[:4]}…{token[-2:]}" if len(token) > 8 else ("set" if token else ""),
    }


def _token_source(token: str) -> str:
    if not token:
        return "none"
    client = _redis_client()
    if client is not None:
        try:
            if client.get(REDIS_KEY) == token:
                return "redis"
        except Exception:
            pass
    try:
        if AppSettings.objects.filter(key=APP_SETTING_KEY).exists():
            return "app_settings"
    except Exception:
        pass
    if (getattr(settings, "BREEZE_SESSION", "") or "").strip() == token:
        return "env"
    return "unknown"
