# Stream B — Architectural Lessons (code NOT promoted)

**Status:** **ARCHITECTURE INPUT — BINDING.** These four findings are promoted into the architecture.
**The code that produced them is not.** It remains preserved on `preserve/pre-reset-readiness-hardening`
and is **not approved for production inclusion**.

**Source:** `docs/architecture/stream-b-review.md` (B1–B4).
**Baseline:** `f0e801b`. **Date:** 2026-07-13.

> **Why this document exists.** Stream B was written by someone competent, in one focused burst, with
> good instincts and green tests — and **two of its four changesets silently destroy the owner's work.**
> Deleting the code and moving on would throw away the most valuable thing it produced: **four precise
> statements of what the architecture must make impossible.** Each is now a constraint on ADR-004,
> ADR-008, and the Wave 2 ADRs.

---

## L-A — Machine inference must never overwrite human-authored native state

**Binding rule.** Every identity binding, routing decision, and correction carries a **provenance class**:

| Provenance | Meaning | May a machine recompute it? |
|---|---|---|
| `OWNER_ASSERTED` | A human decided this | **NEVER.** |
| `LINKER_INFERRED` | The system derived this | **Yes** — it is projected state; rebuild it freely. |
| `SYSTEM_IMPORTED` | An external system asserted this | Only by re-import from the same authority. |

> **Machine recomputation may not overwrite an `OWNER_ASSERTED` binding. Not on a better model, not on a
> better linker, not on a later cycle, not ever.**

**If the linker later disagrees with an `OWNER_ASSERTED` binding, that is a `conflicting` observation** —
it is raised as a **Conflict** with a human owner. **It is never silently resolved in either direction.**
*(Operating Model **I8**: missing evidence and contradictory evidence are different states.)*

**How Stream B violated it.** B3 recomputed `hinted_load_id`, `linked_load_ids`, and `packet_load_id`
from the linker **every intake cycle**, and had **no field expressing who decided them** — so no guard was
even expressible. B4 wrote human bindings into exactly those three fields. **The owner corrects the
machine; the machine un-corrects itself on the next tick; the audit log still says the correction
stands.** That is an inference masquerading as projected truth — **precisely what ADR-002 forbids.**

**Binds:** ADR-002 (state classes), **ADR-007** (identity & claims), **ADR-008 §3.6** (Identity Binding
Claim lifecycle — `SUPERSEDED` may be reached **only** by a deterministic rule or a human, never by a
re-run of the inferring component).

---

## L-B — A human correction must bind to an immutable identifier, never an ordinal

**Binding rule.** A human decision is bound to the **immutable identity of the work item or artifact**
(`observation_id`, `work_item_id`, `document_id`) — **never to a position in a list.**

> **An ordinal is a rendering artifact. It is not an identity.**

**If ordinal UX is retained** — and it should be, because `assign unlinked 2 to LD-4471` is genuinely how
an owner wants to talk — then:

1. The displayed ordinal **resolves immediately, at render time, to an immutable identifier**;
2. that identifier is **carried in the interaction** (the Slack block value, the pending-op record);
3. **the eventual action is bound to the identifier, never re-resolved against the list;**
4. if the identifier no longer exists or has changed state, the action **fails closed and says so** — it
   does not fall back to position.

**How Stream B violated it.** B4's `^assign\s+unlinked\s+(\d+)\s+to\s+…` re-resolved `N` against a list
**re-derived every cycle**. New mail arriving between the render and the command silently re-points the
assignment. **The owner binds a document to a load they never looked at.**

> **This is the same class of error as the money fence: the identity that gets acted on must be the
> identity the human approved.** The money fence already knows this. The identity layer did not.

**Binds:** **ADR-005** (approval binding — the approved *subject* is bound, not re-resolved),
**ADR-007**, and the pre-effect checkpoint's **material-facts fingerprint** (ADR-004 §2.4).

---

## L-C — A natural-language acknowledgement must not imply a deterministic rule was installed

**Binding rule.** The system **may not respond `"Noted the procedure"`** — or any phrasing that implies a
rule now governs its behaviour — **unless a real structured rule was created, validated, scoped,
versioned, and made enforceable.**

**A prompt-string memory is not a policy.**

| | A **policy** | A **memory** |
|---|---|---|
| Representation | structured, typed rule | free text |
| Scope | explicit (tenant, lane, action class) | implicit |
| Versioned | yes — and the **policy version binds into the pre-effect checkpoint** | no |
| Enforced by | a **deterministic guard** that can refuse an effect | an LLM's attention |
| Failure mode | **fails closed** | **silently ignored** |
| Honest reply | *"That rule is now enforced. I cannot bill without a POD."* | *"I'll keep that in mind."* |

> **If the owner believes they installed a control, and what they installed was a suggestion, the system
> has lied — and the owner will stop checking the thing they think is now guarded.** That is strictly
> worse than refusing the request.

**How Stream B violated it.** B4's `never bill without POD` wrote a `PROCEDURE` fact into the knowledge
base, which is recalled into the **model's prompt** (`operator_agent.py`) — and replied
`":clipboard: Noted the procedure for raise_invoice."` The real POD gate is the **code-level document
fence** (Stream A), which is genuine. So it was **not unsafe** — but the owner was told they installed a
rule, and they did not.

**Consequence for the architecture:** owner-stated rules must **compile to policy** (a typed, versioned,
enforceable predicate evaluated in checkpoint step 6) **or be honestly reported as memory.** There is no
third option. **A control the owner believes in must be enforced in code, or it must not claim to be a
control.**

**Binds:** **ADR-010** (policy & autonomy), ADR-004 §2.4 step 6 (**policy-version binding**),
Engineering Principle **P2** (guards are never model-evaluated).

---

## L-D — Retry classification must distinguish permanent failures from transient ones

**Binding rule.** Every retry policy classifies each failure as **TRANSIENT** or **PERMANENT**, explicitly,
by an allowlist — **never by a catch-all base class.**

- **TRANSIENT** (transport): socket reset, timeout, throttle, server-closed-connection ⇒ bounded retry
  with backoff.
- **PERMANENT** (authentication, authorization, configuration, protocol, malformed request) ⇒
  **fail loudly, immediately, once.** **Never retried.** It raises an **Exception with a human owner.**

> **A permanent credential failure retried forever is not resilience. It is a system hiding a fixable
> problem from the only person who can fix it** — while looking, from the outside, like an intermittent
> transient. That is the most expensive class of bug to diagnose.

**Additional:** a permanent auth failure retried in a tight loop against a provider (Gmail, a TMS,
a factoring portal) invites **rate-limiting or a security block** — converting a five-minute password fix
into an account lockout.

**How Stream B violated it.** B1 placed **`imaplib.IMAP4.error`** in its transient set. That is the
**base class for IMAP protocol and authentication errors** — a stale `NEYMA_IMAP_PASSWORD` would be
retried 3× every cycle, forever.

**Credit where due:** B1's `.eml` write is **content-addressed and existence-guarded**, so a retry cannot
duplicate a message. **Retry idempotency was correct.** Retry *classification* was not. The architecture
must require **both** — and today only idempotency is written down.

**Binds:** **ADR-006** (verification & unknown-outcome), **ADR-008 §2.9** (crash recovery: *recovery never
guesses; it re-derives or it escalates*), and the **Exception** lifecycle (ADR-008 §3.9).

---

## SUMMARY — what these four become

| Lesson | Becomes | In |
|---|---|---|
| **L-A** | Provenance class on every binding; `OWNER_ASSERTED` is never recomputed; disagreement raises a **Conflict** | ADR-002, ADR-007, ADR-008 §3.6 / §3.7 |
| **L-B** | Human decisions bind to immutable identity; ordinals resolve **at render time** | ADR-005, ADR-007 |
| **L-C** | Owner rules **compile to enforceable policy** or are honestly reported as memory | ADR-010, ADR-004 §2.4(6) |
| **L-D** | Explicit TRANSIENT/PERMANENT retry classification; **permanent failures never retry** | ADR-006, ADR-008 §2.9 |

> **All four changesets had passing tests. Two of them silently destroy the owner's work.**
> **Tests passing was never evidence.** These lessons are what Stream B was actually for.
