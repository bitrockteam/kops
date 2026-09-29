---
title: Policy: credentials and secrets
owner: anna.vitali
space: Security
updated: 2026-09-10
---

# Policy: credentials and secrets

1. Credentials live in the platform vault. Never in wiki pages, tickets, chat, repositories or config maps.
2. A page or ticket found to contain a credential is quarantined by the ingest pipeline, never stored,
   and the security monitor is notified with the source and the author. The credential is rotated
   within 24 hours.
3. Personal data is ingested only from pages that state a retention rule, and every access path is traced.
4. Agents get read-only, named, time-bounded credentials through a gateway. No agent holds an SSH key.
