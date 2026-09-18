from __future__ import annotations

import logging

import httpx

from .models import ParsedFoodLog
from .settings import ApiSettings


SYSTEM_PROMPT = """
Extract only what the user said about foods, portions, days/meals, cooking methods,
Indian location, settlement type, and observable quality cues. Normalize food names for
catalog search. Never calculate, estimate, or return calories, macros, micronutrients, or
nutrient retention. Do not guess an omitted portion, location, cooking method, or quality.
Use null and needsConfirmation=true when an answer is required before matching real data.
Keep a stated portion with only the food it grammatically measures. Do not copy a plate, bowl,
or other quantity to an accompanying food whose quantity was not stated.
Preserve every explicitly stated addition or style in modifiers instead of dropping it. For
example, "poha with peanuts" has foodName "poha" and modifiers ["peanuts"].
""".strip()

LOGGER = logging.getLogger("aaharai_api.groq")


class GroqNotConfiguredError(RuntimeError):
    pass


class GroqUpstreamError(RuntimeError):
    pass


class GroqFoodParser:
    def __init__(
        self,
        settings: ApiSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def parse(self, text: str) -> ParsedFoodLog:
        key = self._settings.groq_api_key
        if key is None or not key.get_secret_value():
            raise GroqNotConfiguredError("GROQ_API_KEY is not configured on the server")

        payload = {
            "model": self._settings.groq_model,
            "temperature": 0,
            "max_completion_tokens": 8_192,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "aaharai_food_log",
                    "strict": True,
                    "schema": ParsedFoodLog.model_json_schema(by_alias=True),
                },
            },
        }
        headers = {"Authorization": f"Bearer {key.get_secret_value()}"}
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.groq_base_url,
                timeout=self._settings.groq_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post("/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                completion = response.json()
            content = completion["choices"][0]["message"]["content"]
            return require_missing_portion_confirmation(
                ParsedFoodLog.model_validate_json(content)
            )
        except httpx.HTTPStatusError as exc:
            try:
                provider_error = exc.response.json().get("error", {})
                provider_code = provider_error.get("code", "unknown")
                provider_message = provider_error.get("message", "unspecified error")
            except (TypeError, ValueError):
                provider_code = "unparseable"
                provider_message = "unparseable provider error"
            LOGGER.error(
                "Groq rejected the structured-output request: HTTP %s, code %s: %s",
                exc.response.status_code,
                provider_code,
                str(provider_message)[:1_000],
            )
            raise GroqUpstreamError("Groq could not parse this food log") from exc
        except httpx.HTTPError as exc:
            LOGGER.error("Groq transport failed: %s", type(exc).__name__)
            raise GroqUpstreamError("Groq could not parse this food log") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            LOGGER.error("Groq returned an invalid food-log response: %s", type(exc).__name__)
            # Do not expose the upstream body or authorization details to the app.
            raise GroqUpstreamError("Groq could not parse this food log") from exc


def require_missing_portion_confirmation(parsed: ParsedFoodLog) -> ParsedFoodLog:
    entries = []
    ambiguities = list(parsed.ambiguities)
    for entry in parsed.entries:
        missing_portion = entry.quantity_value is None or entry.quantity_unit is None
        if missing_portion:
            entries.append(entry.model_copy(update={"needs_confirmation": True}))
            message = f"Portion is missing for {entry.food_name}"
            if message not in ambiguities:
                ambiguities.append(message)
        else:
            entries.append(entry)
    return parsed.model_copy(update={"entries": entries, "ambiguities": ambiguities})
