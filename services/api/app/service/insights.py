"""NVIDIA Llama-3.3-70B-Instruct insights extractor (free NIM endpoint).

Given a Parakeet transcript with segment timestamps, ask the model to
identify 3-6 topical sections of the video and return a JSON array of
`Insight` objects. We use OpenAI-compatible chat-completions calls
against the NIM gateway so the same code shape can target any
OpenAI-compatible provider if someone forks the sample.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.types import Insight

logger = logging.getLogger(__name__)


class InsightsError(RuntimeError):
    """Raised when the insights call cannot complete or returns unusable JSON."""


SYSTEM_PROMPT = (
    "You analyze video transcripts and identify 3-6 distinct topical sections. "
    "Return a JSON object with an `insights` array. Each entry has: "
    "title (short label), summary (one sentence), start_seconds (number, "
    "inclusive lower bound), end_seconds (number, exclusive upper bound), and "
    "key_quotes (array of 0-3 short verbatim quotes). Times must align with "
    "the supplied transcript segments and be non-overlapping and monotonic."
)


def _build_user_prompt(transcript: dict[str, Any]) -> str:
    segments = transcript.get("segments", [])
    # Cap context: ~600 segments is plenty for a 90-min video at ~9s/segment.
    trimmed = segments[:600]
    lines = []
    for seg in trimmed:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        text = str(seg.get("text", "")).strip().replace("\n", " ")
        lines.append(f"[{start:.2f}-{end:.2f}] {text}")
    return "Transcript segments:\n" + "\n".join(lines)


def extract_insights(
    transcript: dict[str, Any],
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[Insight]:
    """Call Llama-3.3 and return validated Insight objects.

    Returns `[]` when the transcript is empty — the caller treats that
    as a successful no-op rather than a failure.
    """
    if not settings.nvidia_api_key:
        raise InsightsError("NVIDIA_API_KEY is not set")
    if not transcript.get("segments"):
        return []

    client_kwargs = dict(
        base_url=settings.nvidia_base_url,
        timeout=httpx.Timeout(120.0),
        headers={
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if transport is not None:
        client_kwargs["transport"] = transport

    body = {
        "model": settings.nvidia_insights_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(transcript)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 1500,
    }

    with httpx.Client(**client_kwargs) as client:
        resp = client.post("/chat/completions", json=body)
    if resp.status_code >= 400:
        raise InsightsError(f"NIM insights returned {resp.status_code}: {resp.text[:400]}")

    try:
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        raise InsightsError(f"NIM insights returned unparseable JSON: {e}") from e

    raw_items = parsed.get("insights", []) if isinstance(parsed, dict) else []
    insights: list[Insight] = []
    for i, item in enumerate(raw_items):
        try:
            insights.append(
                Insight(
                    index=i,
                    title=str(item["title"]),
                    summary=str(item["summary"]),
                    start_seconds=float(item["start_seconds"]),
                    end_seconds=float(item["end_seconds"]),
                    key_quotes=[str(q) for q in item.get("key_quotes", [])][:3],
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Dropping malformed insight at index %d: %s", i, e)
            continue
    return insights
