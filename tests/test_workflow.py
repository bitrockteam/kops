from __future__ import annotations

import os
import re
import time

import httpx
import psycopg
import pytest

from app.config import Settings
from app.model import BridgeModelClient, ModelError


BASE_URL = os.getenv("KOPS_TEST_BASE_URL", "http://127.0.0.1:8080")


def _csrf(client: httpx.Client, path: str = "/") -> str:
    response = client.get(path)
    response.raise_for_status()
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match, response.text[:500]
    return match.group(1)


def _post(client: httpx.Client, path: str, data: dict | list[tuple[str, str]]) -> httpx.Response:
    if isinstance(data, dict):
        data = {**data, "csrf": _csrf(client)}
    else:
        data = [*data, ("csrf", _csrf(client))]
    return client.post(path, data=data, follow_redirects=True)


def _switch(client: httpx.Client, subject_id: str) -> None:
    response = _post(client, "/session/persona", {"subject_id": subject_id})
    assert response.status_code == 200
    assert subject_id.replace("_", " ").split()[0].lower() in response.text.lower() or "persona changed" in response.text.lower()


def _source_id(html: str, title: str) -> str:
    pattern = rf'<article class="card">\s*<h3>{re.escape(title)}</h3>.*?href="/sources/([0-9a-f-]+)"'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"source not found: {title}"
    return match.group(1)


def _wait_for_candidate(client: httpx.Client, timeout: float = 30) -> str:
    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        response = client.get("/api/state")
        response.raise_for_status()
        state = response.json()
        if state["jobs"]:
            last_state = state["jobs"][0]
            if last_state["status"] == "ready":
                assert last_state["candidate_id"]
                return last_state["candidate_id"]
            if last_state["status"] in {"failed", "blocked", "cancelled"}:
                pytest.fail(f"job ended as {last_state}")
        time.sleep(0.5)
    pytest.fail(f"job did not complete: {last_state}")


def _authorize_and_publish(client: httpx.Client, candidate_id: str) -> str:
    _switch(client, "reviewer")
    review = client.get(f"/?stage=review&candidate={candidate_id}")
    review.raise_for_status()
    assert "Complete admitted manifest" in review.text
    verified = _post(
        client,
        f"/candidates/{candidate_id}/verify",
        {"decision": "verified", "findings": "Independent fixture acceptance checked the exact hash and manifest."},
    )
    assert "Candidate verified" in verified.text

    _switch(client, "publisher")
    authorized = _post(client, f"/candidates/{candidate_id}/authorize", {})
    assert "created separately from verification" in authorized.text
    match = re.search(r'action="/operations/([0-9a-f-]+)/publish"', authorized.text)
    assert match, authorized.text[:1000]
    operation_id = match.group(1)
    published = _post(client, f"/operations/{operation_id}/publish", {})
    assert "page revisions are visible" in published.text
    return operation_id


@pytest.mark.integration
def test_local_model_receive_is_deadline_and_byte_bounded():
    model = BridgeModelClient(frozenset({"fixture-model"}))
    config = {
        "endpoint": "http://fixture-model:8090",
        "test_variant": "fixture-trickle",
        "limits": {"wall_time_seconds": 1, "max_output_bytes": 1024, "max_output_tokens": 100},
    }
    started = time.monotonic()
    with pytest.raises(ModelError, match="wall-time limit"):
        model.answer(config, "test")
    assert time.monotonic() - started < 3

    config["test_variant"] = "fixture-oversize"
    with pytest.raises(ModelError, match="output byte limit"):
        model.answer(config, "test")

    config["test_variant"] = "fixture-trickle"
    config["limits"]["wall_time_seconds"] = 10
    started = time.monotonic()
    with pytest.raises(ModelError, match="cancelled"):
        model.compile(config, "test", cancelled=lambda: time.monotonic() - started > 0.5)
    assert time.monotonic() - started < 2


@pytest.mark.integration
def test_governed_workflow_is_persistent_authorized_and_revocable():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        deadline = time.monotonic() + 30
        while True:
            try:
                if client.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                pytest.fail("API did not become ready")
            time.sleep(0.5)

        unknown_persona = _post(client, "/session/persona", {"subject_id": "attacker_supplied_admin"})
        assert unknown_persona.status_code == 400
        assert "unknown synthetic persona" in unknown_persona.text

        configured = _post(
            client,
            "/model/save",
            {
                "max_input_bytes": "60000",
                "max_output_bytes": "30000",
                "max_output_tokens": "1000",
                "wall_time_seconds": "30",
                "max_retries": "1",
            },
        )
        assert "Reachable" in configured.text
        fixtures = _post(client, "/fixtures/load", {})
        assert "Synthetic corpus is ready" in fixtures.text

        _switch(client, "dual_compiler")
        sources_page = client.get("/?stage=sources")
        engineering_id = _source_id(sources_page.text, "Engineering expansion plan")
        finance_id = _source_id(sources_page.text, "Finance budget")

        preview = _post(
            client,
            "/admission/preview",
            {"audience_id": "engineering", "source_ids": [engineering_id, finance_id]},
        )
        assert "Refused hidden or incompatible inputs: 1" in preview.text
        assert "FIN-CANARY-7391" not in preview.text

        queued = _post(
            client,
            "/jobs/create",
            {"audience_id": "engineering", "source_ids": [engineering_id], "task_text": "Compile the Engineering expansion knowledge."},
        )
        assert "queued" in queued.text
        engineering_candidate = _wait_for_candidate(client)
        engineering_operation = _authorize_and_publish(client, engineering_candidate)

        read_page = client.get("/?stage=read")
        document_match = re.search(r'href="/documents/([0-9a-f-]+)">Read current page', read_page.text)
        assert document_match
        engineering_document = document_match.group(1)
        delivered = client.get(f"/documents/{engineering_document}")
        delivered.raise_for_status()
        assert "FIN-CANARY-7391" not in delivered.text
        assert "Read audit receipt" in delivered.text

        _switch(client, "operator_admin")
        replay = _post(client, "/demo/replay-publication", {})
        assert engineering_operation in replay.text
        assert "without a duplicate revision" in replay.text

        _switch(client, "dual_compiler")
        joint_job = _post(
            client,
            "/jobs/create",
            {"audience_id": "joint", "source_ids": [engineering_id, finance_id], "task_text": "Compile the joint schedule and budget assessment."},
        )
        assert "queued" in joint_job.text
        joint_candidate = _wait_for_candidate(client)
        _authorize_and_publish(client, joint_candidate)
        _switch(client, "dual_compiler")
        joint_catalog = client.get("/?stage=read")
        joint_cards = re.findall(r'<article class="card"><h3>.*?</article>', joint_catalog.text, re.DOTALL)
        joint_document = None
        for card in joint_cards:
            if "joint" in card:
                match = re.search(r'/documents/([0-9a-f-]+)', card)
                if match:
                    joint_document = match.group(1)
                    break
        assert joint_document
        assert client.get(f"/documents/{joint_document}").status_code == 200

        answered = _post(
            client,
            "/query",
            {"audience_id": "joint", "question": "Which schedule estimates conflict?"},
        )
        response_match = re.search(r'href="/responses/([0-9a-f-]+)">Inspect answer artifact', answered.text)
        assert response_match
        response_id = response_match.group(1)
        assert "contradictory" in answered.text
        with psycopg.connect(Settings.load("api").database_url) as connection:
            citation_count, input_count = connection.execute(
                """
                SELECT jsonb_array_length(q.citations), count(qi.document_id)
                FROM kops.query_responses q
                JOIN kops.query_response_inputs qi ON qi.response_id = q.response_id
                WHERE q.response_id = %s GROUP BY q.response_id
                """,
                (response_id,),
            ).fetchone()
        assert citation_count == 1
        assert input_count > citation_count
        promoted = _post(client, f"/responses/{response_id}/save-candidate", {})
        assert "it is not published" in promoted.text
        promoted_match = re.search(r"private candidate ([0-9a-f-]+)", promoted.text)
        assert promoted_match
        promoted_candidate = promoted_match.group(1)
        promoted_review = client.get(f"/?stage=review&candidate={promoted_candidate}")
        assert promoted_review.status_code == 200
        admitted_table = re.search(r"Complete admitted manifest</h3>(.*?)</table>", promoted_review.text, re.DOTALL)
        assert admitted_table
        assert "Engineering expansion plan" in admitted_table.group(1)
        assert "Finance budget" in admitted_table.group(1)
        supported = _post(
            client,
            "/query",
            {"audience_id": "joint", "question": "What equipment does the expansion use?"},
        )
        assert "supported" in supported.text
        unsupported = _post(
            client,
            "/query",
            {"audience_id": "joint", "question": "This is an unanswerable question about lunar offices."},
        )
        assert "unsupported" in unsupported.text

        revised = _post(client, "/fixtures/revise-budget", {})
        assert "dependent pages are stale" in revised.text
        stale_page = client.get(f"/documents/{joint_document}")
        assert stale_page.status_code == 200
        assert "State: stale" in stale_page.text

        _switch(client, "operator_admin")
        revoked = _post(
            client,
            "/access/membership",
            {"subject_id": "dual_compiler", "group_id": "finance"},
        )
        assert "revoked" in revoked.text
        _switch(client, "dual_compiler")
        denied_current = client.get(f"/documents/{joint_document}")
        assert denied_current.status_code == 404
        assert "Page not available for this session or current access" in denied_current.text
        assert f'href="/documents/{joint_document}"' not in denied_current.text
        assert client.get(f"/documents/{joint_document}?version=1").status_code == 404
        assert client.get(f"/responses/{response_id}").status_code == 403
        assert response_id not in client.get("/?stage=read").text

        with psycopg.connect(Settings.load("api").database_url) as connection:
            joint_audit_correlation = connection.execute(
                "SELECT correlation_id FROM kops.audit_events WHERE resource_id = %s AND audience_id = 'joint' LIMIT 1",
                (response_id,),
            ).fetchone()[0]
        _switch(client, "auditor")
        assert joint_audit_correlation in client.get("/?stage=audit").text
        _switch(client, "operator_admin")
        revoke_auditor = _post(client, "/access/membership", {"subject_id": "auditor", "group_id": "finance"})
        assert "revoked" in revoke_auditor.text
        _switch(client, "auditor")
        assert joint_audit_correlation not in client.get("/?stage=audit").text
        _switch(client, "operator_admin")
        recovery_csrf = _csrf(client)
        disabled = client.post("/demo/audit-availability", data={"csrf": recovery_csrf}, follow_redirects=False)
        assert disabled.status_code == 303
        assert "deliberately+unavailable" in disabled.headers["location"]
        assert client.get("/").status_code == 503
        assert client.get("/api/state").status_code == 503
        assert client.get("/documents/00000000-0000-0000-0000-000000000000").status_code == 503
        assert client.get(f"/documents/{engineering_document}").status_code == 503
        restored = client.post("/demo/audit-availability", data={"enabled": "true", "csrf": recovery_csrf}, follow_redirects=True)
        assert "available" in restored.text
        assert client.get(f"/documents/{engineering_document}").status_code == 200

        unreachable = _post(client, "/demo/model-availability", {"enabled": "false"})
        assert "deliberately unreachable" in unreachable.text
        blocked_read = client.get("/?stage=read")
        assert "Questions are blocked" in blocked_read.text
        assert "<button disabled>Ask local model</button>" in blocked_read.text
        blocked_compile = client.get("/?stage=compile")
        assert "Compilation is blocked" in blocked_compile.text

        injected_title = "<script>alert(1)</script>"
        imported = _post(
            client,
            "/sources/import",
            {"title": injected_title, "audience_id": "engineering", "content": "Synthetic markup boundary check."},
        )
        assert "Source revision 1 imported" in imported.text
        sources = client.get("/?stage=sources")
        match = re.search(
            r"&lt;script&gt;alert\(1\)&lt;/script&gt;.*?href=\"/sources/([0-9a-f-]+)\"",
            sources.text,
            re.DOTALL,
        )
        assert match
        source_detail = client.get(f"/sources/{match.group(1)}")
        assert source_detail.status_code == 200
        assert "<script>" not in source_detail.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in source_detail.text

        restored_membership = _post(
            client,
            "/access/membership",
            {"subject_id": "dual_compiler", "group_id": "finance", "active": "true"},
        )
        assert "active" in restored_membership.text
        _switch(client, "dual_compiler")
        assert client.get(f"/responses/{response_id}").status_code == 200
        _switch(client, "operator_admin")
        changed_policy = _post(
            client,
            "/access/source-policy",
            {"source_id": engineering_id, "audience_id": "finance"},
        )
        assert "Source policy revision" in changed_policy.text
        assert client.get(f"/documents/{engineering_document}?version=1").status_code == 409
        assert client.get(f"/?stage=review&candidate={engineering_candidate}").status_code == 404
        _switch(client, "dual_compiler")
        assert client.get(f"/responses/{response_id}").status_code == 409
        assert f'href="/documents/{engineering_document}"' not in client.get("/?stage=read").text
