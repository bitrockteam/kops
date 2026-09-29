#!/usr/bin/env python3
"""Synthetic world for the kops demo: Meridian Ferries.

Deterministic, standard library only, no model. One run produces the org data
the demo needs to tag, route and render, plus a raw corpus in quantity:

    python scripts/generate_meridian.py --out fixtures/meridian

Everything here is invented: company, people, systems, suppliers, phone
numbers, credentials. The planted secrets are the canonical fake values
(Amazon's documented example key, the 4111 test card) so a pre-filter has
something to catch without anything real being at risk.

Rule kept from the decision log: collectors and generators never call a model.
"""

import argparse
import csv
import hashlib
import json
import random
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20260929
COMPANY = {
    "name": "Meridian Ferries",
    "legal": "Meridian Ferries S.p.A. (fictional)",
    "hq": "Genoa, Italy (fictional)",
    "employees": 900,
    "routes": ["Genoa-Olbia", "Livorno-Bastia", "Naples-Palermo", "Civitavecchia-Cagliari"],
    "systems": {
        "nbs": "New Booking System: web and API for bookings, on Kubernetes since May 2026",
        "paygate": "PayGate: the adapter towards the payment provider CardinalPay",
        "sirius": "Sirius: the legacy booking system, read-only through sirius-bridge until March 2027",
        "visionx": "Vision X: fleet telemetry and port operations dashboard",
        "helphub": "HelpHub: the helpdesk ticketing tool used by Customer Care",
    },
}

# ---------------------------------------------------------------------------
# Org: units, roles, domains, tags, people
# ---------------------------------------------------------------------------

ROLES = {
    "helpdesk-l1": {
        "description": "Answers the phone and the chat for customers, first level",
        "domains": ["customer-support"],
        "audience_brief": {
            "who": "An operator with a customer on the line. Average handling time is four minutes.",
            "needs": "What to say to the customer, at most three checks in the tools they have (HelpHub, the NBS back office), and the one condition under which they escalate, to which queue.",
            "must_not_get": "Architecture, commands, database or cluster names, supplier terms, names or phone numbers of engineers. Even where the operator is entitled to more, the L1 page is the script and nothing else.",
            "form": "A numbered script under 120 words. Customer-facing sentences in quotes. Error codes spelled as the customer sees them.",
            "glossary": {"PNR": "booking reference", "PayGate": "the payment step", "PAY-502": "payment provider unavailable"},
        },
    },
    "ops-desk": {
        "description": "Second and third level operations for the booking platform and Vision X",
        "domains": ["booking-platform", "fleet-operations", "customer-support"],
        "audience_brief": {
            "who": "An engineer with a ticket or an alert, at the desk or on call.",
            "needs": "Symptoms, the checks in order with the exact commands, the decision points, who to escalate to, what changed recently.",
            "must_not_get": "Supplier prices, personal data beyond the on-call name and phone, customer-facing wording.",
            "form": "Checklist first, commands as code, then the reasoning. Live state next to the runbook when available.",
            "glossary": {},
        },
    },
    "developer": {
        "description": "Builds and fixes NBS, PayGate and the bridges",
        "domains": ["booking-platform"],
        "audience_brief": {
            "who": "A developer with the code open.",
            "needs": "The code path, the ADR that decided it, the commits that touched it, the incident that motivated it, the test that covers it.",
            "must_not_get": "Customer scripts, prices, personal data.",
            "form": "Paths, identifiers and links first; prose second.",
            "glossary": {},
        },
    },
    "functional-analyst": {
        "description": "Owns the functional view of the platform and the customer processes",
        "domains": ["booking-platform", "customer-support", "fleet-operations"],
        "audience_brief": {
            "who": "Someone who has to explain to the business what happened, what it cost in bookings, and what will change.",
            "needs": "Business impact, affected flows and routes, customer-visible behavior, decisions and dates, open questions.",
            "must_not_get": "Commands, cluster names, code, prices.",
            "form": "Narrative in business terms, under 300 words, with a dated decision list.",
            "glossary": {"PAY-502": "payment provider outage", "hold": "the ten minute reservation before payment"},
        },
    },
    "fleet-ops": {
        "description": "Port and vessel operations, boarding, manifests",
        "domains": ["fleet-operations", "customer-support"],
        "audience_brief": {
            "who": "A port coordinator with a boarding in progress.",
            "needs": "Manifest state, boarding blockers, who to call, the customer-facing line.",
            "must_not_get": "Platform internals, prices, personal data of staff.",
            "form": "Short, by vessel and departure, times in local time.",
            "glossary": {"manifest": "the passenger and vehicle list Vision X sends to the port"},
        },
    },
    "finance-controller": {
        "description": "Costs, supplier terms, pricing, invoicing",
        "domains": ["finance"],
        "audience_brief": {
            "who": "A controller closing the month or checking a supplier.",
            "needs": "Amounts, rates, volumes, contract terms, totals first.",
            "must_not_get": "Operational detail beyond what changes an amount; personal data.",
            "form": "Tables with euro amounts and dates; a one-line reading under each table.",
            "glossary": {},
        },
    },
    "hr-partner": {
        "description": "People data, onboarding, on-call allowances, working time",
        "domains": ["people"],
        "audience_brief": {
            "who": "The HR partner for Platform and Customer Care.",
            "needs": "Roster, contract type, allowances, onboarding steps, working-time notes.",
            "must_not_get": "System internals, supplier terms.",
            "form": "Per person, minimal, with the retention rule stated on every page.",
            "glossary": {},
        },
    },
    "security-monitor": {
        "description": "Receives quarantine notifications and can read lineage for any item",
        "domains": ["security"],
        "lineage": True,
        "audience_brief": {
            "who": "The person who gets the notification when a collector quarantines something, and who reconstructs a breach.",
            "needs": "Events with timestamps, who could see what and when, where an item could have gone.",
            "must_not_get": "Nothing is hidden from lineage; content itself is not shown unless the role also has the domain.",
            "form": "Event lists and lineage tables. No prose reading.",
            "glossary": {},
        },
    },
}

DOMAINS = {
    "booking-platform": "NBS, PayGate, Sirius bridge: how the booking platform is built and run",
    "customer-support": "Tickets, scripts, escalation: what Customer Care needs to answer customers",
    "fleet-operations": "Vision X, ports, manifests, boarding",
    "finance": "Pricing, supplier rates, invoicing",
    "people": "Rosters, onboarding, on-call, working time: personal data",
    "security": "Policies, credentials, access, quarantines",
}

TAGS = {
    "service:nbs": "New Booking System", "service:paygate": "PayGate adapter and CardinalPay",
    "service:sirius": "Legacy Sirius and sirius-bridge", "service:visionx": "Vision X",
    "service:helphub": "HelpHub ticketing",
    "kind:runbook": "Operational procedure", "kind:incident": "Incident or post-mortem",
    "kind:ticket": "Helpdesk ticket", "kind:script": "Customer-facing script",
    "kind:adr": "Architecture decision record", "kind:commit": "Commit message",
    "kind:log": "Application log", "kind:policy": "Policy", "kind:contract": "Contract or supplier terms",
    "kind:roster": "Staff roster", "kind:guide": "User guide",
    "severity:p1": "Service down or boarding blocked", "severity:p2": "Degraded", "severity:p3": "Single customer",
    "topic:checkout": "Payment and confirmation step", "topic:refund": "Refunds", "topic:check-in": "Check-in and QR",
    "topic:deploy": "Deploy and rollback", "topic:database": "PostgreSQL and pooling", "topic:kubernetes": "Cluster and pods",
    "topic:telemetry": "Vessel telemetry", "topic:port": "Port operations", "topic:pricing": "Fares and pricing rules",
    "topic:supplier": "Supplier relationship", "topic:invoice": "Invoicing", "topic:onboarding": "Onboarding",
    "topic:on-call": "On-call rota", "topic:credentials": "Credentials and secrets", "topic:access": "Access rights",
    "personal:yes": "Contains personal data",
}

DOMAIN_TAGS = {
    "booking-platform": ["service:nbs", "service:paygate", "service:sirius", "kind:runbook", "kind:incident",
                         "kind:adr", "kind:commit", "kind:log", "topic:checkout", "topic:deploy",
                         "topic:database", "topic:kubernetes"],
    "customer-support": ["service:helphub", "kind:ticket", "kind:script", "topic:refund", "topic:check-in",
                         "severity:p1", "severity:p2", "severity:p3"],
    "fleet-operations": ["service:visionx", "topic:telemetry", "topic:port", "kind:guide", "kind:runbook", "kind:incident"],
    "finance": ["topic:pricing", "topic:supplier", "topic:invoice", "kind:contract"],
    "people": ["kind:roster", "topic:onboarding", "topic:on-call", "personal:yes"],
    "security": ["kind:policy", "topic:credentials", "topic:access"],
}

# Directory groups are what an org chart export carries; role_mappings turns them into roles.
ROLE_MAPPINGS = {
    "CC-L1": "helpdesk-l1", "CC-LEAD": "functional-analyst", "PLAT-OPS": "ops-desk", "PLAT-DEV": "developer",
    "PROD": "functional-analyst", "FLEET-PORT": "fleet-ops", "FIN-CTRL": "finance-controller",
    "HR-BP": "hr-partner", "SEC-MON": "security-monitor",
}

PEOPLE = [
    # principal, name, unit, title, manager, groups, rendering profile
    ("giulia.ferrante", "Giulia Ferrante", "Customer Care", "Helpdesk operator L1, day shift", "marta.esposito", ["CC-L1"],
     {"length": "short", "leads_with": "what to say to the customer", "format": "numbered steps",
      "tone": "plain, reassuring", "avoid": ["acronyms", "system names"],
      "own_words": {"the booking code": "PNR", "the payment thing": "PayGate", "the old system": "Sirius"},
      "notes": "Reads on a second monitor while talking. Wants the escalation condition in bold."}),
    ("marco.belli", "Marco Belli", "Customer Care", "Helpdesk operator L1, night shift", "marta.esposito", ["CC-L1"],
     {"length": "short", "leads_with": "whether to escalate now", "format": "numbered steps",
      "tone": "direct", "avoid": ["explanations"],
      "own_words": {"the code": "PNR", "the pay page": "checkout"},
      "notes": "Alone at night. Wants to know when he is allowed to wake someone up."}),
    ("marta.esposito", "Marta Esposito", "Customer Care", "Customer Care lead", "paolo.ricci", ["CC-L1", "CC-LEAD"],
     {"length": "medium", "leads_with": "impact on the queue", "format": "short paragraphs then a list",
      "tone": "managerial", "avoid": ["commands"],
      "own_words": {"the floor": "the L1 team", "AHT": "average handling time"},
      "notes": "Wants numbers: tickets affected, customers waiting."}),
    ("sara.conti", "Sara Conti", "Platform Engineering", "Operations engineer L2", "roberto.mancuso", ["PLAT-OPS"],
     {"length": "short", "leads_with": "the first command to run", "format": "checklist with code blocks",
      "tone": "terse", "avoid": ["background", "business framing"],
      "own_words": {"the adapter": "paygate-adapter", "the pool": "pgbouncer"},
      "notes": "Copies commands from the page. Raw outputs, not summaries of outputs."}),
    ("davide.rinaldi", "Davide Rinaldi", "Platform Engineering", "Site reliability engineer L3", "roberto.mancuso", ["PLAT-OPS", "PLAT-DEV"],
     {"length": "long", "leads_with": "the hypothesis", "format": "timeline then evidence",
      "tone": "analytical", "avoid": ["step lists without a why"],
      "own_words": {"the storm": "the 12 September PAY-502 burst"},
      "notes": "Wants what changed in the last 48 hours before anything else."}),
    ("elena.moretti", "Elena Moretti", "Platform Engineering", "Backend developer, NBS", "roberto.mancuso", ["PLAT-DEV"],
     {"length": "medium", "leads_with": "the file and function", "format": "paths, then prose",
      "tone": "precise", "avoid": ["customer wording"],
      "own_words": {"the retry thing": "ADR-007 retry with backoff"},
      "notes": "Asks for the commit that introduced a behavior, then reads the ADR."}),
    ("nadia.orlando", "Nadia Orlando", "Platform Engineering", "Backend developer and QA, NBS", "roberto.mancuso", ["PLAT-DEV"],
     {"length": "medium", "leads_with": "the failing test", "format": "bullets",
      "tone": "practical", "avoid": [],
      "own_words": {"the QA box": "the QA environment"},
      "notes": "Maintains the QA environment page. Pastes things she should not paste."}),
    ("simone.pace", "Simone Pace", "Platform Engineering", "Frontend developer, NBS", "roberto.mancuso", ["PLAT-DEV"],
     {"length": "short", "leads_with": "what the user sees", "format": "bullets with screenshots described",
      "tone": "visual", "avoid": ["database detail"],
      "own_words": {"the spinner": "the checkout pending state"},
      "notes": "Cares about error messages as rendered."}),
    ("tommaso.greco", "Tommaso Greco", "Product", "Functional analyst", "paolo.ricci", ["PROD"],
     {"length": "long", "leads_with": "the business impact", "format": "narrative with a dated decision list",
      "tone": "explanatory", "avoid": ["commands", "cluster names"],
      "own_words": {"the funnel": "search to confirm flow", "drop": "abandoned holds"},
      "notes": "Writes for the steering committee. Wants numbers he can quote."}),
    ("paolo.ricci", "Paolo Ricci", "Product", "Product owner, NBS", "roberto.mancuso", ["PROD"],
     {"length": "short", "leads_with": "the decision", "format": "bullets with dates",
      "tone": "decisive", "avoid": ["long background"],
      "own_words": {"the bridge": "sirius-bridge"},
      "notes": "Three bullets or he stops reading."}),
    ("federica.bruni", "Federica Bruni", "Fleet Operations", "Port operations coordinator, Genoa", "roberto.mancuso", ["FLEET-PORT"],
     {"length": "short", "leads_with": "the departure affected", "format": "by vessel and time",
      "tone": "operational", "avoid": ["platform internals"],
      "own_words": {"the list": "the manifest", "the gate": "the boarding gate"},
      "notes": "On a tablet in the port. Local time only."}),
    ("chiara.lombardi", "Chiara Lombardi", "Finance", "Finance controller", "roberto.mancuso", ["FIN-CTRL"],
     {"length": "medium", "leads_with": "the total", "format": "table then one line",
      "tone": "exact", "avoid": ["technical detail"],
      "own_words": {"CP": "CardinalPay", "MM": "monthly minimum"},
      "notes": "Euro amounts with two decimals. Dates in ISO."}),
    ("luca.santoro", "Luca Santoro", "People", "HR business partner", "roberto.mancuso", ["HR-BP"],
     {"length": "short", "leads_with": "the person concerned", "format": "per person",
      "tone": "careful", "avoid": ["copying personal data into answers when not asked"],
      "own_words": {"the rota": "the on-call roster"},
      "notes": "Expects the retention rule to be restated."}),
    ("anna.vitali", "Anna Vitali", "Security", "Security monitor", "roberto.mancuso", ["SEC-MON"],
     {"length": "short", "leads_with": "the event", "format": "event list, lineage table",
      "tone": "forensic", "avoid": ["prose readings"],
      "own_words": {"the lake": "the raw store"},
      "notes": "Timestamps in UTC, correlation ids visible."}),
    ("roberto.mancuso", "Roberto Mancuso", "Platform Engineering", "Head of Platform", "", ["PLAT-OPS", "PLAT-DEV", "PROD"],
     {"length": "short", "leads_with": "the status and the risk", "format": "three bullets",
      "tone": "executive", "avoid": ["detail unless asked"],
      "own_words": {},
      "notes": "Has the widest rights and needs the least. The test case for need over rights."}),
]

AGENTS = [
    ("ops-agent", "Read-only ops agent", ["PLAT-OPS"]),
]

# ---------------------------------------------------------------------------
# Wiki pages: raw, as the owners wrote them. Some are planted on purpose.
# ---------------------------------------------------------------------------

PAGES = {}

def page(name, title, owner, space, body):
    PAGES[name] = {"title": title, "owner": owner, "space": space, "body": textwrap.dedent(body).strip() + "\n"}


page("nbs-architecture.md", "New Booking System: architecture", "elena.moretti", "Platform", """
    # New Booking System: architecture

    NBS replaced Sirius for all four routes in May 2026. It runs in the `nbs` namespace of the
    production Kubernetes cluster and is deployed by Argo CD from `main`.

    ## Components
    - `nbs-web`: React single page app, served by nginx, 3 replicas.
    - `nbs-api`: Python, FastAPI, 6 replicas, horizontal autoscaling on CPU.
    - `nbs-worker`: async jobs: confirmation mail, PNR sync to Vision X manifests, refund batches.
    - `nbs-db`: PostgreSQL 16, one primary and one streaming replica, managed by Platform. `pgbouncer`
      in transaction pooling mode sits in front of it (ADR-006).
    - `paygate-adapter`: the only component that talks to CardinalPay (ADR-003). Holds the provider
      credentials from the platform vault. Implements authorize, capture, refund and the 3DS callback.
    - `sirius-bridge`: read-only lookups of legacy bookings, PNR prefix `S-`, until March 2027 (ADR-008).

    ## Booking flow
    search, quote, hold (10 minutes, BK-409 when expired), pay (authorize then capture), confirm
    (PNR issued, mail sent, manifest updated in Vision X).

    ## Error codes as the customer sees them
    - `PAY-431`: 3DS declined by the issuer. Not an outage.
    - `PAY-502`: payment provider unreachable. Outage or degradation on the CardinalPay side or in the adapter.
    - `BK-409`: hold expired before payment.
    - `BK-404`: PNR not found.
    - `CHK-001`: check-in window closed.

    ## Data
    Tables `bookings`, `passengers`, `vehicles`, `payments`, `manifests`. `passengers` holds names and
    document numbers: personal data, retention 24 months after departure.

    ## Observability
    Grafana dashboards `nbs-overview` and `nbs-payments`. Alerts route to the ops-desk on-call through
    the paging tool. Logs are shipped as JSON lines with `request_id`.
    """)

page("nbs-runbook-checkout-failures.md", "Runbook: NBS checkout failures", "sara.conti", "Operations", """
    # Runbook: NBS checkout failures

    ## Symptoms
    Customers report "payment failed" at the last step. HelpHub tickets mention `PAY-502` or `PAY-431`.
    The `nbs-payments` dashboard shows authorize error rate above 5%.

    ## Triage
    1. Adapter health: `kubectl -n nbs get pods -l app=paygate-adapter` and
       `kubectl -n nbs logs deploy/paygate-adapter --since=15m | grep upstream`.
    2. CardinalPay status page. If they declare an incident, go to step 4.
    3. If `PAY-502` stays above 5% for 10 minutes and CardinalPay is green: set the config map key
       `nbs.paygate.retry=true` (ADR-007) and restart the adapter: `kubectl -n nbs rollout restart deploy/paygate-adapter`.
    4. If CardinalPay is down: enable deferred checkout, `nbs.checkout.deferred=true` (ADR-005). Customers
       get a 24 hour hold and a payment link by mail. Tell the Customer Care lead so that L1 gets the script.
    5. `PAY-431` is never an outage: the issuer declined 3DS. The customer retries with another card. Do not escalate.

    ## Escalation
    On-call L3 if two adapter restarts do not clear the error rate within 15 minutes.

    ## Afterwards
    Open a post-mortem page, link the HelpHub tickets, reset the two flags to `false`.
    """)

page("nbs-runbook-deploy-rollback.md", "Runbook: NBS deploy and rollback", "davide.rinaldi", "Operations", """
    # Runbook: NBS deploy and rollback

    Deploys are blue/green through Argo CD (ADR-004). A deploy is a merge to `main`; Argo syncs within
    three minutes and shifts traffic when the new ReplicaSet passes the readiness probe on `/health`.

    ## Rollback
    1. `argocd app history nbs-api` and pick the previous revision.
    2. `argocd app rollback nbs-api <id>`.
    3. Watch `kubectl -n nbs rollout status deploy/nbs-api`.
    4. Post in the ops channel: revision, reason, ticket.

    ## Freeze windows
    No deploys on Fridays after 14:00 and on the day before a peak departure (Genoa-Olbia Friday
    evenings in July and August).

    ## What to check after any deploy
    Error rate on `nbs-overview`, p95 latency of `/api/quote`, the `paygate-adapter` authorize success rate.
    """)

page("nbs-runbook-db-connections.md", "Runbook: nbs-db connection exhaustion", "davide.rinaldi", "Operations", """
    # Runbook: nbs-db connection exhaustion

    ## Symptoms
    `nbs-api` returns 500 on `/api/hold`; logs of `nbs-db` show
    `FATAL: remaining connection slots are reserved for non-replication superuser connections`.

    ## Cause seen so far
    A worker deploy with the pool size raised, or a long refund batch holding transactions open.

    ## Steps
    1. `kubectl -n nbs exec deploy/pgbouncer -- psql -p 6432 pgbouncer -c "SHOW POOLS"`.
    2. If `cl_waiting` grows: `SHOW SERVERS`, find the client with the oldest `connect_time`.
    3. If it is `nbs-worker` refund batch: pause it with `nbs.worker.refunds.paused=true`, let the
       batch resume after the pool drains.
    4. Never raise `max_connections` on the primary during an incident.

    ## Escalation
    L3 if `cl_waiting` does not drop within 10 minutes.
    """)

page("paygate-integration.md", "PayGate: CardinalPay integration", "elena.moretti", "Platform", """
    # PayGate: CardinalPay integration

    `paygate-adapter` wraps the CardinalPay REST API. Operations: `authorize`, `capture`, `refund`,
    `3ds-callback`. Every call carries an idempotency key derived from the booking id and the attempt number.

    - Authorize is called at "pay"; capture is called at "confirm". A hold that expires (BK-409) voids
      the authorization.
    - CardinalPay returns HTTP 502 when their gateway is saturated. Since ADR-007 the adapter retries
      three times with exponential backoff (200 ms, 800 ms, 3200 ms) when `nbs.paygate.retry` is on.
    - 3DS challenges come back through the callback; a declined challenge is `PAY-431`.
    - Credentials: sandbox and production API keys live in the platform vault under `paygate/`. They are
      never in the repository, the config maps or this page.
    - Webhooks for refunds land on `/webhooks/cardinalpay` and are verified by signature.

    Code: `services/paygate_adapter/client.py`, `services/paygate_adapter/retry.py`,
    tests in `tests/paygate/test_retry.py`.
    """)

page("sirius-retirement-plan.md", "Sirius retirement plan", "paolo.ricci", "Product", """
    # Sirius retirement plan

    Sirius stopped taking new bookings on 2026-05-04. Bookings made before that date keep their `S-` PNR
    and stay readable through `sirius-bridge` (ADR-008).

    - 2026-05-04: NBS live on all routes. Sirius read-only.
    - 2026-11-30: last `S-` departure.
    - 2027-03-31: `sirius-bridge` switched off; remaining `S-` records archived.

    ## What Customer Care needs to know
    A customer with a PNR starting with `S-` is looked up in the NBS back office with the "legacy" toggle.
    Changes to an `S-` booking are not possible; the operator rebooks in NBS and refunds Sirius through
    the refund script.
    """)

page("visionx-port-ops-guide.md", "Vision X: port operations guide", "federica.bruni", "Fleet Operations", """
    # Vision X: port operations guide

    Vision X receives the manifest of every departure from NBS (`nbs-worker`, PNR sync) and shows it to
    the gate with vehicle lanes and boarding status.

    - A manifest is final 45 minutes before departure. Later bookings appear as "late" and need a gate override.
    - A missing vehicle on the manifest usually means the PNR sync failed: check the departure in the
      Vision X "sync" tab; a red clock means NBS did not send the update. Call the ops desk, do not retype the vehicle.
    - Boarding delays over 20 minutes are announced by the gate and reported in HelpHub as a P3 so that
      Customer Care can answer the phone with the same information.
    """)

page("visionx-telemetry-alerts.md", "Vision X: telemetry alerts", "federica.bruni", "Fleet Operations", """
    # Vision X: telemetry alerts

    Vessels send position, speed and engine status every 30 seconds. Vision X raises:

    - `TEL-STALE`: no telemetry for 5 minutes. Usually the satellite link; the vessel calls the port on VHF.
    - `TEL-ETA`: ETA drifts more than 30 minutes. Port operations re-plan the berth and the gate.
    - `TEL-ENG`: engine status warning. Fleet management only; not for Customer Care.

    Dashboard `visionx-fleet`, alert route: fleet-ops pager, copy to the ops desk for `TEL-STALE`.
    """)

page("helpdesk-l1-refund-script.md", "L1 script: refund request", "marta.esposito", "Customer Care", """
    # L1 script: refund request

    1. Ask for the booking reference and the departure date. Find the booking in the NBS back office.
    2. Check the fare: "Flex" is refundable in full up to 24 hours before departure; "Smart" is refundable
       at 50% up to 72 hours before; "Basic" is not refundable.
    3. If refundable: press "Request refund", read the amount to the customer:
       "Your refund of [amount] will reach your card within 7 working days."
    4. If not refundable: "Your fare does not allow a refund. I can move the booking to another date for a
       change fee." Offer the change.
    5. Escalate to the Customer Care lead only if the customer disputes a refund already requested more than
       10 working days ago.

    Bookings with a reference starting with `S-`: see the legacy toggle in the back office; rebook in NBS
    and request the refund from the legacy tab.
    """)

page("helpdesk-l1-checkin-script.md", "L1 script: check-in and QR problems", "marta.esposito", "Customer Care", """
    # L1 script: check-in and QR problems

    1. "Can you tell me the booking reference and which port you are at?"
    2. Open the booking. If the status is "Confirmed" and the departure is within 24 hours, press
       "Resend boarding pass". "I have sent the boarding pass again by mail and SMS."
    3. If the customer sees `CHK-001`: the check-in window is closed. "Please go to the ticket desk at the
       port with your reference; they will board you from the desk."
    4. If the gate says the vehicle is not on the list: open a P2 ticket in the "Port" queue with the
       reference and the departure. "The port has been informed, please stay at the gate."
    5. Never tell the customer to re-book to fix a check-in problem.
    """)

page("helpdesk-escalation-matrix.md", "Customer Care escalation matrix", "marta.esposito", "Customer Care", """
    # Customer Care escalation matrix

    | Situation | Queue in HelpHub | Priority | Who answers |
    |---|---|---|---|
    | Payment failures for more than one customer in 15 minutes | Platform | P2 | ops desk |
    | Customers cannot pay at all, site error | Platform | P1 | ops desk, on-call at night |
    | Vehicle or passenger missing at the gate | Port | P2 | fleet-ops |
    | Boarding delayed, customers calling | Port | P3 | fleet-ops posts the announcement |
    | Refund disputed after 10 working days | Care lead | P3 | Customer Care lead |
    | Invoice requested by a company | Finance | P3 | finance |

    Operators do not call engineers directly. The on-call is paged by the P1 ticket.
    """)

page("supplier-cardinalpay-rate-card.md", "Supplier: CardinalPay profile and rate card", "chiara.lombardi", "Finance", """
    # Supplier: CardinalPay profile and rate card

    ## Profile
    CardinalPay Payments Ltd (fictional). Contract 2025-11-01 to 2027-10-31, notice 6 months.
    Support: 24/7 for P1 through the merchant portal, business hours otherwise. Technical contact for
    Meridian: the Platform team. SLA: 99.9% monthly availability of the authorize endpoint; service
    credits at 5% of the monthly fee per 0.1% below.

    ## Rates
    | Item | Rate |
    |---|---|
    | Card authorize and capture | 0.90% of amount + 0.12 EUR |
    | 3DS challenge | 0.03 EUR per challenge |
    | Refund | 0.20 EUR per refund |
    | Monthly minimum | 4,500.00 EUR |
    | Chargeback handling | 15.00 EUR per case |

    2026 volume so far: 412,380 transactions, 31.2 M EUR processed, fees 336,910.40 EUR to August.
    """)

page("hr-roster-ops-oncall-q4.md", "Ops on-call roster Q4 2026", "luca.santoro", "People", """
    # Ops on-call roster Q4 2026

    Retention: this page is kept until 2027-12-31 and then deleted. Personal data: names, mobile numbers,
    contract and allowance information. Do not copy outside the People space.

    | Week | Primary | Mobile | Secondary | Contract | Allowance band |
    |---|---|---|---|---|---|
    | 41 | Sara Conti | +39 345 000 0101 | Davide Rinaldi | permanent | B |
    | 42 | Davide Rinaldi | +39 345 000 0102 | Sara Conti | permanent | C |
    | 43 | Sara Conti | +39 345 000 0101 | Roberto Mancuso | permanent | B |
    | 44 | Davide Rinaldi | +39 345 000 0102 | Sara Conti | permanent | C |
    | 45 | Sara Conti | +39 345 000 0101 | Davide Rinaldi | permanent | B |

    Note for weeks 46 to 48: Davide Rinaldi is on reduced hours for a medical reason agreed with HR;
    secondary only, no night pages. Elena Moretti covers as secondary on request, allowance band A.
    """)

page("qa-environment-access.md", "QA environment access", "nadia.orlando", "Platform", """
    # QA environment access

    Hosts and accounts for the QA environment. Ask Nadia before changing anything.

    | Host | User | Password |
    |---|---|---|
    | qa-nbs-api.internal.example | qa-admin | Qa!2026-ferry-Xk9pL |
    | qa-nbs-db.internal.example | qa_reader | reader-2026-qa |
    | qa-visionx.internal.example | qa-ops | VisionQA#77 |

    Object storage for test fixtures: access key `AKIAIOSFODNN7EXAMPLE`, secret in the shared drive.

    Test card for the CardinalPay sandbox: 4111 1111 1111 1111, any future expiry, CVC 123.
    """)

page("incident-2026-09-12-nbs-checkout-outage.md", "Post-mortem: NBS checkout outage, 12 September 2026", "davide.rinaldi", "Operations", """
    # Post-mortem: NBS checkout outage, 12 September 2026

    ## Summary
    From 14:09 to 14:41 CEST every payment attempt on NBS failed with `PAY-502`. 1,214 holds expired
    without payment. 63 HelpHub tickets. No data lost.

    ## Timeline (CEST)
    - 14:09 CardinalPay authorize endpoint starts returning HTTP 502 for 40% of calls.
    - 14:12 `nbs-payments` alert, on-call (Sara Conti) acknowledges.
    - 14:15 Adapter restart, no effect. CardinalPay status page green.
    - 14:23 Retry flag `nbs.paygate.retry` enabled: error rate drops to 18%.
    - 14:31 Deferred checkout enabled; Customer Care lead informed; L1 script sent to the floor.
    - 14:41 CardinalPay recovers. Flags left on until 16:00, then reset.

    ## Root cause
    Capacity incident on the CardinalPay side, confirmed by their report on 15 September. The retry
    flag was off by default (ADR-007 shipped it opt-in).

    ## Actions
    - Retry on by default from release 2026.38 (commit `nbs-api: enable paygate retry by default`).
    - Customer Care keeps the deferred checkout script pinned in HelpHub.
    - Ask CardinalPay for the service credit under the SLA.
    """)

page("onboarding-new-ops-engineer.md", "Onboarding: new operations engineer", "luca.santoro", "People", """
    # Onboarding: new operations engineer

    ## Week 1, People
    Contract signed, badge, laptop, mandatory security training, working-time agreement, on-call
    allowance form (band A until the first solo on-call).

    ## Week 1, Platform
    Read-only access to the production cluster (`view` ClusterRole in `nbs`), the Grafana dashboards,
    HelpHub Platform queue. Shadow the on-call for two weeks.

    ## Week 3
    Run the checkout failures runbook in the QA environment with a colleague. First secondary on-call.

    ## Week 6
    First primary on-call, with the L3 as secondary.
    """)

page("security-policy-credentials.md", "Policy: credentials and secrets", "anna.vitali", "Security", """
    # Policy: credentials and secrets

    1. Credentials live in the platform vault. Never in wiki pages, tickets, chat, repositories or config maps.
    2. A page or ticket found to contain a credential is quarantined by the ingest pipeline, never stored,
       and the security monitor is notified with the source and the author. The credential is rotated
       within 24 hours.
    3. Personal data is ingested only from pages that state a retention rule, and every access path is traced.
    4. Agents get read-only, named, time-bounded credentials through a gateway. No agent holds an SSH key.
    """)

page("pricing-season-2027.md", "Pricing: season 2027 rules", "chiara.lombardi", "Finance", """
    # Pricing: season 2027 rules

    Confidential until published on 2026-12-01.

    | Route | Basic from | Smart from | Flex from | Vehicle from |
    |---|---|---|---|---|
    | Genoa-Olbia | 39.00 EUR | 59.00 EUR | 89.00 EUR | 79.00 EUR |
    | Livorno-Bastia | 29.00 EUR | 45.00 EUR | 69.00 EUR | 65.00 EUR |
    | Naples-Palermo | 35.00 EUR | 55.00 EUR | 85.00 EUR | 75.00 EUR |
    | Civitavecchia-Cagliari | 42.00 EUR | 62.00 EUR | 95.00 EUR | 85.00 EUR |

    Rules: peak weeks (27 to 35) +40% on Basic and Smart; Flex unchanged. Change fee 15.00 EUR.
    Refund policy unchanged from 2026 (Flex 100% to 24 h, Smart 50% to 72 h, Basic none).
    """)

page("nbs-faq-back-office.md", "NBS back office: how to", "tommaso.greco", "Product", """
    # NBS back office: how to

    - Find a booking: by PNR, by passenger surname and departure date, or by card last four digits.
    - Legacy toggle: shows `S-` bookings from Sirius, read-only.
    - Resend boarding pass: available from 24 hours before departure for confirmed bookings.
    - Request refund: computes the refundable amount from the fare rules; needs no approval under 300.00 EUR.
    - Move booking: changes date or route; the change fee is applied automatically.
    - Deferred checkout: when enabled by operations, customers with an expired hold get a payment link
      valid 24 hours; the back office shows "Awaiting payment".
    """)

# ---------------------------------------------------------------------------
# ADRs
# ---------------------------------------------------------------------------

ADRS = [
    ("ADR-001", "Replace Sirius with a new booking platform", "2025-09-10", "paolo.ricci",
     "Sirius could not support dynamic pricing or online vehicle booking. Decision: build NBS as a new platform and keep Sirius read-only for one season."),
    ("ADR-002", "FastAPI and PostgreSQL for NBS", "2025-10-02", "elena.moretti",
     "Team skills and the need for a relational model for bookings, passengers and manifests. Decision: Python with FastAPI, PostgreSQL 16, async jobs in a worker."),
    ("ADR-003", "CardinalPay as payment provider behind an adapter", "2025-10-20", "roberto.mancuso",
     "One provider, one adapter, so the provider can be replaced. Decision: paygate-adapter is the only component holding provider credentials."),
    ("ADR-004", "Blue/green deploys through Argo CD", "2025-12-01", "davide.rinaldi",
     "Rollback in under a minute during peak season. Decision: Argo CD sync from main, readiness on /health, previous revision kept."),
    ("ADR-005", "Hold-and-pay-later mode for provider outages", "2026-03-14", "paolo.ricci",
     "A provider outage should not lose the sale. Decision: a deferred checkout flag that converts an expired hold into a 24 hour payment link."),
    ("ADR-006", "pgbouncer in front of nbs-db", "2026-04-08", "davide.rinaldi",
     "Six API replicas and the worker exhausted connections in load tests. Decision: transaction pooling with pgbouncer, pool size 40."),
    ("ADR-007", "Retry with backoff on PAY-502", "2026-06-22", "elena.moretti",
     "CardinalPay returns 502 under load and usually recovers within a second. Decision: three retries with exponential backoff, behind a flag, opt-in at first."),
    ("ADR-008", "Keep sirius-bridge read-only until March 2027", "2026-05-04", "paolo.ricci",
     "Customers hold S- bookings until November 2026 and refunds run for months after. Decision: read-only bridge, switch off 2027-03-31."),
]

# ---------------------------------------------------------------------------
# Generators for volume: tickets, commits, logs
# ---------------------------------------------------------------------------

CUSTOMERS = ["A. Rossi", "B. Neri", "C. Galli", "D. Fontana", "E. Marini", "F. Colombo", "G. Serra", "H. Piras",
             "I. Melis", "J. Sanna", "K. Ferri", "L. Costa", "M. Riva", "N. Barbieri", "O. Longo", "P. Sala",
             "Q. Villa", "R. Testa", "S. Bianchi", "T. Grassi", "U. Monti", "V. Pellegrini", "W. Caruso", "X. Leone"]
ROUTES = COMPANY["routes"]
PORTS = ["Genoa", "Olbia", "Livorno", "Bastia", "Naples", "Palermo", "Civitavecchia", "Cagliari"]
FARES = ["Basic", "Smart", "Flex"]
REASONS = ["change of plans", "illness in the family", "double booking", "wrong date selected", "vehicle sold"]

TICKET_KINDS = [
    # kind, weight, severity, queue, subject, body, escalate_to
    ("refund", 22, "p3", "Care", "Refund request for {pnr}",
     "Customer {cust} asks a refund for {route} on {date}. Reason: {reason}. Fare {fare}. Handled with the refund script.", None),
    ("checkin", 16, "p3", "Care", "Boarding pass not received for {pnr}",
     "Customer {cust} at {port} has no boarding pass mail. Resent from the back office. Confirmed receipt.", None),
    ("chk001", 8, "p3", "Care", "CHK-001 at the gate for {pnr}",
     "Customer {cust} sees CHK-001 on the app at {port}. Sent to the ticket desk per script.", None),
    ("pay502", 14, "p2", "Platform", "Payment failed with PAY-502 on {route}",
     "Customer {cust} tried to pay twice for {route} on {date} and got PAY-502 both times. Hold expired (BK-409). Escalated per matrix.", "ops-desk"),
    ("pay431", 10, "p3", "Care", "PAY-431 declined for {pnr}",
     "Customer {cust} declined by the bank at 3DS. Advised to retry with another card. Second attempt succeeded.", None),
    ("bk404", 7, "p3", "Care", "Booking not found (BK-404) {pnr}",
     "Customer {cust} typed the reference with a letter O instead of zero. Found by surname and date.", None),
    ("account", 6, "p3", "Care", "Cannot log in to the customer account",
     "Customer {cust} did not receive the reset mail. Resent. Suggested checking spam.", None),
    ("visionx", 6, "p2", "Port", "Vehicle missing on the manifest, {route} {date}",
     "Gate at {port} reports vehicle of {cust} not on the list. Red clock on the sync tab. Ops desk called.", "fleet-ops"),
    ("port", 5, "p3", "Port", "Boarding delayed at {port}, customers calling",
     "Delay of 35 minutes announced by the gate for {route}. Customers informed with the same message.", None),
    ("invoice", 4, "p3", "Finance", "Invoice requested for {pnr}",
     "Company customer {cust} asks an invoice for {route} on {date}. Forwarded to Finance queue.", None),
    ("sirius", 2, "p3", "Care", "Old booking {spnr} not visible",
     "Customer {cust} has an S- reference. Legacy toggle used, booking found, rebooked in NBS.", None),
]

RICH_TICKETS = [
    dict(id="HH-2026-0301", kind="pay502", severity="p1", queue="Platform", opened="2026-09-12T14:11:00+02:00",
         closed="2026-09-12T16:05:00+02:00", opened_by="giulia.ferrante", assigned="sara.conti", status="closed",
         subject="Nobody can pay: PAY-502 on every route",
         body="Since about 14:05 every customer calling gets PAY-502 at the payment step, on all routes. "
              "Nine calls in ten minutes. Site loads, search works, payment fails. Opening as P1 per matrix."),
    dict(id="HH-2026-0302", kind="pay502", severity="p2", queue="Care", opened="2026-09-12T14:35:00+02:00",
         closed="2026-09-12T14:50:00+02:00", opened_by="marta.esposito", assigned="giulia.ferrante", status="closed",
         subject="Script for deferred checkout, pinned",
         body="Ops enabled deferred checkout. Tell customers: 'Your booking is held for 24 hours and you will "
              "receive a payment link by mail within a few minutes.' Do not ask them to retry the card now."),
    dict(id="HH-2026-0318", kind="visionx", severity="p1", queue="Port", opened="2026-09-19T17:20:00+02:00",
         closed="2026-09-19T18:10:00+02:00", opened_by="federica.bruni", assigned="sara.conti", status="closed",
         subject="Vision X manifest blank for Genoa-Olbia 19:30",
         body="The whole manifest for the 19:30 departure is empty in Vision X. 212 passengers, 84 vehicles at the gate. "
              "Sync tab shows red clock since 16:50. Need the manifest or a manual boarding list."),
    dict(id="HH-2026-0322", kind="refund", severity="p2", queue="Platform", opened="2026-09-22T09:15:00+02:00",
         closed="2026-09-22T11:40:00+02:00", opened_by="marta.esposito", assigned="davide.rinaldi", status="closed",
         subject="Refund batch stuck since Sunday night",
         body="No refund from the weekend has reached the customers. 140 requests in 'Requested' state. "
              "Customers calling. Is the batch running?"),
    dict(id="HH-2026-0331", kind="pay431", severity="p2", queue="Platform", opened="2026-09-26T21:05:00+02:00",
         closed=None, opened_by="marco.belli", assigned="davide.rinaldi", status="open",
         subject="3DS challenges timing out, several PAY-431 in an hour",
         body="Six customers between 20:00 and 21:00 report the bank app never showed the 3DS request and NBS "
              "returned PAY-431. Different banks. Not a decline pattern I have seen before."),
    dict(id="HH-2026-0077", kind="pay502", severity="p3", queue="Care", opened="2026-08-14T10:02:00+02:00",
         closed="2026-08-14T10:20:00+02:00", opened_by="giulia.ferrante", assigned="giulia.ferrante", status="closed",
         subject="Customer pasted card details in chat",
         body="Customer L. Costa wrote in the chat: 'card 4111 1111 1111 1111 exp 09/28 cvc 123, please charge it "
              "yourselves'. Told the customer we never take card details in chat and to use the site."),
    dict(id="HH-2026-0119", kind="account", severity="p3", queue="Platform", opened="2026-08-28T15:30:00+02:00",
         closed="2026-08-28T16:00:00+02:00", opened_by="nadia.orlando", assigned="sara.conti", status="closed",
         subject="QA back office login for the new tester",
         body="Please create the QA back office user for the new tester. Temporary password: Qa!2026-ferry-Xk9pL, "
              "same as the admin one on the QA page. She will change it."),
    dict(id="HH-2026-0140", kind="account", severity="p3", queue="Care", opened="2026-09-02T08:45:00+02:00",
         closed="2026-09-02T09:10:00+02:00", opened_by="marco.belli", assigned="luca.santoro", status="closed",
         subject="Working time note for night shift",
         body="Following the HR meeting: Marco Belli will not do night shifts from 6 October for a medical reason "
              "already documented with HR. Rota to be updated. Personal, do not forward."),
]

COMMIT_TEMPLATES = [
    ("nbs-api", ["add {thing} to /api/quote response", "handle BK-409 on late capture", "fix hold expiry off by one",
                 "enable paygate retry by default", "log request_id on every 5xx", "bump fastapi to {ver}",
                 "validate PNR format before lookup", "add /health details for argo readiness"]),
    ("paygate-adapter", ["retry authorize on 502 with backoff (ADR-007)", "idempotency key from booking id and attempt",
                         "verify webhook signature", "handle 3DS callback timeout", "map provider 429 to PAY-502",
                         "add metrics for authorize latency", "rotate client on credential reload"]),
    ("nbs-worker", ["refund batch: commit every 50 rows", "pause refunds behind flag", "manifest sync: resend on red clock",
                    "confirmation mail template for deferred checkout", "cap pool size at 8"]),
    ("nbs-web", ["show PAY-431 as a card problem, not an outage", "deferred checkout banner", "resend boarding pass button",
                 "legacy toggle in booking search", "checkout spinner timeout at 20 s"]),
    ("sirius-bridge", ["read-only guard on every endpoint", "S- lookup by surname and date", "archive export for 2027-03"]),
    ("infra", ["pgbouncer pool 40 (ADR-006)", "argo app for nbs-api blue/green", "alert route to ops-desk pager",
               "view ClusterRole for onboarding", "freeze window annotation"]),
]
THINGS = ["fare rules", "vehicle length", "pet option", "cabin class", "port fees"]
VERS = ["0.115.0", "0.116.1", "0.117.0"]

DEV_AUTHORS = ["elena.moretti", "nadia.orlando", "simone.pace", "davide.rinaldi", "roberto.mancuso"]


def sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def gen_tickets(rng):
    tickets = []
    start = datetime(2026, 8, 1, 8, 0)
    kinds = [k for k in TICKET_KINDS for _ in range(k[1])]
    l1 = ["giulia.ferrante", "marco.belli", "giulia.ferrante", "giulia.ferrante"]
    n = 0
    for i in range(112):
        k = rng.choice(kinds)
        n += 1
        opened = start + timedelta(minutes=rng.randint(0, 58 * 24 * 60))
        d = dict(pnr="NB" + str(rng.randint(100000, 999999)), spnr="S-" + str(rng.randint(10000, 99999)),
                 cust=rng.choice(CUSTOMERS), route=rng.choice(ROUTES), port=rng.choice(PORTS),
                 date=(opened + timedelta(days=rng.randint(1, 40))).date().isoformat(),
                 fare=rng.choice(FARES), reason=rng.choice(REASONS))
        opened_by = rng.choice(l1)
        assigned = {"ops-desk": rng.choice(["sara.conti", "davide.rinaldi"]),
                    "fleet-ops": "federica.bruni"}.get(k[6], opened_by)
        if k[3] == "Finance":
            assigned = "chiara.lombardi"
        closed = opened + timedelta(minutes=rng.randint(8, 600))
        tickets.append(dict(id="HH-2026-%04d" % n, kind=k[0], severity=k[2], queue=k[3],
                            opened=opened.isoformat() + "+02:00", closed=closed.isoformat() + "+02:00",
                            opened_by=opened_by, assigned=assigned, status="closed",
                            subject=k[4].format(**d), body=k[5].format(**d)))
    tickets.extend(RICH_TICKETS)
    tickets.sort(key=lambda t: t["opened"])
    return tickets


def gen_commits(rng):
    commits = []
    t = datetime(2026, 5, 4, 9, 0)
    for i in range(200):
        comp, msgs = rng.choice(COMMIT_TEMPLATES)
        msg = rng.choice(msgs).format(thing=rng.choice(THINGS), ver=rng.choice(VERS))
        t += timedelta(hours=rng.randint(2, 30))
        full = "%s: %s" % (comp, msg)
        commits.append(dict(sha=sha(full + str(i))[:12], component=comp, message=full,
                            author=rng.choice(DEV_AUTHORS), date=t.isoformat() + "+02:00",
                            files=rng.randint(1, 9), pr=rng.randint(300, 520)))
    # the one the post-mortem points at
    commits.append(dict(sha=sha("retry default")[:12], component="nbs-api",
                        message="nbs-api: enable paygate retry by default", author="elena.moretti",
                        date="2026-09-15T11:20:00+02:00", files=3, pr=517))
    commits.sort(key=lambda c: c["date"])
    return commits


def gen_logs(rng):
    """JSON lines for nbs-web (through the api) and nbs-db, with two bursts and one pool exhaustion."""
    web, db = [], []
    paths = ["/api/search", "/api/quote", "/api/hold", "/api/pay", "/api/confirm", "/health", "/api/booking"]
    t = datetime(2026, 9, 12, 13, 0)
    for i in range(1500):
        t += timedelta(seconds=rng.randint(1, 8))
        path = rng.choice(paths)
        status, upstream, lat = 200, "-", rng.randint(20, 400)
        burst = datetime(2026, 9, 12, 14, 9) <= t <= datetime(2026, 9, 12, 14, 41)
        if path == "/api/pay":
            upstream = "paygate-adapter"
            if burst and rng.random() < (0.4 if t < datetime(2026, 9, 12, 14, 23) else 0.18):
                status, lat = 502, rng.randint(1800, 4200)
            elif rng.random() < 0.03:
                status = 402  # PAY-431 surfaced as 402 to the SPA
        if path == "/api/hold" and datetime(2026, 9, 12, 15, 30) <= t <= datetime(2026, 9, 12, 15, 42) and rng.random() < 0.5:
            status, lat = 500, rng.randint(900, 3000)
        web.append(json.dumps(dict(ts=t.isoformat() + "Z", level="error" if status >= 500 else "info",
                                   request_id=sha(str(i))[:16], method="GET" if path in ("/api/search", "/health", "/api/booking") else "POST",
                                   path=path, status=status, latency_ms=lat, upstream=upstream,
                                   code="PAY-502" if status == 502 else ("PAY-431" if status == 402 else None))))
    t = datetime(2026, 9, 12, 13, 0)
    for i in range(500):
        t += timedelta(seconds=rng.randint(5, 30))
        line = "LOG:  checkpoint complete" if rng.random() < 0.2 else "LOG:  duration: %d ms  statement: select ... from bookings where pnr = $1" % rng.randint(2, 60)
        if datetime(2026, 9, 12, 15, 30) <= t <= datetime(2026, 9, 12, 15, 42):
            line = "FATAL:  remaining connection slots are reserved for non-replication superuser connections"
        db.append("%s UTC [%d] %s" % (t.strftime("%Y-%m-%d %H:%M:%S"), 1000 + i % 60, line))
    return web, db


# ---------------------------------------------------------------------------
# Evaluation material: ground truth and the one-question-many-audiences set
# ---------------------------------------------------------------------------

EXPECTED_TAGS = {
    "wiki/nbs-architecture.md": dict(tags=["service:nbs", "service:paygate", "service:sirius", "topic:kubernetes", "topic:database"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/nbs-runbook-checkout-failures.md": dict(tags=["service:nbs", "service:paygate", "kind:runbook", "topic:checkout"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/nbs-runbook-deploy-rollback.md": dict(tags=["service:nbs", "kind:runbook", "topic:deploy", "topic:kubernetes"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/nbs-runbook-db-connections.md": dict(tags=["service:nbs", "kind:runbook", "topic:database"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/paygate-integration.md": dict(tags=["service:paygate", "topic:checkout"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/sirius-retirement-plan.md": dict(tags=["service:sirius", "kind:script"], personal=False, mixed=True, sensitivity="internal",
                                           split={"booking-platform": "timeline and bridge", "customer-support": "what Customer Care needs to know"}),
    "wiki/visionx-port-ops-guide.md": dict(tags=["service:visionx", "topic:port", "kind:guide"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/visionx-telemetry-alerts.md": dict(tags=["service:visionx", "topic:telemetry", "kind:guide"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/helpdesk-l1-refund-script.md": dict(tags=["kind:script", "topic:refund", "service:helphub"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/helpdesk-l1-checkin-script.md": dict(tags=["kind:script", "topic:check-in"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/helpdesk-escalation-matrix.md": dict(tags=["kind:script", "service:helphub"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/supplier-cardinalpay-rate-card.md": dict(tags=["topic:supplier", "kind:contract", "service:paygate"], personal=False, mixed=True, sensitivity="confidential",
                                                   split={"booking-platform": "profile, support, SLA", "finance": "rates and volumes"}),
    "wiki/hr-roster-ops-oncall-q4.md": dict(tags=["kind:roster", "topic:on-call", "personal:yes"], personal=True, mixed=False, sensitivity="restricted",
                                            note="Ingested with lineage. The on-call name for a week may be derived for ops-desk; phone, contract, allowance and the medical note may not."),
    "wiki/qa-environment-access.md": dict(quarantine=True, reason="passwords, an access key and a card number", never_in_raw=True),
    "wiki/incident-2026-09-12-nbs-checkout-outage.md": dict(tags=["service:nbs", "service:paygate", "kind:incident", "topic:checkout", "severity:p1"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/onboarding-new-ops-engineer.md": dict(tags=["topic:onboarding", "topic:access", "topic:on-call"], personal=False, mixed=True, sensitivity="internal",
                                                split={"people": "week 1 People, allowance", "booking-platform": "access and shadowing"}),
    "wiki/security-policy-credentials.md": dict(tags=["kind:policy", "topic:credentials", "topic:access"], personal=False, mixed=False, sensitivity="internal"),
    "wiki/pricing-season-2027.md": dict(tags=["topic:pricing", "kind:contract"], personal=False, mixed=False, sensitivity="confidential"),
    "wiki/nbs-faq-back-office.md": dict(tags=["service:nbs", "kind:guide", "kind:script"], personal=False, mixed=False, sensitivity="internal"),
    "tickets/HH-2026-0301": dict(tags=["kind:ticket", "severity:p1", "topic:checkout", "service:paygate"], personal=False, mixed=False, sensitivity="internal"),
    "tickets/HH-2026-0077": dict(quarantine=True, reason="card number in the body", never_in_raw=True),
    "tickets/HH-2026-0119": dict(quarantine=True, reason="password in the body", never_in_raw=True),
    "tickets/HH-2026-0140": dict(tags=["kind:ticket", "personal:yes", "topic:on-call"], personal=True, mixed=False, sensitivity="restricted"),
}

QUESTIONS = [
    dict(id="Q1", question="A customer on the phone gets PAY-502 at payment. What do I do?",
         returns={
             "helpdesk-l1": "A five line script: what to say, one check in the back office (is deferred checkout on), the condition to open a P2 in Platform. No system names. Under 120 words.",
             "ops-desk": "The checkout failures runbook as a checklist with commands, plus the live panel: adapter pods, last 15 minutes of upstream errors, CardinalPay status. Last change: the retry flag default (commit, 15 September).",
             "developer": "Code path pay -> paygate_adapter.client.authorize -> retry.py; ADR-007; the post-mortem of 12 September; the test that covers the backoff.",
             "functional-analyst": "What the customer sees, how many holds expire per minute of outage (from the post-mortem: about 38), the deferred checkout decision (ADR-005) and its customer wording. No commands.",
             "finance-controller": "No page in the finance wiki answers this. 404 with a pointer to the SLA credit clause in the supplier item.",
             "hr-partner": "404.",
         }),
    dict(id="Q2", question="Is NBS checkout healthy right now?",
         returns={
             "ops-desk": "The ops agent's live view: web.health, web.metrics authorize error rate, db.recent_failures, adapter log tail, with Jev's anomaly score, as a candidate panel.",
             "helpdesk-l1": "One line derived from the same live view: 'Payments are working normally' or 'Payments are degraded; use the deferred checkout script'. Nothing else.",
             "roberto.mancuso": "Three bullets: status, risk, who is on it. Same role rights as ops-desk, a different return.",
         }),
    dict(id="Q3", question="What do we pay CardinalPay per transaction?",
         returns={
             "finance-controller": "The rate table and the 2026 volume line from the finance item split out of the supplier page.",
             "ops-desk": "The supplier profile item: support hours, SLA, contact path. The rates are in another domain: not shown, not hinted.",
             "helpdesk-l1": "404.",
         }),
    dict(id="Q4", question="Who is on call for NBS this weekend?",
         returns={
             "ops-desk": "The primary and secondary names for the week, derived from the roster. No phone numbers, no contract, no allowance, no medical note.",
             "hr-partner": "The roster row, with the retention rule restated.",
             "helpdesk-l1": "'Open a P1 in the Platform queue; the on-call is paged automatically.' Names are not needed to do the job.",
             "security-monitor": "Not the roster: the lineage of the roster item, who could see it and who did.",
         }),
    dict(id="Q5", question="Why did we retire Sirius and what happens to old bookings?",
         returns={
             "functional-analyst": "ADR-001 reasoning, the retirement timeline, the customer-facing consequences.",
             "helpdesk-l1": "The legacy toggle and the rebook-and-refund steps, from the Customer Care item split out of the retirement plan.",
             "developer": "ADR-008, sirius-bridge read-only guard commit, the archive export task.",
         }),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fixtures")
    args = ap.parse_args()
    out = Path(args.out)
    rng = random.Random(SEED)

    # org
    write_json(out / "org" / "company.json", COMPANY)
    write_json(out / "org" / "roles.json", ROLES)
    write_json(out / "org" / "domains.json", dict(domains=DOMAINS, tags=TAGS, domain_tags=DOMAIN_TAGS, role_mappings=ROLE_MAPPINGS))
    (out / "org").mkdir(parents=True, exist_ok=True)
    with (out / "org" / "people.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["principal", "kind", "name", "unit", "title", "manager", "groups"])
        for p in PEOPLE:
            w.writerow([p[0], "person", p[1], p[2], p[3], p[4], ";".join(p[5])])
        for a in AGENTS:
            w.writerow([a[0], "agent", a[1], "Platform Engineering", "service account", "roberto.mancuso", ";".join(a[2])])
    write_json(out / "org" / "rendering_profiles.json", {p[0]: p[6] for p in PEOPLE})

    # wiki
    for name, pg in PAGES.items():
        fm = "---\ntitle: %s\nowner: %s\nspace: %s\nupdated: 2026-09-%02d\n---\n\n" % (pg["title"], pg["owner"], pg["space"], rng.randint(1, 27))
        (out / "wiki").mkdir(parents=True, exist_ok=True)
        (out / "wiki" / name).write_text(fm + pg["body"], encoding="utf-8")

    # adr
    for aid, title, date, author, text in ADRS:
        (out / "adr").mkdir(parents=True, exist_ok=True)
        (out / "adr" / (aid.lower() + ".md")).write_text(
            "# %s: %s\n\nDate: %s\nAuthor: %s\nStatus: accepted\n\n%s\n" % (aid, title, date, author, text), encoding="utf-8")

    # volume
    tickets = gen_tickets(rng)
    write_json(out / "tickets" / "tickets.json", tickets)
    commits = gen_commits(rng)
    write_json(out / "repo" / "commits.json", commits)
    web, db = gen_logs(rng)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    (out / "logs" / "nbs-web.jsonl").write_text("\n".join(web) + "\n", encoding="utf-8")
    (out / "logs" / "nbs-db.log").write_text("\n".join(db) + "\n", encoding="utf-8")

    # eval
    write_json(out / "eval" / "expected_tags.json", EXPECTED_TAGS)
    write_json(out / "eval" / "questions.json", QUESTIONS)

    manifest = dict(seed=SEED, generated="2026-09-29", company=COMPANY["name"],
                    counts=dict(people=len(PEOPLE), agents=len(AGENTS), roles=len(ROLES), domains=len(DOMAINS),
                                tags=len(TAGS), wiki_pages=len(PAGES), adrs=len(ADRS), tickets=len(tickets),
                                commits=len(commits), web_log_lines=len(web), db_log_lines=len(db),
                                planted_quarantines=sum(1 for v in EXPECTED_TAGS.values() if v.get("quarantine")),
                                mixed_items=sum(1 for v in EXPECTED_TAGS.values() if v.get("mixed")),
                                personal_items=sum(1 for v in EXPECTED_TAGS.values() if v.get("personal"))))
    write_json(out / "manifest.json", manifest)
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
