"""Unit tests for the collector package: pure logic, no network, no Docker.

Run with ``python -m pytest collector/tests/test_collector.py`` from the repository root so that
both ``app`` and ``collector`` are importable. This file lives outside ``tests/`` (whose
``testpaths`` default pytest collects with no explicit path, exactly how the ``docker compose
--profile test`` run and the ``Makefile`` ``test`` target invoke it) because the ``collector``
package is a separate build context (``collector/Dockerfile``) never installed into the
``app``-only image those containers run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from collector import prefilter, sources
from collector.rawstore import RawStore, content_hash
from collector.registry import check_registration, parse_registry, scope_fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_cloud_key_rule_matches_aws_style_key():
    hits = prefilter.find_hits("access key AKIAIOSFODNN7EXAMPLE in the shared drive")
    assert {h["rule"] for h in hits} == {"cloud-key"}


def test_card_luhn_matches_valid_card_number():
    hits = prefilter.find_hits("card 4111 1111 1111 1111 exp 09/28")
    assert {h["rule"] for h in hits} == {"card-luhn"}


def test_card_luhn_ignores_digit_run_embedded_in_hex_token():
    # A 16-hex-char request id can contain a 13-19 digit run that happens to be Luhn-valid;
    # it must not fire unless the digits sit on their own, not embedded in a longer token.
    hits = prefilter.find_hits('{"request_id": "ec88337069419126"}')
    assert hits == []


def test_card_luhn_rejects_invalid_checksum():
    hits = prefilter.find_hits("card 4111 1111 1111 1112 exp 09/28")
    assert hits == []


def test_private_key_rule_matches_pem_header():
    hits = prefilter.find_hits("-----BEGIN RSA PRIVATE KEY-----\nMIIC...")
    assert {h["rule"] for h in hits} == {"private-key"}


def test_password_line_matches_table_header_and_inline_label():
    header_hits = prefilter.find_hits("| Host | User | Password |\n| a | b | c |")
    assert {h["rule"] for h in header_hits} == {"password-line"}
    inline_hits = prefilter.find_hits("Temporary password: Qa!2026-ferry-Xk9pL, change it")
    assert {h["rule"] for h in inline_hits} == {"password-line"}


def test_iban_rule_matches_plausible_iban():
    hits = prefilter.find_hits("wire to DE89370400440532013000 for settlement")
    assert {h["rule"] for h in hits} == {"iban"}


def test_unknown_space_rule_flags_space_outside_allowlist():
    hits = prefilter.find_hits("ordinary text", space="Shadow IT")
    assert {h["rule"] for h in hits} == {"unknown-space"}
    assert prefilter.find_hits("ordinary text", space="Finance") == []


def test_people_space_is_restricted_others_are_not():
    assert prefilter.is_restricted("People") is True
    assert prefilter.is_restricted("Operations") is False
    assert prefilter.is_restricted(None) is False


def test_collect_wiki_reads_roster_space_from_frontmatter():
    items = sources.collect_wiki({"path": str(REPO_ROOT / "fixtures/meridian/wiki/*.md")})
    roster = next(item for item in items if item["item_id"] == "wiki/hr-roster-ops-oncall-q4.md")
    assert roster["space"] == "People"
    assert prefilter.is_restricted(roster["space"]) is True


def test_registry_file_parses_with_four_collectors_and_prefilter_block():
    text = (REPO_ROOT / "collectors.yaml").read_text(encoding="utf-8")
    registry = parse_registry(text)
    names = [entry["name"] for entry in registry["collectors"]]
    assert names == ["wiki", "tickets", "repo", "logs"]
    assert registry["prefilter"]["rules"] == [
        "cloud-key", "card-luhn", "iban", "private-key", "password-line", "unknown-space",
    ]
    repo_entry = next(entry for entry in registry["collectors"] if entry["name"] == "repo")
    assert repo_entry["scope"]["batch"] == 20


def test_check_registration_flags_unregistered_and_drifted_scope():
    scope = {"path": "/srv/x"}
    fingerprint = scope_fingerprint(scope)
    registrations = {"wiki": {"scope_fingerprint": fingerprint, "owner": "franco", "registered_at": "now"}}
    assert check_registration("wiki", scope, registrations)[0] == "ok"
    assert check_registration("ghost", scope, registrations)[0] == "unregistered"
    assert check_registration("wiki", {"path": "/srv/y"}, registrations)[0] == "scope_changed"


def test_collect_repo_batches_commits_without_dropping_any():
    commits = [{"sha": str(i)} for i in range(45)]
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        commits_path = Path(tmp) / "commits.json"
        commits_path.write_text(json.dumps(commits), encoding="utf-8")
        items = sources.collect_repo({"path": str(commits_path), "batch": 20})
    assert len(items) == 3
    assert sum(len(json.loads(item["content"])) for item in items) == 45


def test_raw_store_is_content_addressed_and_immutable(tmp_path):
    store = RawStore(tmp_path)
    sha1 = store.write_raw("wiki", "wiki/a.md", "hello", prefilter_version=1)
    sha2 = store.write_raw("wiki", "wiki/a.md", "hello", prefilter_version=1)
    assert sha1 == sha2 == content_hash("hello")
    files = list((tmp_path / "raw" / "wiki").glob("*.json"))
    assert len(files) == 1
    sha3 = store.write_raw("wiki", "wiki/a.md", "hello, revised", prefilter_version=1)
    assert sha3 != sha1
    assert len(list((tmp_path / "raw" / "wiki").glob("*.json"))) == 2


def test_raw_store_persists_the_restricted_flag(tmp_path):
    store = RawStore(tmp_path)
    sha = store.write_raw("wiki", "wiki/hr-roster-ops-oncall-q4.md", "roster body", prefilter_version=1, restricted=True)
    record = json.loads((tmp_path / "raw" / "wiki" / f"{sha}.json").read_text(encoding="utf-8"))
    assert record["restricted"] is True


def test_quarantined_items_never_appear_under_raw(tmp_path):
    store = RawStore(tmp_path)
    hits = prefilter.find_hits("card 4111 1111 1111 1111")
    store.write_quarantine("wiki", "wiki/secret.md", "card 4111 1111 1111 1111", hits, prefilter_version=1)
    assert list((tmp_path / "raw").rglob("*.json")) == []
    assert len(list((tmp_path / "quarantine").rglob("*.json"))) == 1


def test_handle_run_end_to_end_notifies_without_keyerror(tmp_path, monkeypatch):
    # Regression test: a run that quarantines at least one item used to crash while building
    # the ntfy message (it indexed the per-collector result dict instead of the item dict).
    import dataclasses

    from collector import server

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "clean.md").write_text(
        "---\ntitle: Clean\nspace: Operations\n---\n\nNothing sensitive here.\n", encoding="utf-8"
    )
    (wiki_dir / "secret.md").write_text(
        "---\ntitle: Secret\nspace: Operations\n---\n\ncard 4111 1111 1111 1111\n", encoding="utf-8"
    )

    registry_path = tmp_path / "collectors.yaml"
    registry_path.write_text(
        "collectors:\n"
        "  - {name: wiki, kind: file, owner: franco, scope: {path: " + wiki_dir.as_posix() + "/*.md}}\n"
        "prefilter: {version: 1, rules: [card-luhn], on_hit: quarantine-and-notify}\n",
        encoding="utf-8",
    )
    raw_root = tmp_path / "raw_root"

    monkeypatch.setattr(
        server, "settings", dataclasses.replace(server.settings, registry_path=registry_path, raw_root=raw_root)
    )
    monkeypatch.setattr(server, "store", RawStore(raw_root))
    monkeypatch.setattr(server, "registrations_path", raw_root / "registrations.json")
    monkeypatch.setattr(server, "_report", lambda *args, **kwargs: None)
    notified = []
    monkeypatch.setattr(server, "ring", lambda *args, **kwargs: notified.append(args) or True)

    status, manifest = server.handle_run({"collector": "all"})

    assert status == 200
    result = manifest["results"][0]
    assert result["seen"] == 2
    assert len(result["admitted"]) == 1
    assert len(result["quarantined"]) == 1
    assert notified and "wiki/secret.md" in notified[0][2]
