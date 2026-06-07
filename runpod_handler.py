"""
meet-insights — RunPod serverless handler.

Replaces the FastAPI app with a proper runpod.serverless.start() handler
so it doesn't crash-loop on RunPod.

Input shape (event['input']):
{
    "transcript_text": "...",          # required
    "meeting_id":      "abc-123",      # optional, default "unknown"
    "meeting_type":    "client-call",  # optional
    "language_hint":   "hinglish",     # optional, default "hinglish"
}

Output:
{
    "status":       "success",
    "meeting_id":   "...",
    "summary":      "...",
    "action_items": [...],
    "insights":     {...},
    "model_used":   "gemini-2.5-flash",
    "stub":         false
}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import runpod
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# =========================================
# Gemini helpers  (unchanged logic from main.py)
# =========================================

def _build_prompt(transcript_text: str, meeting_type: Optional[str], language_hint: str) -> str:
    meeting_type_hint = f"Meeting type: {meeting_type}." if meeting_type else ""
    return f"""You are a meeting intelligence assistant. The transcript below is in {language_hint or 'English'}.
{meeting_type_hint}

TRANSCRIPT:
{transcript_text}

Return a JSON object with exactly these keys:
{{
  "summary": "<3-4 paragraph English summary>",
  "action_items": [
    {{"task": "<task>", "owner": "<name or UNKNOWN>", "due": "<date or null>", "priority": "high|medium|low"}}
  ],
  "insights": {{
    "sentiment": "positive|neutral|negative|mixed",
    "key_decisions": ["<decision>"],
    "risks": ["<risk>"],
    "blockers": ["<blocker>"],
    "topics": ["<topic>"]
  }}
}}

Rules:
- Output ONLY valid JSON. No markdown fences.
- Translate all content to English.
- If a field cannot be determined write null or [].
"""


def _call_gemini(prompt: str) -> Dict[str, Any]:
    raw_text = ""
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw_text = response.text
    except ImportError:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        raw_text = response.text

    # Strip any accidental markdown fences
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])

    return json.loads(cleaned.strip())


def _stub_result(meeting_id: str) -> Dict[str, Any]:
    """Returned when GEMINI_API_KEY is not configured."""
    return {
        "status": "success",
        "meeting_id": meeting_id,
        "summary": (
            "STUB: Gemini API key not configured. "
            "Set GEMINI_API_KEY env var to enable real analysis."
        ),
        "action_items": [
            {
                "task": "Configure GEMINI_API_KEY",
                "owner": "DevOps",
                "due": None,
                "priority": "high",
            }
        ],
        "insights": {
            "sentiment": "neutral",
            "key_decisions": [],
            "risks": ["Gemini not configured"],
            "blockers": [],
            "topics": [],
        },
        "model_used": "stub",
        "stub": True,
    }


# =========================================
# RunPod handler
# =========================================

def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        input_data = event.get("input", {}) or {}

        transcript_text: str = input_data.get("transcript_text", "").strip()
        meeting_id: str = input_data.get("meeting_id", "unknown")
        meeting_type: Optional[str] = input_data.get("meeting_type")
        language_hint: str = input_data.get("language_hint", "hinglish")

        if not transcript_text:
            return {
                "status": "error",
                "error_type": "ValidationError",
                "message": "transcript_text is required and cannot be empty",
            }

        logger.info(f"Analyze request: meeting_id={meeting_id} chars={len(transcript_text)}")

        # ---- Stub mode ----
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set — returning stub response")
            return _stub_result(meeting_id)

        # ---- Live Gemini call ----
        prompt = _build_prompt(transcript_text, meeting_type, language_hint)
        result = _call_gemini(prompt)

        return {
            "status": "success",
            "meeting_id": meeting_id,
            "summary": result.get("summary", ""),
            "action_items": result.get("action_items", []),
            "insights": result.get("insights", {}),
            "model_used": "gemini-2.5-flash",
            "stub": False,
        }

    except Exception as e:
        logger.error(f"Handler failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
        }


# =========================================
# RunPod entrypoint
# =========================================
if __name__ == "__main__":
    logger.info("Starting meet-insights RunPod serverless handler")
    runpod.serverless.start({"handler": handler})
