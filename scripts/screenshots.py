#!/usr/bin/env python3
"""Capture actual local GUI state with a temporary headless Firefox session."""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


BASE_URL = os.environ.get("KOPS_SCREENSHOT_URL", "http://127.0.0.1:8080").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("KOPS_SCREENSHOT_DIR", "screenshots"))


class FirefoxSession:
    def __init__(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.endpoint = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen(
            ["geckodriver", "--host", "127.0.0.1", "--port", str(port), "--log", "error"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.session_id: str | None = None

    def request(self, method: str, path: str, payload: dict | None = None) -> object:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.endpoint + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Firefox WebDriver returned {error.code}: {error.read().decode()[:500]}") from error
        return result["value"]

    def __enter__(self) -> FirefoxSession:
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError("geckodriver stopped before Firefox could start")
                try:
                    if self.request("GET", "/status"):
                        break
                except (OSError, ValueError):
                    time.sleep(0.2)
            else:
                raise RuntimeError("geckodriver did not become ready")
            session = self.request(
                "POST",
                "/session",
                {"capabilities": {"alwaysMatch": {"browserName": "firefox", "moz:firefoxOptions": {"args": ["-headless"]}}}},
            )
            self.session_id = session["sessionId"]
            self.request("POST", f"/session/{self.session_id}/window/rect", {"width": 1600, "height": 1000})
            return self
        except Exception:
            self.__exit__()
            raise

    def __exit__(self, *_: object) -> None:
        if self.session_id:
            try:
                self.request("DELETE", f"/session/{self.session_id}")
            except (OSError, RuntimeError):
                pass
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        if self.process.stderr:
            self.process.stderr.close()

    def navigate(self, path: str) -> None:
        self.request("POST", f"/session/{self.session_id}/url", {"url": BASE_URL + path})

    def execute(self, script: str) -> object:
        return self.request("POST", f"/session/{self.session_id}/execute/sync", {"script": script, "args": []})

    def capture(self, filename: str) -> None:
        encoded = self.request("GET", f"/session/{self.session_id}/screenshot")
        destination = OUTPUT_DIR / filename
        destination.write_bytes(base64.b64decode(encoded))
        print(destination)


def main() -> None:
    parsed = urlparse(BASE_URL)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Screenshot URL must be a local HTTP address")
    with urllib.request.urlopen(BASE_URL + "/health", timeout=5) as response:
        if response.status != 200:
            raise SystemExit("Local kops is not healthy")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with FirefoxSession() as browser:
        browser.navigate("/?stage=publish")
        publication_text = browser.execute("return document.body.innerText")
        if "committed" not in publication_text.lower():
            raise SystemExit(f"A committed publication is required before screenshots: {publication_text[-1000:]!r}")
        browser.capture("01-publication.png")

        browser.navigate("/?stage=read")
        joint_page = browser.execute(
            "return [...document.querySelectorAll('main article.card')]"
            ".filter(card => card.innerText.includes('joint'))"
            ".map(card => card.querySelector('a[href^=\"/documents/\"]')?.getAttribute('href'))[0] || null"
        )
        if not joint_page:
            raise SystemExit("A joint page is required before revocation screenshots")
        browser.capture("02-authorized-catalog.png")

        browser.navigate("/?stage=access")
        browser.execute(
            "const form = document.querySelector('form[action=\"/access/membership\"]');"
            "form.querySelector('select[name=\"subject_id\"]').value = 'dual_compiler';"
            "form.querySelector('select[name=\"group_id\"]').value = 'finance';"
            "form.querySelector('input[name=\"active\"]').checked = false;"
        )
        browser.capture("03-access-changes.png")
        browser.navigate("/?stage=audit")
        browser.capture("04-protected-audit.png")

        browser.execute(
            "const form = document.querySelector('.persona-form');"
            "form.querySelector('select').value = 'dual_compiler'; form.submit();"
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if browser.execute("return document.querySelector('#persona')?.value") == "dual_compiler":
                break
            time.sleep(0.2)
        else:
            raise SystemExit("Firefox did not switch to the revoked persona")
        browser.navigate("/?stage=read")
        visible = browser.execute("return document.querySelector('main').innerText")
        if "joint" in visible.lower():
            raise SystemExit("Revoked persona still sees a joint audience page")
        browser.capture("05-revoked-catalog.png")

        browser.navigate(joint_page)
        denied = browser.execute("return document.body.innerText")
        if "page not available" not in denied.lower():
            raise SystemExit(f"Revoked persona did not receive the expected page denial: {denied[:300]!r}")
        browser.capture("06-revoked-page-denial.png")


if __name__ == "__main__":
    main()
