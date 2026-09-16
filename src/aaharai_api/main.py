from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import GoogleTokenVerifier, verify_google_token, verify_google_token_async
from .catalog import FoodCatalog
from .groq import GroqFoodParser, GroqNotConfiguredError, GroqUpstreamError
from .models import FoodLogParseRequest, HealthResponse, MatchedFoodEntry, MatchedFoodLog
from .settings import ApiSettings


def create_app(
    settings: ApiSettings | None = None,
    *,
    groq_transport: httpx.AsyncBaseTransport | None = None,
    google_token_verifier: GoogleTokenVerifier = verify_google_token,
) -> FastAPI:
    settings = settings or ApiSettings()
    parser = GroqFoodParser(settings, transport=groq_transport)
    catalog = FoodCatalog(settings.food_catalog_path)
    app = FastAPI(title="AaharAI private API", version="0.1.0")
    bearer = HTTPBearer(auto_error=False)

    if settings.google_auth_required and not settings.google_oauth_client_id:
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID is required when GOOGLE_AUTH_REQUIRED=true"
        )

    async def require_google_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict | None:
        if not settings.google_auth_required:
            return None
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google sign-in is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await verify_google_token_async(
            credentials.credentials,
            settings.google_oauth_client_id or "",
            google_token_verifier,
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        key = settings.groq_api_key
        return HealthResponse(
            groq_configured=bool(key and key.get_secret_value()),
            google_auth_configured=bool(settings.google_oauth_client_id),
            google_auth_required=settings.google_auth_required,
            food_catalog_configured=catalog.configured,
        )

    @app.post("/v1/parse-food-log", response_model=MatchedFoodLog)
    async def parse_food_log(
        request: FoodLogParseRequest,
        _user: dict | None = Depends(require_google_user),
    ) -> MatchedFoodLog:
        try:
            parsed = await parser.parse(request.text)
            return MatchedFoodLog(
                entries=[
                    MatchedFoodEntry(
                        **entry.model_dump(),
                        candidates=catalog.search(entry.food_name),
                    )
                    for entry in parsed.entries
                ],
                ambiguities=parsed.ambiguities,
            )
        except GroqNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Food-language service is not configured",
            ) from exc
        except GroqUpstreamError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Food-language service could not parse this entry",
            ) from exc

    return app


app = create_app()
