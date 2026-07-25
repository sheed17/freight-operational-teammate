# ADR-019 — Persistent Conversational Operations Layer

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Builds on:** ADR-002 (provenance), ADR-003 (authorization assertion), ADR-004 (effect boundary),
ADR-006 (verification / unknown outcomes), ADR-015 (communications), ADR-017 (web control plane),
ADR-018 (operational graph). **Enforces** engineering rule 9 (events — and now conversation —
cannot grant execution authority) and rule 14 (one coherent identity, not a swarm of agents).

---

## 1. Decision

Neyma provides a **persistent, role-aware conversational operations layer**. The experience should
feel like communicating with a highly attentive **operational teammate that keeps working between
conversations** — not a chatbot, and not a separate orchestration system.

> **The conversational layer is a surface over the canonical spine, never a parallel system.** It
> operates through the same **tenant identity · user identity and role · Work Items · operational
> state · evidence · obligations · policies · approvals · effect controls · verification · audit
> history** as every other part of Neyma. It owns no state of its own.

## 2. What users can do

Ask what is happening · ask why something happened · ask what remains open · issue natural-language
operational requests · provide missing context · correct information · approve or reject bounded
actions · request summaries · ask for supporting evidence · take over work · communicate through
text or voice where supported.

## 3. Proactive ownership (not request-only)

Neyma communicates **proactively**, not only when asked, when: a genuine decision is required · an
obligation is late · evidence conflicts · an external outcome is unknown · a policy boundary is
reached · customer or financial risk increases · work completes · responsibility changes · a
promised follow-up is due. **A teammate that only answers when spoken to has not done its job.**

## 4. Response transparency — the mandatory taxonomy

Every operational response distinguishes, explicitly: **what Neyma knows · what it inferred · what
it completed · what it verified · what failed · what remains unknown · what it is waiting for ·
what it will do next · whether a human must act.** Inference is never presented as fact
(ADR-002); completion is never presented without verification (§6).

## 5. Conversation is never authority and never truth

- **Conversation is never a second source of truth.** The canonical operational state is the
  source; the conversation reads and proposes against it.
- Natural-language interpretation **may create**: a proposed intent · a draft Work Item · structured
  constraints · a request for clarification · a proposed external action.
- It **may not** independently create consequential authority.
- **A conversational instruction that would cause a consequential external effect passes through
  the same authentication, authorization, policy, evidence, approval, idempotency, effect-grant and
  verification controls as every other action** (ADR-003/004). Voice is architecturally supported
  **through the same structured-intent and authority pipeline** — never a separate effect path.

## 6. Honesty invariants

- **Neyma must not pretend to be human.**
- **Neyma must never claim an action was completed unless the required completion and verification
  evidence exists** (ADR-006; UNKNOWN_OUTCOME is stated as unknown, never as done).
- Neyma may **remember approved tenant preferences with provenance** — a preference is an
  `OWNER_ASSERTED` fact, not a silently learned default.

## 7. One identity, every channel, one conversation

**One coherent Neyma identity with role-aware experiences** — not disconnected agents with
conflicting personalities, memory or authority. It may be rendered through **Neyma web · Slack ·
Microsoft Teams · email · mobile · voice · other approved channels**, and **all channels resolve to
the same conversation, Work Item and operational history** where applicable. Channel-specific memory
divergence is a defect.

- The **web control plane** (ADR-017) includes a **conversational workspace alongside** structured
  queues, evidence packets, configuration and operational history.
- **Slack and Teams** support conversational requests and bounded actions (through §5's pipeline).

## 8. Acceptance criteria — the seven preventions (guarded)

The rebaseline records these as durable acceptance criteria; guards
(`eval/tests/test_rebaseline_invariants.py`) prevent their violation from re-entering current
authority, and the implementing phases must satisfy them:

1. **No chatbot-only product design** — the conversational layer is a surface over the operating
   engine, not the product.
2. **Conversation is never canonical state.**
3. **Conversation is never independent authority.**
4. **No unverified claims of completion.**
5. **No channel-specific memory divergence** — all channels resolve to one conversation/history.
6. **No disconnected personas with conflicting authority** — one coherent identity.
7. **No passive request-only behavior where proactive ownership is required** (§3).

## 9. External interaction reference — non-binding

**Jack & Jill AI** is used as **one non-binding interaction-design reference** for the *quality* of
a conversational product experience — conversational onboarding, a persistent agent identity,
role-aware communication, natural back-and-forth, continuity across conversations, proactive
updates, clear explanation of what the agent is doing, work continuing between interactions, and the
feeling of an attentive agent rather than form-based software.

**Recorded honestly:** Jack & Jill is a **conversational recruiting/career product, not a freight
product**, and it uses **two personas** (Jack for candidates, Jill for employers). Its two-persona
split is a **contrast**, not a model — Neyma is deliberately **one identity** (§7). It is an
interaction reference **only**; per ADR-012, **no competitor defines Neyma's canonical identity**.
Neyma's identity, freight workflows, operational state, authority, evidence, safety controls and
production architecture are designed from **Neyma's own customer needs and repository evidence**.
High-quality conversational and agentic products generally are additional references; the design is
**not overfit to any single company**.

**The lesson:** communicate naturally and continuously like an attentive operational teammate, while
executing through a **deterministic, auditable, authority-controlled** freight operating engine.

## 10. Consequences

- Nothing is implemented by U-REBASELINE-1. The capability lands in the phases that already carry
  its foundations: **P9** (conversational intent ingested as *proposed*, with provenance — never
  authority), **P11** (the conversational workspace in the control plane; cross-channel continuity;
  role-aware experiences), **P12** (a conversational instruction that causes an effect routed
  through the full kernel). Voice rides the same pipeline whenever it is added.
- Sources for the non-binding reference: jackandjill.ai; TechCrunch (2025-10-16).
