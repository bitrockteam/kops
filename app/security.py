from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings
from app.contracts import PolicyDecision, Principal
from app.db import Database


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class DestinationError(ValueError):
    pass


class MockIdentityProvider:
    """Resolves only signed server-issued subject identifiers against trusted fixtures."""

    def __init__(self, database: Database, secret: str) -> None:
        self.database = database
        self.serializer = URLSafeTimedSerializer(secret, salt="kops-demo-session-v1")

    def issue_session(self, subject_id: str) -> str:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT subject_id FROM kops.personas WHERE subject_id = %s AND active",
                (subject_id,),
            ).fetchone()
        if not row:
            raise AuthenticationError("unknown synthetic persona")
        return self.serializer.dumps({"subject_id": subject_id, "recipient": "kops-local-api"})

    def resolve_session(self, signed_session: str | None) -> Principal:
        if not signed_session:
            subject_id = "operator_admin"
        else:
            try:
                payload = self.serializer.loads(signed_session, max_age=8 * 60 * 60)
            except SignatureExpired as error:
                raise AuthenticationError("demo session expired") from error
            except BadSignature as error:
                raise AuthenticationError("invalid demo session") from error
            if payload.get("recipient") != "kops-local-api":
                raise AuthenticationError("wrong demo session recipient")
            subject_id = payload.get("subject_id")
        with self.database.connection() as connection:
            persona = connection.execute(
                """
                SELECT subject_id, display_name, action_grants
                FROM kops.personas WHERE subject_id = %s AND active
                """,
                (subject_id,),
            ).fetchone()
            if not persona:
                raise AuthenticationError("unknown or inactive demo persona")
            groups = connection.execute(
                "SELECT group_id FROM kops.memberships WHERE subject_id = %s AND active",
                (subject_id,),
            ).fetchall()
        return Principal(
            subject_id=persona["subject_id"],
            display_name=persona["display_name"],
            action_grants=frozenset(persona["action_grants"]),
            groups=frozenset(row["group_id"] for row in groups),
        )


class PostgresPolicyService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def authorize(self, principal: Principal, action: str, audience_id: str) -> PolicyDecision:
        with self.database.connection() as connection:
            audience = connection.execute(
                """
                SELECT required_groups, policy_revision
                FROM kops.audiences WHERE audience_id = %s AND active
                """,
                (audience_id,),
            ).fetchone()
        if not audience:
            return PolicyDecision(False, "audience_not_available", 0)
        if action not in principal.action_grants and "*" not in principal.action_grants:
            return PolicyDecision(False, "action_not_granted", audience["policy_revision"])
        required = set(audience["required_groups"])
        if not required.issubset(principal.groups):
            return PolicyDecision(False, "audience_membership_required", audience["policy_revision"])
        return PolicyDecision(True, "allowed", audience["policy_revision"])

    def require(self, principal: Principal, action: str, audience_id: str) -> PolicyDecision:
        decision = self.authorize(principal, action, audience_id)
        if not decision.allowed:
            raise AuthorizationError(decision.reason_code)
        return decision

    def source_compatible(self, source_audience_id: str, target_audience_id: str) -> bool:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT audience_id, required_groups
                FROM kops.audiences WHERE audience_id IN (%s, %s) AND active
                """,
                (source_audience_id, target_audience_id),
            ).fetchall()
        policies = {row["audience_id"]: set(row["required_groups"]) for row in rows}
        if source_audience_id not in policies or target_audience_id not in policies:
            return False
        return policies[source_audience_id].issubset(policies[target_audience_id])


def _is_allowed_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return False
    return ip.is_loopback or ip.is_private


def validate_model_endpoint(endpoint: str, allowed_hostnames: Iterable[str] = ()) -> str:
    parsed = urlparse(endpoint.strip())
    if parsed.scheme not in {"http", "https"}:
        raise DestinationError("model endpoint must use http or https")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise DestinationError("model endpoint contains unsupported authority data")
    hostname = parsed.hostname.lower()
    if hostname in {"169.254.169.254", "metadata.google.internal"}:
        raise DestinationError("cloud metadata destinations are denied")
    try:
        ipaddress.ip_address(hostname)
        hostname_is_ip = True
    except ValueError:
        hostname_is_ip = False
    configured_hostnames = {item.lower() for item in allowed_hostnames}
    if not hostname_is_ip and hostname not in {"localhost"} | configured_hostnames:
        raise DestinationError("model endpoint hostname is not in the operator allowlist")
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        }
    except socket.gaierror as error:
        raise DestinationError("model endpoint hostname could not be resolved") from error
    if not addresses or not all(_is_allowed_ip(address) for address in addresses):
        raise DestinationError("model endpoint must resolve only to loopback or private addresses")
    return endpoint.rstrip("/")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class RequestContext:
    principal: Principal
    correlation_id: str
    run_id: str | None = None
    job_id: str | None = None
