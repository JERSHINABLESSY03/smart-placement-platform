import json
import os
from urllib import error, request


class GeminiServiceError(Exception):
    """A safe, user-facing error returned by the Gemini integration."""

    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


SYSTEM_INSTRUCTION = (
    "You are a supportive, accurate tutor for students preparing for technical "
    "placement interviews. Explain concepts clearly, use step-by-step reasoning "
    "when helpful, adapt to the student's level, and distinguish facts from "
    "assumptions. Do not claim to have executed code or checked external systems. "
    "For practice questions, create original questions and include answers with "
    "brief explanations only after the question. For hints, provide a useful "
    "nudge without immediately revealing the complete solution. Encourage the "
    "student to attempt problems independently."
)

MODE_INSTRUCTIONS = {
    "concept": "Explain the requested concept, give an intuitive example, then summarize key interview points.",
    "coding": "Explain the code or programming concept. Discuss complexity when relevant; never claim code was executed.",
    "aptitude": "Explain the aptitude problem step by step and show the reasoning clearly.",
    "dbms": "Explain the DBMS concept with a practical example and interview-relevant distinctions.",
    "sql": "Explain the SQL query or concept, including assumptions and expected behavior.",
    "practice": "Generate original placement-practice questions at the requested level. Include a separate answer key with concise explanations.",
    "hint": "Give progressive hints, starting with a small nudge. Do not reveal a full solution unless the student asks.",
    "mistake": "Diagnose the student's described mistake constructively, explain the underlying misconception, and suggest a correction.",
    "recommendation": "Suggest a realistic study plan based on the student's stated goals, available time, and weak areas.",
}


class GeminiService:
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    @classmethod
    def generate_reply(cls, mode, prompt, history):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or api_key == "your-gemini-api-key":
            raise GeminiServiceError(
                "The AI tutor is not configured. Add a valid GEMINI_API_KEY to the server .env file."
            )

        model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
        contents = [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in history
        ]
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            f"{SYSTEM_INSTRUCTION}\n\n"
                            f"Current tutoring mode: {MODE_INSTRUCTIONS[mode]}"
                        )
                    }
                ]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 1200,
            },
        }
        http_request = request.Request(
            cls.API_URL.format(model=model),
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code == 429:
                raise GeminiServiceError(
                    "The AI tutor is receiving too many requests. Please wait a moment and try again.",
                    status_code=429,
                ) from exc
            if exc.code in (401, 403):
                raise GeminiServiceError(
                    "The AI provider rejected the server API key. Check the GEMINI_API_KEY configuration."
                ) from exc
            if exc.code >= 500:
                raise GeminiServiceError(
                    "The AI provider is temporarily unavailable. Please try again shortly."
                ) from exc
            raise GeminiServiceError(
                "The AI provider could not process this request. Please revise it and try again."
            ) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise GeminiServiceError(
                "The AI tutor could not be reached. Check the server connection and try again."
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GeminiServiceError(
                "The AI provider returned an unreadable response. Please try again."
            ) from exc

        try:
            parts = payload["candidates"][0]["content"]["parts"]
            reply = "\n".join(part["text"] for part in parts if isinstance(part.get("text"), str)).strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise GeminiServiceError(
                "The AI tutor did not return a usable answer. Please try again."
            ) from exc
        if not reply:
            raise GeminiServiceError(
                "The AI tutor returned an empty answer. Please ask in a different way."
            )
        return reply
