from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Principal:
    subject_id: str
    display_name: str
    action_grants: frozenset[str]
    groups: frozenset[str]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    policy_revision: int


class IdentityProvider(Protocol):
    def resolve_session(self, signed_session: str | None) -> Principal: ...


class PolicyService(Protocol):
    def authorize(self, principal: Principal, action: str, audience_id: str) -> PolicyDecision: ...


class ContentStore(Protocol):
    def put_immutable(self, namespace: str, object_id: str, revision: str, body: str) -> tuple[str, str]: ...
    def read(self, object_key: str) -> str: ...


class ModelClient(Protocol):
    def test_connection(self, config: dict[str, Any]) -> dict[str, Any]: ...
    def compile(self, config: dict[str, Any], prompt: str) -> dict[str, Any]: ...
    def answer(self, config: dict[str, Any], prompt: str) -> dict[str, Any]: ...


class JobService(Protocol):
    def request_compile(self, principal: Principal, request: dict[str, Any]) -> str: ...
    def cancel(self, principal: Principal, job_id: str) -> None: ...


class PublicationService(Protocol):
    def publish_document(self, operation_ref: str) -> dict[str, Any]: ...
    def apply_document_edit(self, operation_ref: str) -> dict[str, Any]: ...
    def block_document(self, operation_ref: str) -> dict[str, Any]: ...


class AuditSink(Protocol):
    def append(self, event: dict[str, Any]) -> str: ...
