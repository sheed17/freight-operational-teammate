# ADR-014 — Credential and Machine-Identity Posture

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Supersedes:** the absolute "`human_established_session_only` — Neyma never holds external
credentials" wherever it was stated as a permanent universal rule (CLAUDE.md §10, PRODUCT.md §5,
ARCHITECTURE.md, README.md, adapter specs 02/10 and the adapter registry auth rows).
**Preserves — permanently:** **authentication does not create action authority.** A valid
credential, session, API token, database connection or reachable adapter **never independently
authorizes an external effect** (ADR-004, TOOL-ACCESS-POLICY).

---

## 1. Decision

Neyma **may securely possess customer-authorized authentication material.** The permanent
security rule is:

> **Neyma minimizes handling of employees' raw personal credentials and prefers dedicated,
> scoped machine identities.**

Architecturally permitted access models: OAuth grants and refresh tokens · API keys · dedicated
service accounts · scoped bot users · EDI credentials · approved database connections · email
mailbox grants · accounting-system grants · SMS/communications-provider credentials ·
tenant-specific browser identities · managed encrypted browser sessions · human-established
browser sessions · desktop or VDI automation where required · webhooks · supported file-transfer
mechanisms · other customer-approved adapters.

## 2. Preferred integration order

1. **Official APIs, webhooks, OAuth and supported integrations.**
2. **Dedicated service accounts** or scoped machine identities.
3. **EDI, database or approved file exchange.**
4. **Managed customer-authorized browser automation.**
5. **Human-established session attachment** when safer supported access is not available.

Human-established browser attachment (`human_established_session_only`) remains a **supported
fallback and a valid per-tenant configuration choice** — it is no longer a universal identity or
deployment requirement. Existing tenant configs that select it remain correct.

## 3. Governance — required wherever Neyma possesses authentication material

Explicit customer authorization · tenant isolation · least privilege · encryption at rest and in
transit · access controls · audit logs · revocation · rotation · expiry where supported ·
purpose limitation · environment separation · incident-response procedures · customer
offboarding and credential destruction.

Credentials resolve **only inside the adapter boundary on a claimed grant**; agents, prompts,
logs and tooling never hold or see raw secrets. Secrets never enter the repository (`.env`
gitignored; production uses managed secrets — ADR-016).

## 4. Consequences

- The adapter specifications' auth rows are amended: rule 2-style scoped machine identities are
  the preferred path per external system; `human_established_session_only` is one supported
  session policy among several, chosen per tenant.
- P4 (containment) and the credential surfaces deferred to it now cover **all** permitted access
  models, not only browser attachment.
- Nothing here is implemented by U-REBASELINE-1; this ADR makes the decision durable. Credential
  infrastructure lands with the phases that need it (P4 boundary, P11 onboarding).
