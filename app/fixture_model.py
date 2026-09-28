"""Deterministic local inference double used only by automated tests."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import FastAPI


app = FastAPI(title="kops test-only fixture inference", docs_url=None, redoc_url=None)


@app.get("/api/tags")
def tags() -> dict[str, Any]:
    return {"models": [{"name": "fixture-governed-model"}]}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {"data": [{"id": "fixture-governed-model", "object": "model"}]}


def _source_ids(prompt: str) -> list[tuple[str, int]]:
    return [(source_id, int(revision)) for source_id, revision in re.findall(r'<source id="([^"]+)" revision="(\d+)"', prompt)]


def _page_ids(prompt: str) -> list[tuple[str, int]]:
    return [(document_id, int(version)) for document_id, version in re.findall(r'<page document_id="([^"]+)" version="(\d+)"', prompt)]


def _response(messages: list[dict[str, str]]) -> str:
    prompt = messages[-1]["content"]
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
        citations = [{"document_id": document_id, "version": version} for document_id, version in _page_ids(prompt)]
        question = prompt.lower()
        if "unanswerable" in question:
            result = {"answer": "The authorized pages do not support an answer.", "citations": [], "evaluation": "unsupported"}
        elif "conflict" in question:
            result = {"answer": "The authorized pages report conflicting schedule estimates.", "citations": citations, "evaluation": "contradictory"}
        else:
            result = {"answer": "The expansion plan includes calibration stations and a quality gate.", "citations": citations, "evaluation": "supported"}
    return json.dumps(result)


@app.post("/api/chat")
def ollama_chat(payload: dict[str, Any]) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": _response(payload["messages"])}, "done": True}


@app.post("/v1/chat/completions")
def openai_chat(payload: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": _response(payload["messages"])}}]}
