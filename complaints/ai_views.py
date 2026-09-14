import json
import os
import urllib.error
import urllib.request

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import WorkerProfile


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _extract_output_text(response_data):
    """
    OpenAI Responses API response se
    first output_text return karta hai.
    """

    for item in response_data.get("output", []):
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")

    return ""


@login_required(login_url="login")
@require_POST
def analyze_complaint_ai(request):
    """
    Complaint Description analyze karta hai.

    Return:
    - category
    - priority
    - summary
    """

    # =====================================================
    # REQUEST JSON READ
    # =====================================================

    try:
        body = json.loads(
            request.body.decode("utf-8")
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError
    ):

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request data.",
            },
            status=400,
        )

    # =====================================================
    # DESCRIPTION
    # =====================================================

    description = str(
        body.get(
            "description",
            ""
        )
    ).strip()

    # =====================================================
    # DESCRIPTION VALIDATION
    # =====================================================

    if len(description) < 10:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Please write at least 10 characters "
                    "in Complaint Description."
                ),
            },
            status=400,
        )

    if len(description) > 5000:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Complaint Description is too long. "
                    "Please keep it under 5000 characters."
                ),
            },
            status=400,
        )

    # =====================================================
    # OPENAI API KEY
    # =====================================================

    api_key = os.environ.get(
        "OPENAI_API_KEY",
        ""
    ).strip()

    if not api_key:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "AI is not configured on the server. "
                    "OPENAI_API_KEY is missing."
                ),
            },
            status=503,
        )

    # =====================================================
    # MODEL
    # =====================================================

    model = os.environ.get(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    ).strip()

    if not model:
        model = "gpt-5.6-luna"

    # =====================================================
    # CATEGORY LIST
    # WorkerProfile se automatically li ja rahi hai
    # =====================================================

    categories = [
        value
        for value, label
        in WorkerProfile.SKILL_CHOICES
    ]

    # =====================================================
    # AI INSTRUCTION
    # =====================================================

    developer_instruction = (
        "You are the AI complaint analyzer for a smart "
        "complaint management system. "

        "Analyze only the complaint description supplied "
        "by the user. "

        f"Choose the service category from exactly these "
        f"values: {', '.join(categories)}. "

        "Choose priority from exactly these values: "
        "Normal, High, Emergency. "

        "Emergency must only be selected when there is an "
        "immediate safety threat or serious danger, such as "
        "exposed live electrical wires, fire, major flooding, "
        "or another situation requiring immediate attention. "

        "High means the issue is important or time-sensitive "
        "but is not an immediate emergency. "

        "Normal means a routine complaint. "

        "Write a short factual summary in simple English. "

        "Do not invent any information that the user did not "
        "provide."
    )

    # =====================================================
    # OPENAI REQUEST BODY
    # =====================================================

    request_payload = {

        "model": model,

        # Complaint analysis response ko API-side
        # conversation state ke roop me store nahi karna.
        "store": False,

        "input": [

            {
                "role": "developer",

                "content": [
                    {
                        "type": "input_text",
                        "text": developer_instruction,
                    }
                ],
            },

            {
                "role": "user",

                "content": [
                    {
                        "type": "input_text",
                        "text": description,
                    }
                ],
            },
        ],

        # =================================================
        # STRUCTURED JSON OUTPUT
        # =================================================

        "text": {

            "format": {

                "type": "json_schema",

                "name": "complaint_analysis",

                "description": (
                    "Complaint category, priority "
                    "and short summary."
                ),

                "strict": True,

                "schema": {

                    "type": "object",

                    "properties": {

                        "category": {
                            "type": "string",
                            "enum": categories,
                        },

                        "priority": {
                            "type": "string",

                            "enum": [
                                "Normal",
                                "High",
                                "Emergency",
                            ],
                        },

                        "summary": {
                            "type": "string",
                        },
                    },

                    "required": [
                        "category",
                        "priority",
                        "summary",
                    ],

                    "additionalProperties": False,
                },
            }
        },

        "max_output_tokens": 250,
    }

    # =====================================================
    # HTTP REQUEST
    # =====================================================

    openai_request = urllib.request.Request(

        OPENAI_RESPONSES_URL,

        data=json.dumps(
            request_payload
        ).encode(
            "utf-8"
        ),

        headers={
            "Authorization": (
                f"Bearer {api_key}"
            ),

            "Content-Type": (
                "application/json"
            ),
        },

        method="POST",
    )

    # =====================================================
    # CALL OPENAI
    # =====================================================

    try:

        with urllib.request.urlopen(
            openai_request,
            timeout=30,
        ) as response:

            response_data = json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

    # =====================================================
    # OPENAI HTTP ERROR
    # =====================================================

    except urllib.error.HTTPError as error:

        try:

            error_body = json.loads(
                error
                .read()
                .decode(
                    "utf-8"
                )
            )

            api_message = (
                error_body
                .get(
                    "error",
                    {}
                )
                .get(
                    "message",
                    ""
                )
            )

        except Exception:

            api_message = ""

        print(
            "OPENAI AI ANALYZER HTTP ERROR:",
            error.code,
            api_message,
        )

        return JsonResponse(
            {
                "success": False,

                "error": (
                    "AI analysis is temporarily unavailable. "
                    "Please choose the priority manually "
                    "and continue."
                ),
            },
            status=502,
        )

    # =====================================================
    # CONNECTION / TIMEOUT ERROR
    # =====================================================

    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:

        print(
            "OPENAI AI ANALYZER CONNECTION ERROR:",
            error,
        )

        return JsonResponse(
            {
                "success": False,

                "error": (
                    "AI analysis is temporarily unavailable. "
                    "Please choose the priority manually "
                    "and continue."
                ),
            },
            status=502,
        )

    # =====================================================
    # GET AI OUTPUT
    # =====================================================

    output_text = (
        _extract_output_text(
            response_data
        )
    )

    if not output_text:

        return JsonResponse(
            {
                "success": False,

                "error": (
                    "AI did not return an analysis. "
                    "Please choose the priority manually."
                ),
            },
            status=502,
        )

    # =====================================================
    # JSON RESULT
    # =====================================================

    try:

        analysis = json.loads(
            output_text
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,

                "error": (
                    "AI returned an invalid result. "
                    "Please choose the priority manually."
                ),
            },
            status=502,
        )

    # =====================================================
    # RESULT VALUES
    # =====================================================

    category = str(
        analysis.get(
            "category",
            ""
        )
    ).strip()

    priority = str(
        analysis.get(
            "priority",
            ""
        )
    ).strip()

    summary = str(
        analysis.get(
            "summary",
            ""
        )
    ).strip()

    # =====================================================
    # FINAL SERVER-SIDE SAFETY VALIDATION
    # =====================================================

    if category not in categories:

        if "Other" in categories:
            category = "Other"

        else:
            category = categories[-1]

    if priority not in {
        "Normal",
        "High",
        "Emergency",
    }:

        priority = "Normal"

    if not summary:

        summary = description[:240]

    # =====================================================
    # SEND RESULT TO BROWSER
    # =====================================================

    return JsonResponse(
        {
            "success": True,
            "category": category,
            "priority": priority,
            "summary": summary[:500],
        }
    )