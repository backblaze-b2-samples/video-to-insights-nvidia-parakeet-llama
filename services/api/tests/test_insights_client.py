"""Insights client: schema validation + transcript prompt construction."""

import json

import httpx
import pytest

from app.service import insights as insights_module
from app.types import Insight

CANNED_INSIGHTS = {
    "insights": [
        {
            "title": "Intro",
            "summary": "Speaker introduces the topic.",
            "start_seconds": 0.0,
            "end_seconds": 30.0,
            "key_quotes": ["welcome to the show"],
        },
        {
            "title": "Deep dive",
            "summary": "Detailed explanation of the architecture.",
            "start_seconds": 30.0,
            "end_seconds": 180.0,
            "key_quotes": [],
        },
    ]
}


def _transport(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}}],
            },
        )

    return httpx.MockTransport(handler)


def test_extract_insights_parses_json(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-token")

    transcript = {"segments": [{"start": 0.0, "end": 5.0, "text": "hello"}]}
    out = insights_module.extract_insights(transcript, transport=_transport(CANNED_INSIGHTS))
    assert len(out) == 2
    assert isinstance(out[0], Insight)
    assert out[0].title == "Intro"
    assert out[1].end_seconds == 180.0


def test_extract_insights_drops_malformed(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-token")

    bad = {"insights": [
        {"title": "ok", "summary": "ok", "start_seconds": 0, "end_seconds": 10},
        {"title": "missing times"},
    ]}
    transcript = {"segments": [{"start": 0, "end": 5, "text": "x"}]}
    out = insights_module.extract_insights(transcript, transport=_transport(bad))
    assert len(out) == 1
    assert out[0].title == "ok"


def test_empty_transcript_returns_empty(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-token")
    assert insights_module.extract_insights({"segments": []}) == []


def test_raises_without_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "")
    with pytest.raises(insights_module.InsightsError):
        insights_module.extract_insights({"segments": [{"start": 0, "end": 1, "text": "x"}]})
