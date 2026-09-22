import json
import os
import urllib.error
import urllib.request


GEMINI_API_BASE = (
    "https://generativelanguage.googleapis.com/v1beta/models"
)


GEMINI_TIMEOUT_SECONDS = int(
    os.environ.get(
        "GEMINI_TIMEOUT_SECONDS",
        "20",
    )
)

GEMINI_THINKING_LEVEL = (
    os.environ.get(
        "GEMINI_THINKING_LEVEL",
        "minimal",
    )
    .strip()
    .lower()
)

ALLOWED_THINKING_LEVELS = {
    "minimal",
    "low",
    "medium",
    "high",
}

if GEMINI_THINKING_LEVEL not in ALLOWED_THINKING_LEVELS:
    GEMINI_THINKING_LEVEL = "minimal"


class GeminiServiceError(Exception):
    def __init__(
        self,
        code,
        message,
        http_status=502,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _extract_text(response_data):
    candidates = response_data.get(
        "candidates",
        [],
    )

    for candidate in candidates:

        content = candidate.get(
            "content",
            {},
        )

        for part in content.get(
            "parts",
            [],
        ):
            text = part.get("text")

            if text:
                return str(text).strip()

    return ""


def _usage_counts(response_data):
    usage = response_data.get(
        "usageMetadata",
        {},
    )

    input_tokens = int(
        usage.get(
            "promptTokenCount",
            0,
        )
        or 0
    )

    total_tokens = int(
        usage.get(
            "totalTokenCount",
            0,
        )
        or 0
    )

    candidate_tokens = int(
        usage.get(
            "candidatesTokenCount",
            0,
        )
        or 0
    )

    thoughts_tokens = int(
        usage.get(
            "thoughtsTokenCount",
            0,
        )
        or 0
    )

    # Using total - prompt is conservative because output pricing
    # can include thinking tokens.
    derived_output = max(
        total_tokens - input_tokens,
        0,
    )

    output_tokens = max(
        derived_output,
        candidate_tokens + thoughts_tokens,
    )

    if total_tokens <= 0:
        total_tokens = (
            input_tokens
            + output_tokens
        )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def gemini_generate_json(
    *,
    system_instruction,
    user_text,
    response_schema,
    max_output_tokens=300,
    temperature=0.1,
):
    """
    Small dependency-free Gemini REST client.

    GEMINI_API_KEY is read only on the Django server.
    """

    api_key = os.environ.get(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise GeminiServiceError(
            "gemini_key_missing",
            (
                "AI is not configured on the server. "
                "GEMINI_API_KEY is missing."
            ),
            503,
        )

    model = os.environ.get(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    ).strip()

    if not model:
        model = "gemini-3.5-flash-lite"

    url = (
        f"{GEMINI_API_BASE}/"
        f"{model}:generateContent"
    )

    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text":
                        system_instruction,
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_text,
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature":
                temperature,
            "maxOutputTokens":
                max_output_tokens,
            "thinkingConfig": {
                "thinkingLevel":
                    GEMINI_THINKING_LEVEL,
            },
            "responseMimeType":
                "application/json",
            "responseSchema":
                response_schema,
        },
    }

    request_obj = urllib.request.Request(
        url,
        data=json.dumps(
            payload,
        ).encode(
            "utf-8"
        ),
        headers={
            "Content-Type":
                "application/json",
            "x-goog-api-key":
                api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request_obj,
            timeout=GEMINI_TIMEOUT_SECONDS,
        ) as response:
            response_data = json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

    except urllib.error.HTTPError as error:

        try:
            body = json.loads(
                error
                .read()
                .decode(
                    "utf-8"
                )
            )

            api_message = (
                body
                .get(
                    "error",
                    {},
                )
                .get(
                    "message",
                    "",
                )
            )

        except Exception:
            api_message = ""

        print(
            "GEMINI HTTP ERROR:",
            error.code,
            api_message,
        )

        if error.code == 404:
            raise GeminiServiceError(
                "gemini_model_unavailable",
                (
                    "The configured AI model is unavailable. "
                    "Please continue manually while the server configuration is updated."
                ),
                503,
            )

        if error.code == 429:
            raise GeminiServiceError(
                "gemini_rate_limit",
                (
                    "AI is busy right now. "
                    "Please try again shortly."
                ),
                503,
            )

        if error.code in {
            401,
            403,
        }:
            raise GeminiServiceError(
                "gemini_auth_error",
                (
                    "AI server configuration needs attention."
                ),
                503,
            )

        raise GeminiServiceError(
            "gemini_http_error",
            (
                "AI analysis is temporarily unavailable. "
                "Please continue manually."
            ),
            502,
        )

    except (
        urllib.error.URLError,
        TimeoutError,
    ) as error:

        print(
            "GEMINI CONNECTION ERROR:",
            error,
        )

        raise GeminiServiceError(
            "gemini_connection_error",
            (
                "AI could not connect right now. "
                "Please continue manually."
            ),
            502,
        )

    except json.JSONDecodeError as error:

        print(
            "GEMINI RESPONSE JSON ERROR:",
            error,
        )

        raise GeminiServiceError(
            "gemini_invalid_response",
            (
                "AI returned an invalid response. "
                "Please continue manually."
            ),
            502,
        )

    output_text = _extract_text(
        response_data
    )

    if not output_text:
        raise GeminiServiceError(
            "gemini_empty_response",
            (
                "AI did not return an analysis. "
                "Please continue manually."
            ),
            502,
        )

    try:
        parsed = json.loads(
            output_text
        )

    except json.JSONDecodeError:
        raise GeminiServiceError(
            "gemini_invalid_json",
            (
                "AI returned an invalid result. "
                "Please continue manually."
            ),
            502,
        )

    return {
        "data": parsed,
        "usage": _usage_counts(
            response_data
        ),
        "model": model,
    }
