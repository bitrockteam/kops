"""Registry file parsing and collector registration, standard library only.

``collectors.yaml`` is restricted to flow-style mappings and lists so that this module can
parse it without a YAML dependency: every value is either a plain scalar, a ``{k: v, ...}``
mapping or a ``[a, b, ...]`` list, all on one line.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _strip_comment(line: str) -> str:
    in_quotes = False
    for index, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "#" and not in_quotes:
            return line[:index]
    return line


def _parse_scalar(token: str) -> object:
    token = token.strip()
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        return token


def _parse_flow(text: str, index: int) -> tuple[object, int]:
    while text[index] == " ":
        index += 1
    if text[index] == "{":
        return _parse_flow_mapping(text, index)
    if text[index] == "[":
        return _parse_flow_list(text, index)
    start = index
    depth = 0
    while index < len(text) and not (depth == 0 and text[index] in ",}]"):
        if text[index] in "{[":
            depth += 1
        elif text[index] in "}]":
            depth -= 1
        index += 1
    return _parse_scalar(text[start:index]), index


def _parse_flow_mapping(text: str, index: int) -> tuple[dict, int]:
    index += 1  # opening brace
    result: dict[str, object] = {}
    while True:
        while text[index] == " ":
            index += 1
        if text[index] == "}":
            return result, index + 1
        key_start = index
        while text[index] != ":":
            index += 1
        key = text[key_start:index].strip()
        index += 1
        value, index = _parse_flow(text, index)
        result[key] = value
        while index < len(text) and text[index] == " ":
            index += 1
        if text[index] == ",":
            index += 1
        elif text[index] == "}":
            return result, index + 1


def _parse_flow_list(text: str, index: int) -> tuple[list, int]:
    index += 1  # opening bracket
    result: list[object] = []
    while True:
        while text[index] == " ":
            index += 1
        if text[index] == "]":
            return result, index + 1
        value, index = _parse_flow(text, index)
        result.append(value)
        while index < len(text) and text[index] == " ":
            index += 1
        if text[index] == ",":
            index += 1
        elif text[index] == "]":
            return result, index + 1


def parse_registry(text: str) -> dict:
    result: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest:
                value, _ = _parse_flow(rest, 0)
                result[key] = value
                current_key = None
            else:
                result[key] = []
                current_key = key
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key is not None:
            value, _ = _parse_flow(stripped[2:].strip(), 0)
            result.setdefault(current_key, [])
            result[current_key].append(value)  # type: ignore[union-attr]
    return result


def scope_fingerprint(scope: dict) -> str:
    return hashlib.sha256(canonical_json(scope).encode("utf-8")).hexdigest()


def load_registrations(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_registrations(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(data) + "\n", encoding="utf-8")


def check_registration(name: str, scope: dict, registrations: dict) -> tuple[str, str]:
    """Two hard authorization rules: not in the registry, or scope drifted since registration."""
    entry = registrations.get(name)
    if entry is None:
        return "unregistered", f"collector '{name}' has no accepted registration"
    if entry["scope_fingerprint"] != scope_fingerprint(scope):
        return "scope_changed", f"collector '{name}' scope changed since {entry['owner']} registered it on {entry['registered_at']}"
    return "ok", "registered"
