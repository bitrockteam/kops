"""Deterministic double of scripts/model_bridge.py, used only by automated tests.

Serves the same two routes as the real bridge (``GET /health``, ``POST /v1/complete``)
with fixture-only behavior selected by ``test_variant`` instead of a model name, since
the real protocol has no model field to select on.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="kops test-only fixture inference", docs_url=None, redoc_url=None)

FIXTURE_MODEL_ID = "fixture-governed-model"
FIXTURE_EFFORT = "high"
FIXTURE_BRIDGE_VERSION = "test-fixture"
FIXTURE_CLI_VERSION = "test-fixture"


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "bridge_version": FIXTURE_BRIDGE_VERSION,
        "cli_version": FIXTURE_CLI_VERSION,
        "requested_model": FIXTURE_MODEL_ID,
        "requested_effort": FIXTURE_EFFORT,
    }


def _source_ids(prompt: str) -> list[tuple[str, int]]:
    return [(source_id, int(revision)) for source_id, revision in re.findall(r'<source id="([^"]+)" revision="(\d+)"', prompt)]


def _page_ids(prompt: str) -> list[tuple[str, int]]:
    return [(document_id, int(version)) for document_id, version in re.findall(r'<page document_id="([^"]+)" version="(\d+)"', prompt)]


def _response(prompt: str) -> str:
    if "<source " in prompt:
        citations = [{"source_id": source_id, "revision": revision} for source_id, revision in _source_ids(prompt)]
        canary_present = "FIN-CANARY-7391" in prompt
        schedule = "Engineering estimates 18 weeks."
        contradictions: list[str] = []
        if canary_present:
            schedule += " Finance assumes 14 weeks, and the supplier estimates 16 weeks."
            contradictions.append("The sources contain 14, 16, and 18 week estimates.")
        result = {
            "pages": [
                {
                    "slug": "expansion-overview",
                    "title": "Aster Works expansion overview",
                    "markdown": f"# Expansion overview\n\n{schedule}\n\nThis maintained page was compiled from the admitted synthetic evidence.",
                    "citations": citations,
                },
                {
                    "slug": "schedule-comparison",
                    "title": "Schedule comparison",
                    "markdown": f"# Schedule comparison\n\n{schedule}",
                    "citations": citations,
                },
            ],
            "contradictions": contradictions,
            "quality_notes": ["Deterministic fixture output for repeatable tests only."],
        }
    else:
        # Deliberately cite only one supplied page so tests distinguish citations
        # from the complete input set that could influence the answer.
        citations = [{"document_id": document_id, "version": version} for document_id, version in _page_ids(prompt)[:1]]
        question = prompt.lower()
        if "unanswerable" in question:
            result = {"answer": "The authorized pages do not support an answer.", "citations": [], "evaluation": "unsupported"}
        elif "conflict" in question:
            result = {"answer": "The authorized pages report conflicting schedule estimates.", "citations": citations, "evaluation": "contradictory"}
        elif "reply with the single word" in question:
            return "OK"
        else:
            result = {"answer": "The expansion plan includes calibration stations and a quality gate.", "citations": citations, "evaluation": "supported"}
    return json.dumps(result)


@app.post("/v1/complete")
async def complete(payload: dict[str, Any]) -> Any:
    variant = payload.get("test_variant")
    if variant == "fixture-trickle":
        async def trickle():
            for _ in range(40):
                yield b" "
                await asyncio.sleep(0.1)
        return StreamingResponse(trickle(), media_type="application/json")
    if variant == "fixture-oversize":
        body = json.dumps({
            "text": "x" * 200000, "object": None, "model": FIXTURE_MODEL_ID, "effort": FIXTURE_EFFORT,
            "usage": {}, "duration_ms": 1, "bridge_version": FIXTURE_BRIDGE_VERSION,
        })
        return StreamingResponse(iter([body.encode("utf-8")]), media_type="application/json")
    text = _response(payload.get("prompt", ""))
    return {
        "text": text, "object": None, "model": FIXTURE_MODEL_ID, "effort": FIXTURE_EFFORT,
        "usage": {}, "duration_ms": 1, "bridge_version": FIXTURE_BRIDGE_VERSION,
    }
