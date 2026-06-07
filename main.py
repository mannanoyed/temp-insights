"""
meet-insights — CPU FastAPI service.

Accepts a raw transcript (text) + meeting_id, runs Gemini analysis,
returns structured insights: summary, action_items, insights dict.

Gemini calls are LIVE when GEMINI_API_KEY is set.
Returns stub data when the key is absent (safe for local integration testing).

POST /analyze
    Body: {"transcript_text": "...", "meeting_id": "..."}
    Returns: {"summary": "...", "action_items": [...], "insights": {...}}

GET /health
    Returns: {"status": "ok"}
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="meet-insights", version="1.0.0")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# =========================================
# Request / Response models
# =========================================

class AnalyzeRequest(BaseModel):
    transcript_text: str
    meeting_id: str = "unknown"
    meeting_type: Optional[str] = None      # standup | client-call | sprint-planning | …
    language_hint: Optional[str] = "hinglish"


class AnalyzeResponse(BaseModel):
    meeting_id: str
    summary: str
    action_items: List[Dict[str, Any]]
    insights: Dict[str, Any]
    model_used: str
    stub: bool = False                       # true when Gemini key is absent


# =========================================
# Gemini helpers
# =========================================

def _build_prompt(req: AnalyzeRequest) -> str:
    meeting_type_hint = f"Meeting type: {req.meeting_type}." if req.meeting_type else ""
    return f"""You are a meeting intelligence assistant. The transcript below is in {req.language_hint or 'English'}.
{meeting_type_hint}

TRANSCRIPT:
{req.transcript_text}

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
    """
    Call Gemini and parse the JSON response.
    Tries google.genai (new SDK) then falls back to google.generativeai (old SDK).
    """
    import json

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    raw_text = response.text

    # Strip any accidental markdown fences
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])

    return json.loads(cleaned.strip())


def _stub_response(meeting_id: str) -> AnalyzeResponse:
    """Returned when GEMINI_API_KEY is not configured."""
    return AnalyzeResponse(
        meeting_id=meeting_id,
        summary=(
            "STUB: Gemini API key not configured. "
            "Set GEMINI_API_KEY env var to enable real analysis."
        ),
        action_items=[
            {
                "task": "Configure GEMINI_API_KEY",
                "owner": "DevOps",
                "due": None,
                "priority": "high",
            }
        ],
        insights={
            "sentiment": "neutral",
            "key_decisions": [],
            "risks": ["Gemini not configured"],
            "blockers": [],
            "topics": [],
        },
        model_used="stub",
        stub=True,
    )


# =========================================
# Routes
# =========================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    if not req.transcript_text or not req.transcript_text.strip():
        raise HTTPException(status_code=400, detail="transcript_text is required and cannot be empty")

    logger.info(f"Analyze request: meeting_id={req.meeting_id} chars={len(req.transcript_text)}")

    # ---- Stub mode ----
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — returning stub response")
        return _stub_response(req.meeting_id)

    # ---- Live Gemini call ----
    try:
        prompt = _build_prompt(req)
        result = _call_gemini(prompt)

        return AnalyzeResponse(
            meeting_id=req.meeting_id,
            summary=result.get("summary", ""),
            action_items=result.get("action_items", []),
            insights=result.get("insights", {}),
            model_used="gemini-2.0-flash",
            stub=False,
        )

    except Exception as e:
        logger.error(f"Gemini call failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Gemini call failed: {str(e)}")
