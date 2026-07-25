# ADR-015 — Communications as a Core Operational Subsystem

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Supersedes:** any reading of email/SMS as optional side integrations or post-MVP extras.
**Preserves:** ADR-003 (bad-news and money communications keep their human gates), ADR-004
(a sent message is an external effect), ADR-006 (unknown delivery outcomes are verified, not
retried blindly).

---

## 1. Decision

Communications are a **first-class operational subsystem** with three simultaneous roles:

1. **Evidence source** — commitments, authorizations and facts arrive by message.
2. **Operational surface** — where work is requested, chased and confirmed.
3. **External effect channel** — an outbound message changes the world and is governed exactly
   like any other consequential effect.

**Email and SMS are required production capabilities for the first commercially useful workflow**
(Delivered Load Closure) — not postponed extras. The implementation program (P9 ingestion, P12
supervised sends) carries this obligation.

## 2. Coverage

Gmail and Microsoft 365 · shared and individual authorized mailboxes · email threads, replies,
forwarding and attachments · SMS · inbound and outbound phone/voice evidence · Slack and Teams ·
customer and carrier portals · EDI and API messages · delivery receipts, bounces and failures ·
message correlation to tenants, people, companies, loads and Work Items · commitments made
through communications · expected responses and follow-up timers · escalation · quiet hours ·
opt-out and consent · templates versus model-generated content · sender identities and
reputation · duplicate prevention · unknown delivery outcomes · communication audits.

## 3. The message-effect contract

Every outbound message is an external effect associated with: **a Work Item · recipient identity
· tenant · purpose · authority · evidence · content digest · delivery state · expected response ·
verification · escalation policy.**

Rules that follow directly from the existing safety spine:

- An outbound message requires the same grant/checkpoint path as any external effect; the
  message's Material Facts include recipient, purpose and content digest.
- **Duplicate prevention is identity, not luck**: the effect identity (Commit Key discipline)
  makes "send the same chase twice" one effect.
- A send with no delivery evidence is **UNKNOWN_OUTCOME** — verified, never auto-resolved.
- An inbound message is an Observation with provenance; a commitment extracted from it is
  `MODEL_EXTRACTED` until a human or a deterministic rule confirms it. **A model-asserted
  authorization is never sufficient to authorize a consequential action** (ADR-003).
- Expected responses create **Expectations** with timers; a silent counterparty is a first-class
  trigger, not an invisible nothing.
- Bad-news communications and any communication that moves money keep permanent human gates
  (ADR-003).

## 4. Consequences

- The **conversational operations layer** (ADR-019) rides on this subsystem: it uses these
  channels as its rendering surfaces, and its consequential instructions are governed messages/
  effects exactly as here — conversation adds a natural-language surface, never a new effect path.
- P9 gains communications **ingestion** (correlation, evidence, expectations); P12 gains
  **supervised outbound** sends; the production architecture (ADR-016) gains communications
  workers and provider credentials (governed by ADR-014).
- Nothing is implemented by U-REBASELINE-1 — the decision is durable; the capability lands in
  the revised phases.
