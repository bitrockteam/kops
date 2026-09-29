"""Minimal stdlib client that rings ntfy when the pre-filter quarantines an item."""

from __future__ import annotations

import urllib.error
import urllib.request


def ring(notify_url: str, topic: str, message: str, *, title: str | None = None) -> bool:
    request = urllib.request.Request(
        f"{notify_url}/{topic}",
        data=message.encode("utf-8"),
        method="POST",
    )
    if title:
        request.add_header("X-Title", title)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
