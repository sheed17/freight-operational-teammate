# ADR-004 — The Structurally Enforced Single Effect Boundary

**Status:** ✅ **FINAL — ACCEPTED.** *(Superseded the DRAFT of 2026-07-11. All open questions resolved by owner decision, 2026-07-13.)*
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Resolves:** correction-plan **Group A** — **F-02** (CRITICAL), the capability half of **F-35**, **F-18** (as a free consequence), and the effect-mutual-exclusion half of **F-07** / audit **R-02**.
**Paired with:** **ADR-008** (durable machines, outbox, inbox). Neither ADR is implementable without the other.
**Blocks:** everything. **This is the keystone. No other mechanism in the architecture is real until this one exists.**

---

## 1. CONTEXT

The Target Specification §19 declares itself *"the single effect boundary"* and §23.4 declares that agents *"have no privileged path to any external system."*

**Neither claim was backed by a mechanism.** Anything that can import an adapter reaches the outside world: a migration script, an admin tool, a retry handler, a compensating workflow, a background reconciler, a well-meaning engineer, **or an AI coding agent implementing from this document.**

The entire safety model — money fence, document fence, approval gates, verify-by-readback, commit-once, audit provenance — **rests on the assumption that all effects flow through one place.** That assumption was enforced by **convention**, which is to say **not at all**.

> **A boundary enforced by good intentions is not a boundary. It is a comment.**

The repository audit proved this is not hypothetical. **Eleven entry points could reach the live TMS. Six can still produce a live financial write.** And one production flag — **on by default** — routed human-approved payables into a **mock ledger** while reporting `DONE` to the owner (**R-01**, severed at `974031d`).

**This ADR makes bypass structurally impossible, not merely forbidden.**

---

## 2. DECISION

### 2.1 The rule

> **An external effect can only be produced by an adapter.**
> **An adapter can only act when presented with (a) a valid, claimable Effect Grant AND (b) a fresh Checkpoint Witness.**
> **An Effect Grant can only be minted by the Action Pipeline, and only from a passed atomic pre-effect checkpoint.**

**There is no admin path. There is no migration path. There is no emergency path. There is no agent path.**

### 2.2 The two-key rule *(owner decision — the most important refinement in this ADR)*

> **An Effect Grant is NECESSARY but NOT SUFFICIENT. The atomic pre-effect checkpoint must ALSO pass immediately before execution.**

A grant alone would answer *"was this attempt authorized?"* — a question about **the past**. It says nothing about whether **the world still looks the way it did when the grant was minted.** A grant minted, then queued behind a slow browser session for ninety seconds, then executed, would act on **stale facts** while carrying a perfectly valid capability.

**Therefore two keys are required at the adapter:**

| Key | Proves | Question it answers |
|---|---|---|
| **Effect Grant** | *the pipeline authorized this specific attempt* | *"May this attempt exist?"* — **authority** |
| **Checkpoint Witness** | *the seven checks passed moments ago, and the facts still hold* | *"Is the world still what we approved?"* — **freshness** |

**The adapter requires both. Neither substitutes for the other.** The window between witness and effect is the **only** window in which reality can drift, and it is made as small as physically possible (§7).

### 2.3 Three distinct lifetimes *(this distinction prevents the most likely misimplementation)*

| Concept | Answers | Lifetime |
|---|---|---|
| **Commit Key** | *"Which logical effect is this?"* | **Stable across all attempts.** Prevents double-commit. |
| **Effect Grant** | *"May this **one attempt** touch the world, right now?"* | **One attempt. Single-use. Never reused.** |
| **Approval** | *"Did a human authorize this committed effect?"* | **Survives a provably-failed attempt; consumed on commit.** (ADR-005) |

> **A retry re-uses the commit key. It NEVER re-uses the grant, and it NEVER re-uses a witness.**
> **Conflating these is how a single human approval becomes an unbounded licence to act.**

### 2.4 The atomic pre-effect checkpoint *(constitutional — preserved verbatim)*

**These seven checks occur as ONE atomic checkpoint. They are NOT independent checks separated by asynchronous work.**

1. **Approval validity** — present, unexpired, unrevoked, correct authority (ADR-005)
2. **Material-facts fingerprint** — void on drift (ADR-005)
3. **Projected-state freshness revalidation** — against the **authoritative source**, never a cache (ADR-001 **C4**)
4. **Native-state revalidation** — claims unretracted, unsuperseded, not `conflicting` (ADR-002)
5. **Entity-version concurrency check** (ADR-009)
6. **Policy evaluation** — caps, authority, autonomy, allowlists, **policy version**; the gate decision is **never null**
7. **Human-brake admission** (ADR-011)

**All seven pass ⇒ a `CheckpointPassed` witness exists ⇒ a grant may be minted.**
**Any one fails ⇒ no witness ⇒ no grant ⇒ no effect is possible.**

> **The brake is enforced by refusing to mint. That is why it is unbypassable, and why it never needs to kill a worker mid-flight.**

### 2.5 Owner decisions, recorded

| Decision | Ruling |
|---|---|
| **Actuation runtime location (v1)** | **Co-located inside the modular monolith.** (P36 — do not distribute what you cannot yet justify.) |
| **Future process separation** | **Must remain possible without changing the Effect Grant contract.** See §4 — this is why authority lives in the **ledger**, not in a type. |
| **`BREAK_GLASS` effect class** | **DOES NOT EXIST.** *An emergency path is a bypass with a nicer name.* |
| **What an emergency actually is** | **An authorized human acts directly in the external system.** Neyma **observes and reconciles** that action afterwards (ADR-001: external systems remain authoritative). **This is honest, and it is the only emergency path.** |
| **Privileged bypass for admin tools, migrations, retry handlers, compensation handlers, background workers, agents** | **NONE. For any of them. Ever.** They are ordinary pipeline clients. |
| **Replay** | **Can never mint or receive an Effect Grant.** Structurally — not by discipline (§4.4). |
| **Grant sufficiency** | **Necessary, not sufficient.** The checkpoint must also pass immediately before execution (§2.2). |

### 2.6 Explicit prohibitions

- **Agents never receive credentials, adapters, grants, or witnesses.** An agent's **only** output is a `ProposedIntent` — **inert data**. It cannot construct a witness, cannot mint a grant, cannot name an adapter.
- **Migration and administrative tooling receive no bypass.** A migration write uses a `MIGRATION` action class **with its own positively-asserted gate**.
- **Compensating actions pass through the same pipeline.** **A rollback is an effect**, and is subject to every rule an effect is subject to.
- **Inbound content may corrupt a proposal; it cannot create the capability to execute.** A fully compromised model produces **a bad `ProposedIntent`**, which the checkpoint then independently validates against reality. **Injection can make Neyma propose something stupid. It cannot make Neyma do something.** *(This is the actual wall behind F-35; content sanitisation is defence-in-depth.)*

---

## 3. THE EFFECT GRANT — CONCRETE MECHANISM

### 3.1 Issuer

**The Action Pipeline is the sole issuer.** There is exactly one minting function in the codebase:

```
mint_grant(witness: CheckpointPassed, target: TargetResource, ...) -> EffectGrantHandle
```

**`CheckpointPassed` has no public constructor.** It is produced **only** by the checkpoint function, on success. **Code that has not passed the checkpoint cannot even express a call to `mint_grant` — it has nothing to pass as the first argument.** *Capability by construction: the type system refuses to compile the bypass.*

### 3.2 Data model — the Effect Grant Ledger

**One durable table, in the same transactional store as pipeline state and the outbox (ADR-008 §2.4).**

| Column | Type | Binding | Why |
|---|---|---|---|
| `grant_id` | uuid, PK | — | Identity. |
| `tenant_id` | text, **NOT NULL** | **tenant binding** | An adapter refuses a grant whose tenant ≠ its operating context. **Always first, always present** (F-12). |
| `action_class` | enum, NOT NULL | **action-class binding** | `RAISE_INVOICE`, `RECORD_PAYABLE`, `FILE_DOCUMENT`, `SEND_OUTBOUND`, `MIGRATION`, … |
| `gate_decision` | enum, NOT NULL | — | `HUMAN_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `UNGATABLE_PERMANENT`. **Never null.** A null gate is an unasserted gate (F-20). |
| `target_system` | text, NOT NULL | **target-resource binding** | `tms:truckingoffice`, `email:smtp`, … |
| `target_resource_id` | text, NOT NULL | **target-resource binding** | `load:4471`. A grant for *invoice load 4471 in TMS-A* **cannot** invoice load 4472, or touch TMS-B. |
| `target_operation` | text, NOT NULL | **target-resource binding** | `create_invoice`. |
| `commit_key` | text, NOT NULL | **commit-key binding** | The stable identity of the **logical effect**. Survives retries. |
| `material_facts_fingerprint` | text, NOT NULL | **material-facts binding** | Hash over the facts the human saw (**amount, party, load, document**). **Drift ⇒ the approval is void** (ADR-005). |
| `entity_versions` | jsonb, NOT NULL | **entity-version binding** | `{"load:4471": 17}`. Optimistic concurrency, enforced at the same instant (ADR-009). |
| `policy_version` | text, NOT NULL | **policy-version binding** | The exact policy that authorized this. **A policy change invalidates in-flight grants** — you cannot act under a policy that no longer exists. |
| `approval_id` | uuid, **NULL only if** `gate_decision ≠ HUMAN_REQUIRED` | **approval binding** | Enforced by a DB **CHECK constraint**, not by code. |
| `checkpoint_id` | uuid, NOT NULL | **witness binding** | FK → `checkpoint_records`. **This is what makes the grant insufficient on its own.** |
| `pipeline_instance_id` | uuid, NOT NULL | — | FK → the durable machine (ADR-008). **An orphan grant is impossible.** |
| `state` | enum, NOT NULL | — | `GRANTED → CLAIMED` \| `EXPIRED` \| `REVOKED` |
| `issued_at` / `expires_at` | timestamptz | **expiry** | §3.4. |
| `claimed_at` | timestamptz, NULL | — | Set by the CAS. |
| `handle_digest` | text, NOT NULL | — | Digest of the issued handle. The handle itself is **never stored**. |

**Uniqueness:** `UNIQUE (tenant_id, commit_key) WHERE state = 'CLAIMED'` — **the database itself forbids two claimed grants for the same logical effect.** *Commit-once is a database constraint, not a code path.*

### 3.3 The token: **opaque and signed — and neither property is the security control**

The handle is a **256-bit random opaque identifier**, transported with an **HMAC signature**.

- **Opaque** — it carries no authority-bearing content. There is nothing in it to tamper with.
- **Signed** — the signature is a **cheap early-rejection filter**, so a garbage handle is refused without a database round-trip.

> **Forgery is irrelevant.** A forged handle names **no ledger row**, so the claim fails.
> **Replay is irrelevant.** A replayed handle attempts to claim an **already-`CLAIMED`** row, so the CAS fails.
> **The ledger is the authority. The token is a pointer.** Any design where the token *is* the authority reintroduces the bearer-token problem: a signature proves origin, **never single-use**.

### 3.4 Expiry

**Short, absolute TTL — seconds, not minutes.** The TTL must exceed the **claim-to-call** window, **not** the whole execution (browser actuation runs 20–35 s; the *claim* is placed immediately before the call).

**The TTL is not the security control** — the CAS is. **The TTL bounds the blast radius of a lost grant.** An expired grant is unclaimable; the pipeline re-runs the **full checkpoint** and mints a **new** one.

### 3.5 Single-use consumption

**An atomic compare-and-set in the ledger:**

```sql
UPDATE effect_grants
   SET state = 'CLAIMED', claimed_at = now()
 WHERE grant_id = $1 AND state = 'GRANTED' AND expires_at > now()
```

**Zero rows updated ⇒ the adapter does nothing and raises.** *(Already claimed, expired, or revoked — the adapter does not care which; all three mean "not now.")*

> **Single-use is a database guarantee, not a token property.** This is the one sentence in this ADR that, if ignored, loses everything.

### 3.6 Storage and revocation

Stored in the transactional store, **partitioned by tenant**, retained as **permanent audit evidence** (a grant is the record of *why* an effect was permitted).

**Revocation** = `GRANTED → REVOKED`, and any subsequent claim fails. Revocation is triggered by:
- **the brake** engaging for that tenant/action class (ADR-011),
- **approval revocation** (ADR-005),
- **a policy-version change** invalidating the authorizing policy,
- **an entity freeze** (`NEEDS_VERIFICATION`, `COMPENSATION_FAILED`, or an open **Conflict** on a material field).

**Revoking an unclaimed grant is always safe** — nothing has happened yet. **Revoking a claimed grant does nothing** — the effect may already exist; that is `UNKNOWN_OUTCOME` territory (§5), not a revocation.

### 3.7 Adapter validation — the complete algorithm

An adapter's **only** public entry point is:

```
execute(grant: EffectGrantHandle, witness: CheckpointWitness, params: EffectParams)
```

**In order, before touching the outside world:**

1. **Verify the handle signature.** Fail ⇒ reject (cheap filter).
2. **Load the grant row.** Absent ⇒ **Sev-0 security event** (a well-formed handle naming no row means someone is minting handles).
3. **Validate the witness:** `witness.checkpoint_id == grant.checkpoint_id`, the checkpoint record exists, and **it is within the freshness window.** A stale or mismatched witness ⇒ **refuse.** *(This is the two-key rule, enforced.)*
4. **Confusion check — the adapter re-validates the grant against its OWN call parameters:** `tenant_id`, `action_class`, `target_system`, `target_resource_id`, `target_operation`. **Any mismatch is a Sev-0 security event, not an error.** *(The confused deputy is the attack this defeats: a valid grant for a small effect, presented alongside parameters for a large one.)*
5. **CAS `GRANTED → CLAIMED`** (§3.5). Zero rows ⇒ **do nothing**, raise.
6. **Emit `EffectAttempted{grant_id, tenant, target}`** — *before* the call, so an orphan is detectable even if the call never returns.
7. **Only now: touch the outside world.**

**A single adapter with no grant parameter, anywhere in the codebase, invalidates the entire model.** This is enforced at build time (§4.2).

### 3.8 Retry semantics

**A retry mints a NEW grant, after re-running the FULL checkpoint.** Grants are **never** re-issued, re-used, or "refreshed."

The **commit key is unchanged** — which is precisely what makes the retry safe: `UNIQUE (tenant_id, commit_key) WHERE state='CLAIMED'` means **if the first attempt actually committed, the second attempt's claim cannot succeed.**

> **The retry does not need to know whether the first attempt worked. The database knows.**

### 3.9 Unknown-outcome semantics

**Crash after `CLAIMED`, before a confirmed result ⇒ we CANNOT distinguish "claimed but never called" from "called and lost the response."**

> **Therefore we MUST NOT assume nothing happened.**

The effect enters **`NEEDS_VERIFICATION`** (ADR-006 / ADR-008 §2.13): the **commit key stays reserved**, the entity is **frozen** for consequential actions, and a human is escalated **with the dollar exposure stated**.

**It MUST NOT time out into success. It MUST NOT time out into failure.** Resolution is by **readback** (ADR-006), or by a human establishing reality. **Never by retry.**

> **Any timeout here is a decision to guess about money.**

---

## 4. ENFORCEMENT — four layers, none of them discipline

*(No naming conventions. No code-review checklists. No prompts. No documentation.)*

### 4.1 Type-level (primary, preventive)
`mint_grant(witness: CheckpointPassed, …)`. **`CheckpointPassed` has no public constructor.** Code that has not passed the checkpoint **cannot express** a call to mint.

### 4.2 CI-level (preventive) — **the import-graph gate**
**A static import-graph check fails the build if any module outside `pipeline/` imports `adapters/`.**
**Not skippable. Part of the merge gate. No exemption list.**

Additionally: **every adapter's public entry point must accept an `EffectGrant` and a `CheckpointWitness`** — asserted by signature inspection over the whole `adapters/` package. **An adapter that forgets is a build failure, not a review comment.**

### 4.3 Module-level (preventive)
Adapter constructors are **module-private**. The adapter registry is reachable **only** from `pipeline/`. **Credentials resolve only inside an adapter, only on presentation of a claimed grant** — they are never reachable by agents, tooling, or even the pipeline itself.

### 4.4 Database-level (preventive)
The CAS (§3.5) and `UNIQUE (tenant_id, commit_key) WHERE state='CLAIMED'` (§3.2). **The database is the final arbiter of "may this act."**

**This is also why process separation stays possible without changing the contract (owner decision §2.5):** authority lives in a **shared transactional ledger**, not in a process-local type. When the actuation runtime is extracted, **it must still claim from the same ledger.** **A process boundary confers no privilege.** The type-level check is a compile-time convenience; **the ledger is the actual boundary.**

### 4.5 Runtime (detective — the backstop, never the control)
Every adapter invocation emits `EffectAttempted`. A continuous reconciler asserts **every `EffectAttempted` has a matching CLAIMED grant and a live pipeline instance.**

> **An adapter invocation with no matching claimed grant is a Sev-0**: it **auto-engages the brake** for that tenant + action class and pages a human. *It means the preventive layers have failed, and the system is acting outside its own boundary.*

### 4.6 Replay is structurally inert
**Replay does not perform live revalidation ⇒ it cannot construct a `CheckpointPassed` ⇒ it cannot mint a grant ⇒ it cannot act.** *(F-18 gets its guarantee for free — a consequence of the capability model, not a discipline to maintain.)*

---

## 5. HOW THIS RETIRES THE SIX WRITE-CAPABLE ENTRY POINTS (R-02 / F-07)

**The entry points are NOT modified by this ADR** (owner decision). **They do not need to be.** Under this mechanism they **simply stop working**, and that is the correct outcome.

| # | Entry point | What happens the day ADR-004 lands |
|---|---|---|
| **1** | `run_action_callback_server.py` | Already routes through the gated spine. **Becomes the canonical pipeline client.** Keeps working. |
| **2** | `run_teammate.py` | Supervises #1. **Keeps working.** |
| **3** | `propose_ar_from_tms.py` | **Becomes a pipeline client** (it proposes; the pipeline effects). Keeps working. |
| **6** | `enter_truckingoffice_invoice.py` | Calls the write driver directly from a terminal. **The import-graph gate fails the build; if it somehow ran, the adapter would refuse — it has no grant.** ⇒ **must become a pipeline client, or be deleted.** |
| **7** | `enter_invoice_discovered.py` | Same. ⇒ **pipeline client or deleted.** |
| **9** | `run_operate_request.py` | Terminal-approved live write. **Refused — a terminal is not an approval authority, and it cannot mint.** ⇒ **pipeline client or deleted.** |
| **10** | `run_operator_agent.py` | An agent on a live TMS with a local approver. **Refused absolutely — an agent can never hold a grant** (§2.6). ⇒ **TEST_ONLY or deleted.** |

**And the deeper fix — the one R-02 is actually about:**

> **The Effect Grant Ledger IS the shared entity-reservation namespace.** Two entry points can no longer bill the same load, because `UNIQUE (tenant_id, commit_key) WHERE state='CLAIMED'` **physically forbids a second claimed grant for the same logical effect** — no matter which process, script, agent, or human initiated it.
>
> **There is no second write path, because there is only one thing in the system that can say "yes": one table, one row, one CAS.**

**Until then, R-02 is open and mitigated only by operator discipline** (runbook warning). **The warning does not resolve R-02. This ADR does — when it is built.**

---

## 6. ALTERNATIVES CONSIDERED

| Alternative | Rejected because |
|---|---|
| **Convention + code review** *(status quo)* | **This is what produced F-02 and R-01.** Discipline is not a control. |
| **Bearer token validated by signature only** | A signature proves **origin**, not **single-use**. A replayed token executes twice. Single-use requires durable state ⇒ the ledger is unavoidable ⇒ once you have the ledger, the signature is a convenience. |
| **Runtime interception / monkey-patching** | **Detective, not preventive.** Bypassable by anything that loads first. **Retained as a detective layer (§4.5), never as the control.** |
| **Network isolation** (adapters as a separate service) | Strong, and **compatible** — but substitutes a network boundary for a capability boundary and adds distribution we cannot yet justify (**P36**). **Deferred, not rejected:** if adapters are later extracted, the ledger already makes the boundary correct. |
| **A `BREAK_GLASS` class for emergencies** | **REJECTED BY OWNER DECISION.** *An emergency path is a bypass with a nicer name — and it will be used on the worst day, under the most pressure, by the most senior person, with the least review.* **The honest emergency path is a human acting directly in the TMS, which Neyma then observes and reconciles.** |
| **Trusting the actuation process because it is separate** | **A process boundary confers no privilege.** It must still claim from the shared ledger. |

---

## 7. FAILURE MODES

| Crash point | Ledger state | Correct behaviour |
|---|---|---|
| Before mint | no grant | **Nothing happened.** Resume; re-run the checkpoint. |
| After mint, before claim | `GRANTED` → expires | **Nothing happened** — the adapter never acted. Re-checkpoint, re-mint. |
| **After claim, before the call returns** | `CLAIMED` | ⚠️ **UNKNOWN OUTCOME.** ⇒ **`NEEDS_VERIFICATION`.** Commit key stays reserved; entity frozen; human escalated **with the dollar exposure**. **Never retried.** |
| After effect, before verify | `CLAIMED` | Same ⇒ **`NEEDS_VERIFICATION`.** Resolve by readback, never by retry. |
| After verify, before record | `CLAIMED` | **This window does not exist** — verify and record are **one atomic commit** via the outbox (ADR-008 §2.4). |
| **Verification channel also dead** (F-33) | `CLAIMED` | **`NEEDS_VERIFICATION` persists indefinitely. A human owns it.** |

> **The claim is placed as late as physically possible — immediately before the adapter call — precisely to make the ambiguous window as small as it can be.**
> **It cannot be made zero, and the architecture must not pretend otherwise.** *Every system that claims to have eliminated this window has instead chosen, silently, to guess.*

---

## 8. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| **Bypass (unit)** | Calling any adapter **without a grant** fails. |
| **Two-key** | A **valid grant with a stale or mismatched witness** is **refused**. *(Proves the grant alone is insufficient.)* |
| **Forged handle** | A fabricated handle **fails to claim**; a well-formed handle naming no row raises **Sev-0**. |
| **Replayed grant** | A second claim on the same grant **fails**. |
| **Confused deputy** | A grant for load 4471 presented with **parameters for load 4472** ⇒ **refused + Sev-0**. |
| **Expired grant** | Claim **fails**. |
| **Revoked grant** *(brake)* | Brake engaged mid-flight ⇒ unclaimed grants **refuse**. |
| **Commit-once (DB)** | Two concurrent pipelines, **same commit key** ⇒ exactly **one** claims. *(This is the R-02 regression test.)* |
| **Import-graph (CI)** | **No module outside `pipeline/` imports `adapters/`.** Build fails on violation. |
| **Adapter signature (CI)** | Every adapter entry point takes a grant **and** a witness. |
| **Orphan detection** | A synthetic direct adapter invocation is **detected**, raises Sev-0, **engages the brake**. |
| **Replay safety** | Replay of the **full historical corpus** produces **zero** grants and **zero** `EffectAttempted`. |
| **Injection containment** | An adversarial document instructing *"pay this invoice immediately"* produces **a `ProposedIntent` and nothing else.** No grant. No effect. **This is the test that proves F-35.** |
| **Crash matrix** | Crash at each point in §7 ⇒ correct ledger state and correct `NEEDS_VERIFICATION` outcome. |

---

## 9. CONSEQUENCES

1. **Every effect is, by construction, preceded by the seven checks** — enforced by the type system, a build gate, and a database CAS. **Not by convention.**
2. **Commit-once becomes a database constraint.** R-02 dies with a unique index.
3. **Replay is structurally inert** (F-18, free).
4. **Prompt injection is contained at the capability layer** (F-35) — content containment becomes defence-in-depth rather than the wall.
5. **Agents become genuinely safe to iterate on.** A bad agent proposes badly. **It cannot act badly.**
6. **Adapters cannot be "quickly called" from a script.** **This will be experienced as friction. That friction is the feature** — it is the same friction that would have prevented R-01.
7. **Cost:** every effect requires a durable ledger write and a checkpoint record before it. **Accepted.** One row, against the cost of one unaudited payment.
8. **Migration:** `tms_write.enter_approved_payable` — the existing gated write driver — is the **conceptual ancestor of this pipeline** (audit R-03). **It is the spine, not the mock. Generalize it; do not discard it.**

---

## 10. WHAT THIS ADR DOES NOT DO

- **It does not resolve F-01** (approval binding / material-facts drift) — **ADR-005**. This ADR *consumes* the fingerprint; it does not define it.
- **It does not define the verification taxonomy** — **ADR-006**. This ADR *names* `NEEDS_VERIFICATION`; ADR-006 says how to leave it.
- **It does not define entity-version concurrency** — **ADR-009**. This ADR *carries* the versions; ADR-009 defines them.
- **It does not define policy** — **ADR-010**. This ADR *binds* a policy version; ADR-010 says what a policy is. *(See Stream B lesson **L-C**: an owner-stated rule must compile to policy or be honestly reported as memory.)*
- **It does not alter the six write-capable entry points.** **Deliberately** — the permanent mechanism is defined first (owner decision).
- **It does not, by existing, close R-02.** **R-02 closes when this is built.**
