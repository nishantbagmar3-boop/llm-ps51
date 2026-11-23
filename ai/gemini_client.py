"""Thin wrapper around the Google GenAI SDK for the Gemini API.

All LLM calls in the application go through this module, so error handling,
model selection and generation settings live in exactly one place.

Run ``python -m ai.gemini_client`` for a quick connectivity test.
"""

import re
import time

import config


class GeminiClientError(Exception):
    """Raised when the Gemini API cannot be used (missing key, API failure...)."""


class GeminiClient:
    """Small facade over google-genai's Client for this application."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = (api_key if api_key is not None else config.GEMINI_API_KEY).strip()
        if not key:
            raise GeminiClientError(config.API_KEY_SETUP_MESSAGE)
        self.model = model or config.GEMINI_MODEL

        # Imported here so the app can start (and show the setup message)
        # even if the SDK import itself fails in a broken environment.
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiClientError(
                "The google-genai package is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc

        # JSON mode (response_mime_type="application/json") is only served by
        # the v1beta API version; the SDK's default ("v1") rejects it.
        self._client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(api_version="v1beta"),
        )

    # ------------------------------------------------------------------ #
    def generate_json(self, prompt: str) -> str:
        """Ask Gemini for a JSON-only response; returns the raw response text."""
        return self._generate(prompt, response_mime_type="application/json")

    def generate_text(self, prompt: str) -> str:
        """Plain-text generation."""
        return self._generate(prompt, response_mime_type=None)

    # The free tier allows only a few requests per minute; on a 429 the API
    # tells us how long to wait, so the client retries instead of failing.
    MAX_RATE_LIMIT_RETRIES = 3

    @staticmethod
    def _retry_delay_seconds(error_message: str) -> float:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_message)
        if match:
            return min(90.0, float(match.group(1)) + 2.0)
        return 35.0

    def _generate(self, prompt: str, response_mime_type: str | None) -> str:
        from google.genai import errors, types

        generation_config = types.GenerateContentConfig(
            temperature=0.0,  # deterministic extraction, no creative drift
            response_mime_type=response_mime_type,
        )
        response = None
        for attempt in range(1 + self.MAX_RATE_LIMIT_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=prompt, config=generation_config
                )
                break
            except errors.APIError as exc:
                if exc.code == 429 and attempt < self.MAX_RATE_LIMIT_RETRIES:
                    time.sleep(self._retry_delay_seconds(str(exc)))
                    continue
                raise GeminiClientError(
                    f"Gemini API call failed ({type(exc).__name__}): {exc}"
                ) from exc
            except Exception as exc:
                raise GeminiClientError(
                    f"Gemini API call failed ({type(exc).__name__}): {exc}"
                ) from exc

        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise GeminiClientError(
                "Gemini returned an empty response. Please try again."
            )
        return text

    # ------------------------------------------------------------------ #
    def make_repair_fn(self):
        """Return a repair function for json_parser.parse_and_validate: one
        limited attempt at fixing structurally invalid LLM JSON."""

        def repair(bad_output: str, error_message: str) -> str:
            prompt = (
                "The following output was supposed to be a single valid JSON "
                "object but failed parsing/validation.\n\n"
                f"ERROR:\n{error_message[:1500]}\n\n"
                f"OUTPUT TO FIX:\n{bad_output[:20000]}\n\n"
                "Return the corrected version as ONE valid JSON object. "
                "Keep every piece of information exactly as it is — fix only "
                "the JSON structure, data types and field names. "
                "Do not add, invent or remove any medical information. "
                "Return JSON only, with no commentary and no code fences."
            )
            return self.generate_json(prompt)

        return repair


def ping() -> str:
    """One tiny live call used to verify the API key and model are working."""
    client = GeminiClient()
    reply = client.generate_text("Reply with exactly: OK")
    return f"model={client.model} reply={reply.strip()[:40]}"


if __name__ == "__main__":
    print(ping())
