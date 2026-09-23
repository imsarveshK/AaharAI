import json
import asyncio

import httpx
from pydantic import SecretStr

from aaharai_api.main import create_app
from aaharai_api.models import ParsedFoodLog
from aaharai_api.settings import ApiSettings


def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://aaharai.test"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_does_not_expose_key():
    app = create_app(ApiSettings(groq_api_key=SecretStr("private-test-key")))
    response = request(app, "GET", "/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "groqConfigured": True,
        "googleAuthConfigured": False,
        "googleAuthRequired": False,
        "foodCatalogConfigured": True,
    }
    assert "private-test-key" not in response.text


def test_food_parse_uses_strict_schema_without_nutrition_fields():
    captured: dict = {}
    parsed = {
        "entries": [
            {
                "originalText": "Monday breakfast two rotis",
                "foodName": "roti",
                "modifiers": [],
                "quantityValue": 2,
                "quantityUnit": "roti",
                "dayOfWeek": "monday",
                "meal": "breakfast",
                "cookingMethod": None,
                "stateOrUt": None,
                "district": None,
                "settlementType": None,
                "qualityCue": None,
                "needsConfirmation": True,
            }
        ],
        "ambiguities": ["Roti weight is required for nutrient calculation"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(parsed)}}]},
        )

    settings = ApiSettings(
        groq_api_key=SecretStr("private-test-key"),
        groq_base_url="https://groq.test/v1",
    )
    app = create_app(settings, groq_transport=httpx.MockTransport(handler))
    response = request(
        app, "POST", "/v1/parse-food-log", json={"text": "Monday breakfast two rotis"}
    )

    assert response.status_code == 200
    assert response.json()["entries"][0]["foodName"] == "roti"
    roti = next(
        item for item in response.json()["entries"][0]["candidates"] if item["name"] == "Roti"
    )
    assert roti["energyKcalPer100g"] is not None
    assert roti["proteinGPer100g"] is not None
    assert roti["carbohydrateGPer100g"] is not None
    assert roti["fatGPer100g"] is not None
    assert "energyKcalPer100G" not in roti
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["temperature"] == 0
    assert captured["max_completion_tokens"] == 8_192
    quantity_unit_schema = captured["response_format"]["json_schema"]["schema"]["$defs"][
        "ParsedFoodEntry"
    ]["properties"]["quantityUnit"]
    assert "enum" not in json.dumps(quantity_unit_schema)
    schema_text = json.dumps(captured["response_format"]["json_schema"]["schema"]).lower()
    for forbidden in ("calories", "energy", "protein", "carbohydrates", "nutrients"):
        assert f'"{forbidden}"' not in schema_text
    assert "private-test-key" not in json.dumps(captured)


def test_samosa_uses_nin_2024_serving_and_quarantines_conflicting_indb_row():
    from aaharai_api.catalog import FoodCatalog

    catalog = FoodCatalog(ApiSettings().food_catalog_path)
    candidates = catalog.search("potato samosa")

    assert all(candidate.name != "Potato samosa" for candidate in candidates)
    samosa = candidates[0]
    assert samosa.name == "Samosa"
    assert samosa.serving_unit == "samosa"
    assert samosa.energy_kcal_per_serving == 200
    assert samosa.energy_kcal_per_100g is None
    assert samosa.fat_g_per_100g is None
    assert samosa.source_label == "ICMR-NIN Dietary Guidelines for Indians 2024"
    assert samosa.source_url == (
        "https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf"
    )


def test_parse_reports_unconfigured_server_without_fallback():
    app = create_app(ApiSettings(groq_api_key=None))
    response = request(app, "POST", "/v1/parse-food-log", json={"text": "one banana"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Food-language service is not configured"


def test_missing_portion_is_never_silently_confirmed():
    parsed = {
        "entries": [
            {
                "originalText": "sambar",
                "foodName": "sambar",
                "modifiers": [],
                "quantityValue": None,
                "quantityUnit": None,
                "dayOfWeek": "tuesday",
                "meal": "dinner",
                "cookingMethod": None,
                "stateOrUt": None,
                "district": None,
                "settlementType": None,
                "qualityCue": None,
                "needsConfirmation": False,
            }
        ],
        "ambiguities": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(parsed)}}]},
        )

    app = create_app(
        ApiSettings(groq_api_key=SecretStr("private-test-key"), groq_base_url="https://groq.test/v1"),
        groq_transport=httpx.MockTransport(handler),
    )
    response = request(app, "POST", "/v1/parse-food-log", json={"text": "sambar"})

    assert response.status_code == 200
    assert response.json()["entries"][0]["needsConfirmation"] is True
    assert response.json()["ambiguities"] == ["Portion is missing for sambar"]


def test_catalog_returns_clean_verified_options_for_indian_dish():
    parsed = {
        "entries": [
            {
                "originalText": "samosa",
                "foodName": "samosa",
                "modifiers": [],
                "quantityValue": 1,
                "quantityUnit": "piece",
                "dayOfWeek": None,
                "meal": "snack",
                "cookingMethod": None,
                "stateOrUt": None,
                "district": None,
                "settlementType": None,
                "qualityCue": None,
                "needsConfirmation": True,
            }
        ],
        "ambiguities": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(parsed)}}]},
        )

    app = create_app(
        ApiSettings(groq_api_key=SecretStr("private-test-key"), groq_base_url="https://groq.test/v1"),
        groq_transport=httpx.MockTransport(handler),
    )
    response = request(app, "POST", "/v1/parse-food-log", json={"text": "samosa"})
    assert response.status_code == 200
    candidates = response.json()["entries"][0]["candidates"]
    assert {item["name"] for item in candidates} == {"Samosa"}
    assert candidates[0]["sourceLabel"] == "ICMR-NIN Dietary Guidelines for Indians 2024"


def test_google_auth_rejects_missing_bearer_token():
    app = create_app(
        ApiSettings(
            groq_api_key=SecretStr("private-test-key"),
            google_oauth_client_id="web-client.apps.googleusercontent.com",
            google_auth_required=True,
        )
    )
    response = request(app, "POST", "/v1/parse-food-log", json={"text": "one banana"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Google sign-in is required"


def test_google_auth_accepts_server_verified_token():
    parsed = {"entries": [], "ambiguities": []}

    def groq_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(parsed)}}]},
        )

    seen: dict[str, str] = {}

    def verify(token: str, audience: str) -> dict:
        seen.update(token=token, audience=audience)
        return {"sub": "user-1", "email": "student@example.com", "email_verified": True}

    app = create_app(
        ApiSettings(
            groq_api_key=SecretStr("private-test-key"),
            groq_base_url="https://groq.test/v1",
            google_oauth_client_id="web-client.apps.googleusercontent.com",
            google_auth_required=True,
        ),
        groq_transport=httpx.MockTransport(groq_handler),
        google_token_verifier=verify,
    )
    response = request(
        app,
        "POST",
        "/v1/parse-food-log",
        headers={"Authorization": "Bearer real-id-token"},
        json={"text": "one banana"},
    )
    assert response.status_code == 200
    assert seen == {
        "token": "real-id-token",
        "audience": "web-client.apps.googleusercontent.com",
    }


def test_auth_required_refuses_to_start_without_client_id():
    try:
        create_app(ApiSettings(google_auth_required=True, google_oauth_client_id=None))
    except RuntimeError as exc:
        assert "GOOGLE_OAUTH_CLIENT_ID" in str(exc)
    else:
        raise AssertionError("Expected missing Google client ID to fail at startup")
