from __future__ import annotations

import socket

import pytest

from app.content import LocalContentStore
from app.provenance import MixedSourceVersions, inherit_dependency
from app.rendering import render_markdown
from app.security import DestinationError, validate_model_endpoint


def test_content_store_is_immutable_and_rejects_traversal(tmp_path):
    store = LocalContentStore(tmp_path)
    key, digest = store.put_immutable("sources", "source-1", "1", "synthetic body")
    assert store.read(key) == "synthetic body"
    assert len(digest) == 64
    assert store.put_immutable("sources", "source-1", "1", "synthetic body") == (key, digest)
    with pytest.raises(ValueError, match="identifier"):
        store.put_immutable("sources", "../escape", "1", "bad")
    with pytest.raises(ValueError, match="object key"):
        store.read("../outside")


@pytest.mark.parametrize(
    "endpoint",
    [
        "file:///tmp/model",
        "http://user:password@127.0.0.1:11434",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal",
        "ftp://127.0.0.1/model",
    ],
)
def test_model_destination_rejects_unsafe_authorities(endpoint):
    with pytest.raises(DestinationError):
        validate_model_endpoint(endpoint)


def test_model_destination_accepts_loopback():
    assert validate_model_endpoint("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"


def test_model_destination_rejects_public_resolution(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    with pytest.raises(DestinationError, match="loopback or private"):
        validate_model_endpoint("https://model.example.test", {"model.example.test"})


def test_hostile_markdown_does_not_render_active_content_or_remote_images():
    rendered = render_markdown(
        "# Safe\n<script>alert(1)</script>\n<img src='https://attacker.invalid/pixel'>\n"
        "[javascript](javascript:alert(1)) [normal](https://example.invalid/page)"
    )
    assert "<script" not in rendered
    assert "<img" not in rendered
    assert 'href="javascript:' not in rendered
    assert "https://example.invalid/page" in rendered


def test_answer_promotion_rejects_mixed_source_versions():
    inherited = {}
    inherit_dependency(inherited, {"source_id": "source-1", "source_revision": 1, "source_policy_revision": 2})
    with pytest.raises(MixedSourceVersions, match="multiple versions"):
        inherit_dependency(inherited, {"source_id": "source-1", "source_revision": 2, "source_policy_revision": 2})
