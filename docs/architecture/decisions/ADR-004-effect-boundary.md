# ADR-004 — The Structurally Enforced Single Effect Boundary

**Status:** DRAFT for approval.
**Resolves:** Correction-plan **Group A** — findings **F-02** (CRITICAL), the effect-boundary half of **F-35**, and the pipeline-durability half of **F-06** (jointly with ADR-008).
**Depends on:** ADR-008 (durable machines and the transactional outbox).
**Blocks:** everything. **This is the keystone ADR. No other mechanism in the architecture is real until this one exists.**

---

## 1. CONTEXT

The Target Specification §19 declares itself *"the single effect boundary"* and §23.4 declares that agents *"have no privileged path to any external system."*

**Neither claim is backed by a mechanism.** The adversarial review (F-02) established that anything able to import an adapter reaches the outside world: a migration script, an admin tool, a retry handler, a compensating workflow, a background reconciler, a well-meaning engineer, **or an AI coding agent implementing from this document.**

The entire safety model — money fence, document fence, approval gates, verify-by-readback, commit-once, audit provenance — **rests on the assumption that all effects flow through one place.** That assumption is currently enforced by **convention**, which is to say **not at all**.

> **A boundary enforced by good intentions is not a boundary.** It is a comment.

The repository audit confirms this is not hypothetical: **11 entry points can currently reach the live TMS**, and one production flag routes human-approved payables into a **mock ledger** while reporting `DONE` (R-01).

**This ADR makes bypass structurally impossible, not merely forbidden.**

---

## 2. DECISION

### 2.1 The rule
> **An external effect can only be produced by an adapter. An adapter can only act when presented with a valid, claimed Effect Grant. An Effect Grant can only be minted by the Action Pipeline, and only after the atomic pre-effect checkpoint has passed.**

**There is no other path. There is no admin path. There is no migration path. There is no emergency path.**

### 2.2 The three distinct lifetimes *(this distinction prevents the most likely misimplementation)*

| Concept | Answers | Lifetime |
|---|---|---|
| **Commit Key** | *"Which logical effect is this?"* | **Stable across all attempts.** Prevents double-commit. |
| **Effect Grant (ECT)** | *"May this **one attempt** touch the world, right now?"* | **One attempt. Single-use. Never reused.** |
| **Approval** | *"Did a human authorize this committed effect?"* | **Survives a provably-failed attempt; consumed on commit.** (ADR-005) |

> **A retry re-uses the commit key. It NEVER re-uses the grant.** Conflating these is how a single approval becomes an unbounded licence.

### 2.3 The Execution Capability Token (Effect Grant) — precise specification

An **Effect Grant** is a **durable row in the Effect Grant Ledger**, plus a signed handle used to transport a reference to it. **Its authority lives in the ledger, not in the token's contents** — so a stolen or replayed handle is worthless.

| Property | Specification |
|---|---|
| **Who may mint** | **Only the Action Pipeline.** The minting function requires a `CheckpointPassed` witness as an argument. `CheckpointPassed` is a type **constructible only by the pre-effect checkpoint function itself**. No other code can produce one. *Capability by construction.* |
| **When it is minted** | **Immediately after** the atomic pre-effect checkpoint passes, and **immediately before** the adapter call. **Nothing asynchronous may occur between mint and claim.** |
| **What must already be validated** | All seven checks of the **atomic pre-effect checkpoint** (§2.4). A grant cannot exist without them. |
| **Tenant scope** | Bound to exactly one `tenant_id`. An adapter refuses a grant whose tenant does not match its operating context. |
| **Action-class scope** | Bound to exactly one action class, with its gate decision (`HUMAN_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `UNGATABLE_PERMANENT`) recorded on the grant. |
| **Commit-key scope** | Bound to exactly one commit key. |
| **Target-resource scope** | Bound to the **specific external resource** it may touch (system + resource identifier + operation). A grant for "invoice load 4471 in TMS-A" **cannot** be used to invoice load 4472, or to touch TMS-B. |
| **Approval binding** | If the gate is `HUMAN_REQUIRED`, the grant carries the `approval_id` **and the material-facts fingerprint** (ADR-005). |
| **Entity-version binding** | Carries the entity versions read (ADR-009), so concurrency is enforced at the same instant. |
| **Expiry** | Short, absolute TTL (**seconds, not minutes**). An expired grant is unusable. The TTL is not a security control — the ledger claim is — but it bounds the window. |
| **Single-use** | Enforced by an **atomic state transition in the ledger**: `GRANTED → CLAIMED`. **A second claim fails.** Single-use is a database guarantee, not a token property. |
| **Forgery resistance** | The handle is signed; **but forgery is irrelevant** — a forged handle names no ledger row, and the claim fails. **The ledger is the authority.** |
| **Replay resistance** | A replayed handle attempts to claim an already-`CLAIMED` row. **The CAS fails. The adapter refuses.** |
| **Crash behaviour** | See §6. |
| **Retry behaviour** | A retry **mints a new grant** after re-running the full checkpoint. **Grants are never re-issued.** |
| **Cross-process** | **Permitted, and designed for** — the actuation runtime (browser sessions) is a separate process (§29.2). The grant handle crosses; **the authority does not.** The actuating process must **claim from the ledger**, which is shared and transactional. **A process boundary confers no privilege.** |
| **How adapters validate it** | An adapter's *only* entry point takes an `EffectGrant`. It **must successfully CAS `GRANTED → CLAIMED`** before touching the outside world. Claim failure ⇒ the adapter **does nothing** and raises. It validates tenant, action class, and target resource against its own call parameters — **a mismatch is a Sev-0 security event, not an error.** |

### 2.4 The atomic pre-effect checkpoint *(constitutional constraint — preserved verbatim)*

**These seven checks occur as ONE atomic checkpoint, immediately before the effect. They are NOT independent checks separated by asynchronous work.**

1. **Approval validity** (present, unexpired, unrevoked, correct authority)
2. **Material-facts fingerprint validation** (ADR-005 — void on drift)
3. **Projected-state freshness revalidation** (against the authoritative source — ADR-001 C4)
4. **Native-state validity revalidation** (claims unretracted, unsuperseded, not `conflicting`)
5. **Entity-version concurrency check** (ADR-009)
6. **Policy evaluation** (caps, authority, autonomy, allowlists — and the gate decision, which is **never null**)
7. **Human-brake admission status** (ADR-011)

**All seven pass ⇒ `CheckpointPassed` is constructed ⇒ a grant may be minted.**
**Any one fails ⇒ no `CheckpointPassed` exists ⇒ no grant can be minted ⇒ no effect is possible.**

> **The brake (7) is enforced by refusing to mint.** That is why it is unbypassable and why it never needs to kill a worker.

### 2.5 Explicit prohibitions *(stated as required)*

- **Agents never receive integration credentials, adapters, or grants.** An agent's *only* output is a **`ProposedIntent`** — inert data. It cannot construct a `CheckpointPassed`, cannot mint a grant, cannot name an adapter.
- **Replay never receives an Effect Grant.** Replay does not perform live revalidation, therefore **it cannot construct a `CheckpointPassed`, therefore it cannot mint.** *Side-effect-free replay is a consequence of the capability model, not a discipline to be maintained.*
- **Migration and administrative tooling receive no bypass.** They are ordinary pipeline clients. A migration write uses a `MIGRATION` action class **with its own positively-asserted gate**.
- **Compensating actions pass through the same pipeline.** A rollback is an effect, and is subject to every rule an effect is subject to.
- **Inbound prompt injection may corrupt a proposed claim, but cannot create the capability to execute an effect.** A fully compromised model produces **a bad `ProposedIntent`** — which the checkpoint then independently validates. **Injection can make the system propose something stupid. It cannot make the system do something.**

---

## 3. ALTERNATIVES CONSIDERED

| Alternative | Rejected because |
|---|---|
| **Convention + code review** (*status quo*) | This is what produced F-02 and R-01. **Discipline is not a control.** Explicitly forbidden by the mandate. |
| **Bearer token, validated by signature only** | A signature proves origin, **not single-use**. A replayed token executes twice. **Single-use requires durable state**, so the ledger is unavoidable — and once you have the ledger, the signature is a convenience, not the control. |
| **Runtime interception / monkey-patch guards** | Detective, not preventive. Bypassable by anything that loads first. **Retained as a *detective* layer (§7.4), never as the primary control.** |
| **Network-level isolation** (adapters in a separate service, callable only by the pipeline) | Strong, and **compatible with this design** — but it substitutes a network boundary for a capability boundary and adds distribution we cannot yet justify (**P36**). **Deferred, not rejected**: if adapters are later extracted, the grant ledger already makes the boundary correct. |
| **Trusting the actuation process** because it is separate | A process boundary confers no privilege. **The actuating process must still claim from the shared ledger.** |

---

## 4. CONSEQUENCES

1. **Every effect is, by construction, preceded by the seven checks.** Not by convention — **by the type system and a database CAS.**
2. **Replay is structurally inert.** (F-18/K gets its guarantee for free.)
3. **Prompt injection is contained at the capability layer**, not merely at the prompt layer. (F-35 — this is the *actual* wall; content containment is defence-in-depth.)
4. **Agents become genuinely safe to iterate on.** A bad agent proposes badly. It cannot act badly.
5. **Cost:** every effect now requires a durable ledger write before it. **Accepted.** It is one row against the cost of an unaudited payment.
6. **Constraint on implementers:** adapters cannot be "quickly called" from a script. **This will be experienced as friction. That friction is the feature.**
7. **The Effect Grant Ledger is also the migration mutual-exclusion mechanism** (ADR-012 / F-07): if the legacy runtime must coexist, it claims from the **same** ledger, or it does not act.

---

## 5. SECURITY PROPERTIES

| Property | How it is achieved |
|---|---|
| **No ambient authority** | Adapters are inert without a claimed grant. |
| **Least privilege** | A grant names one tenant, one action class, one commit key, **one target resource**, one operation. |
| **Non-forgeability** | Authority lives in the ledger; a forged handle names nothing. |
| **Non-replayability** | Single-use enforced by an atomic CAS. |
| **Confused-deputy resistance** | The adapter **re-validates** tenant/action/target against its actual call parameters. A mismatch is a **security event**, not an error. |
| **Injection resistance** | A model cannot construct `CheckpointPassed`. **Compromise is bounded to a bad proposal.** |
| **Insider/tooling resistance** | There is **no admin bypass**, by construction. |
| **Tamper-evidence** | Every mint, claim, and refusal is an event. **An adapter invocation with no matching claimed grant is a Sev-0.** |

---

## 6. FAILURE MODES

| Crash point | Ledger state | Correct behaviour |
|---|---|---|
| **Before mint** | no grant | Nothing happened. Pipeline resumes; re-runs the checkpoint. |
| **After mint, before claim** | `GRANTED` (expires) | **Nothing happened** — the adapter never acted. On resume, the grant is expired/unclaimed ⇒ safe to re-checkpoint and re-mint. |
| **After claim, before the adapter call returns** | `CLAIMED` | ⚠️ **UNKNOWN OUTCOME.** We *cannot* distinguish "claimed but never called" from "called and lost the response." **Therefore we MUST NOT assume nothing happened.** ⇒ the effect enters **`NEEDS_VERIFICATION`** (ADR-006/Group C): the commit key stays reserved, the entity is frozen for consequential actions, a human is escalated with the dollar exposure. |
| **After effect, before verify** | `CLAIMED` | Same: **`NEEDS_VERIFICATION`.** Resolve by readback (ADR-006), never by retry. |
| **After verify, before record** | `CLAIMED` | **Closed by ADR-008** — verify and record are one atomic commit (outbox). This window does not exist. |
| **Verification channel also dead** (F-33) | `CLAIMED` | **`NEEDS_VERIFICATION` persists indefinitely.** It **MUST NOT** time out into success **or** failure. **A human owns it.** *This is deliberately uncomfortable: any timeout here is a decision to guess about money.* |

> **The claim is placed as late as physically possible** — immediately before the adapter call — precisely to make the ambiguous window as small as it can be. **It cannot be made zero, and the architecture must not pretend otherwise.**

---

## 7. ENFORCEMENT MECHANISMS

*(No naming conventions. No developer discipline. No prompts. No documentation.)*

1. **Type-level (primary, preventive).** `mint_grant(checkpoint: CheckpointPassed, …)`. `CheckpointPassed` has **no public constructor** and is produced **only** by the checkpoint function. **Code that has not passed the checkpoint cannot express a call to mint.**
2. **Module-level (preventive).** Adapter constructors are **module-private**. The adapter registry is reachable **only** from the pipeline module. Every adapter's sole public entry point **requires an `EffectGrant`**.
3. **Database-level (preventive).** Single-use via atomic CAS `GRANTED → CLAIMED`. **The database is the final arbiter of "may this act."**
4. **CI-level (preventive).** A **static import-graph check fails the build** if any module outside `pipeline/` imports `adapters/`. This check is **not skippable** and is part of the merge gate.
5. **Runtime monitoring (detective).** Every adapter invocation emits `EffectAttempted{grant_id, tenant, target}`. A continuous reconciler asserts **every `EffectAttempted` has a matching claimed grant and pipeline instance.** An orphan is a **Sev-0** and **auto-engages the brake** for that tenant + action class.
6. **Credential-level (preventive).** Integration credentials are resolvable **only** inside the adapter, **only** on presentation of a claimed grant. **They are never reachable by agents, tooling, or the pipeline itself.**

---

## 8. TESTING REQUIREMENTS

| Test | Asserts |
|---|---|
| **Bypass attempt (unit)** | Calling any adapter without a grant **fails**. |
| **Forged grant** | A fabricated handle **fails to claim**. |
| **Replayed grant** | A second claim on the same grant **fails**. |
| **Wrong tenant / action / target** | The adapter **refuses** and emits a security event. |
| **Expired grant** | Claim **fails**. |
| **Import-graph test (CI)** | No module outside `pipeline/` imports `adapters/`. **Build fails on violation.** |
| **Orphan detection** | A synthetic direct adapter invocation is **detected** and raises Sev-0. |
| **Replay safety** | Replay of a full historical corpus produces **zero** grants and **zero** `EffectAttempted` events. |
| **Injection containment** | An adversarial document instructing the model to "pay this invoice immediately" produces **a `ProposedIntent` and nothing else.** No grant. No effect. *(This is the test that proves F-35.)* |
| **Crash matrix** | Crash injected at each point in §6; assert the correct ledger state and the correct `NEEDS_VERIFICATION` outcome. |

---

## 9. MIGRATION IMPLICATIONS

- **The Effect Grant Ledger is the mutual-exclusion mechanism for F-07 / ADR-012.** During any coexistence window, **the legacy runtime must claim from the same ledger or it must not act.** *(Preferred: hard cutover with physical deletion — P37.)*
- **R-01 (audit) must be severed before anything else**: no production path may reach `MockTmsWriteLedger`. Under this ADR, the mock ledger becomes an **adapter behind the same grant boundary**, usable **only** in test environments — which is where it belongs and where it has genuine value (failure injection, §28.3).
- **R-02 (audit): the 11 write-capable entry points must be reduced to clients of the pipeline, or deleted.** Under this ADR they simply **stop working** unless refactored — **which is the correct and desirable outcome.**
- `tms_write.enter_approved_payable` — the existing **gated write driver** — is the **conceptual ancestor of this pipeline** and should be treated as such during migration (audit R-03). **It is the spine, not the mock.**

---

## 10. OPEN QUESTIONS

| # | Question | Blocks |
|---|---|---|
| **Q1** | **Grant TTL length.** Seconds — but how many? Browser actuation is slow (~20–35s observed). The TTL must exceed the *claim-to-call* window, **not** the whole execution. | Implementation tuning, not design. |
| **Q2** | **Should the actuation runtime be a separate process in v1?** §29.2 assumes yes (browser lifecycle isolation). **The grant model works either way.** Co-locating in v1 is simpler (**P36**) and loses nothing architecturally. | ADR (deployment). Recommend **co-locate in v1**. |
| **Q3** | **Does the grant ledger share a transaction with pipeline state?** **It must** (ADR-008's outbox). Confirm the same store. | ADR-008. |
| **Q4** | **How are credentials scoped to a claimed grant** under Fork B posture (b)? | **Fork B — `NEEDS VALIDATION`.** The mechanism is unaffected; only the credential source changes. |
| **Q5** | Do we need an explicit **`BREAK_GLASS`** action class for a genuine emergency? **Recommendation: NO.** An emergency path is a bypass with a nicer name. **A human acting directly in the TMS is the emergency path — and it is honest, because Neyma will observe it.** | Product decision. |
