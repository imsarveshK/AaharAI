from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleTokenError(Exception):
    """Raised when a Google ID token cannot be accepted."""


GoogleTokenVerifier = Callable[[str, str], dict[str, Any]]


def verify_google_token(token: str, audience: str) -> dict[str, Any]:
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=audience,
        )
    except Exception as exc:
        raise GoogleTokenError("Google ID token verification failed") from exc

    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise GoogleTokenError("Unexpected Google token issuer")
    if claims.get("email_verified") is not True:
        raise GoogleTokenError("Google account email is not verified")
    if not claims.get("sub") or not claims.get("email"):
        raise GoogleTokenError("Google token is missing required identity claims")
    return claims


async def verify_google_token_async(
    token: str,
    audience: str,
    verifier: GoogleTokenVerifier = verify_google_token,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(verifier, token, audience)
    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google sign-in",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
