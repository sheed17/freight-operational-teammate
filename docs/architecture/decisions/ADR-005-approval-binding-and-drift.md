# ADR-005 — Approval Binding & Material-Facts Drift

**Status:** ✅ **FINAL — Wave 2.**
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Resolves:** correction-plan **Group B** — **F-01** (CRITICAL), **F-08**, **F-09**, **F-20**, **F-22**.
**Consumed by:** ADR-004 (checkpoint steps 1–2, approval binding on the grant), ADR-008 §3.4 (the Approval lifecycle).
**Constrained by (frozen):** ADR-002 (§2.3 `provenance_class`), ADR-003 (authorization assertion), ADR-004, ADR-008, Operating Model, Engineering Principles.

---

## 1. CONTEXT

ADR-004 requires the pre-effect checkpoint to validate an **approval** and a **material-facts fingerprint**, and requires the Effect Grant to carry both. **It does not define either.** ADR-008 gives the Approval lifecycle its states but not the rules that drive them.

**This ADR defines the thing the human is actually agreeing to.**

## 2. PROBLEM STATEMENT

**F-01 (CRITICAL):** the architecture revalidated facts **before** the human gate, not **after** it. A human approves *"invoice load 4471 for £2,850"*. The proposal sits in Slack for forty minutes. In that window the TMS rate is corrected to £3,100. The pipeline resumes and executes **against the current TMS value**.

> **The owner approved £2,850. The customer was invoiced £3,100. The audit log records a human approval. Every gate passed.**

The approval was **bound to an action**, not to **the facts that made the action correct**. That is the defect.

Three failure classes follow from it:
1. **Drift** — the world changed between approval and execution (F-01).
2. **Scope creep** — an approval for one effect is reused for another (F-22).
3. **Staleness** — an approval given Friday executes Monday (F-08/F-09).

---

## 3. DECISION

### 3.1 The rule

> ## **A human does not approve an action. A human approves an action *together with the exact facts that made it correct*.**
> ## **If any of those facts change, there is no approval. There is a new question.**

**A previously approved action whose material facts have drifted MUST NOT execute — and the system MUST be able to say exactly which fact changed, from what, to what, and when.**

### 3.2 The Material Fact Set — what the human is agreeing to

**The material fact set is exactly what was rendered to the approver, plus the identity of the effect.** *If it was on the card, it is material. If it was material, it must have been on the card.* **Anything the human could not see cannot be a fact they approved.**

| # | Field | Why material |
|---|---|---|
| 1 | `tenant_id` | An approval never crosses a tenant. |
| 2 | `action_class` | *Invoice* is not *credit*. |
| 3 | `target_system` · `target_resource_id` · `target_operation` | *Load 4471 in TMS-A.* Prevents scope creep (**F-22**). |
| 4 | `commit_key` | The logical effect being authorized (ADR-009 §4). |
| 5 | **`amount_minor` + `currency`** | **The money. Integer minor units. Never a float.** |
| 6 | `counterparty_identity` | *Who gets paid / who gets billed.* An approval to pay **Carrier A** is not an approval to pay **Carrier B** at the same amount. |
| 7 | `entity_reference` | The load / invoice / order. |
| 8 | `bound_document_ids` + their content digests | **The document fence.** The POD the human saw is the POD that gets filed. |
| 9 | **`evidence_condition` of every material field** | `consistent` · `stale` · `unknown` · `absent` · `conflicting` (ADR-002 C5). **Approving on `consistent` evidence is a different decision from approving on `stale` evidence.** |
| 10 | **`provenance_class` of every material field** | ADR-002 §2.3. **See §3.3 — this is the non-obvious one.** |
| 11 | `policy_version` | §3.11. |
| 12 | `entity_versions` | The versions read (ADR-009). |
| 13 | `fingerprint_version` | §3.6. |

**Explicitly NOT material** *(they may change freely without voiding an approval)*: cosmetic rendering, message text, thread ids, the approver's timezone, unrelated fields on the same entity, and **confidence scores** *(a confidence score is not a fact — ADR-007 §5)*.

### 3.3 Provenance is material — and this is the subtle one

> **The same number, believed for a different reason, is a different fact.**

An owner approving *"£2,850 — read from the TMS invoice screen"* (`SYSTEM_IMPORTED`) has made a different decision from an owner approving *"£2,850 — extracted from the rate confirmation PDF"* (`MODEL_EXTRACTED`), and **neither** would have approved *"£2,850 — the model's best guess"* (`MODEL_INFERRED`, which **may never gate a consequential action at all** — ADR-002 §2.3).

**Therefore `provenance_class` is inside the fingerprint.** If the amount is still £2,850 but its provenance has changed, **the basis of the decision has changed, and the approval is void.**

*(This closes a laundering route the fingerprint would otherwise have left open: swap the evidence, keep the number, keep the approval.)*

### 3.4 Canonical serialization — `fp_v1`

**Two systems computing the fingerprint of the same facts must produce the same bytes. Byte-for-byte determinism is the whole mechanism; anything ambiguous here is a silent bypass.**

| Rule | Specification |
|---|---|
| **Encoding** | UTF-8, **Unicode NFC normalized**. |
| **Structure** | A flat, sorted list of `key=value` pairs. **Keys sorted bytewise.** No nested objects; nesting is flattened with `.` separators. |
| **Money** | **Integer minor units + ISO-4217 code.** `285000|GBP`. ### **Floats are FORBIDDEN in the fingerprint.** *(`2850.00` and `2850.0` are the same money and different bytes. That is a defect waiting to be a double-payment.)* |
| **Timestamps** | RFC-3339, **UTC**, **exactly** millisecond precision, `Z` suffix. No local time, ever. |
| **Null vs absent** | **Distinct and both explicit.** `field=<null>` ≠ field omitted. *(ADR-002 C5: `absent` and `unknown` are different conditions; the serialization must not collapse them.)* |
| **Booleans / enums** | Lowercase literals. Enum values by **name**, never by ordinal. |
| **Collections** | Sorted bytewise. Documents as `id:digest` pairs. |
| **Strings** | **Raw. No trimming, no case-folding, no locale collation.** *(A counterparty name that differs only in case is a different counterparty until a human says otherwise.)* |
| **Envelope** | The payload is prefixed with `fp_v1\n` — **the version is inside the hashed bytes**, so a version confusion cannot produce a colliding hash. |

### 3.5 Hashing — and why the hash is **not enough**

`fingerprint = SHA-256(canonical_bytes)`.

> ### **We store the full canonical payload, not just the hash.**

**A hash can prove that something drifted. It can never say what.** And this ADR's requirement is that *"the system must explain exactly why the approval became invalid."* **You cannot diff a hash.** So:

- `approvals.fingerprint` — SHA-256, used for the **fast equality check** at the checkpoint.
- `approvals.canonical_payload` — the full `fp_v1` bytes, retained permanently, used for the **field-level diff** that produces the human explanation (§3.13).

*This is a deliberate storage cost, accepted. The alternative is a system that can say "something changed" to an owner asking which number moved.*

### 3.6 Fingerprint versioning

Each approval stores `fingerprint_version`. **An algorithm change does NOT invalidate live approvals**: drift is checked by recomputing under **the version stored on the approval**, exactly as ADR-008 §2.8 upcasts historical events.

> **A refactor of the hashing code must never silently void every outstanding approval — nor silently validate one it should have voided.** Both are achieved by pinning the version to the approval, not to the code.

### 3.7 Approval scope

**One approval authorizes exactly one commit key, exactly once.**

- **Scope is the fingerprint.** Nothing outside the fingerprint is authorized.
- **A batch — `[Approve all 7]` — mints SEVEN approvals**, each with its own fingerprint, in one transaction. **It is not one approval covering seven effects.** *(If load 3 has drifted, loads 1, 2, 4–7 still execute; load 3 comes back as a new question. One bad load does not void the batch, and — critically — one tap does not silently authorize a fact the owner never saw.)*

### 3.8 Partial approvals — **they do not exist**

> **An approval is all-or-nothing over its material fact set.**

*"Approve it, but for £2,700"* is **not a partial approval.** It is a **new proposal, with a new fingerprint, requiring a new approval.**

**Why not:** a partial approval is an approval over a fact set the system constructed **after** the human looked. The human would be agreeing to a set of facts **that was never rendered to them** — which is exactly the defect this ADR exists to kill. *(Rejected alternative, §5.)*

### 3.9 Expiry

**Absolute TTL, set per action class, at request time.** Money-out is shortest.

| Class | Default TTL | Rationale |
|---|---|---|
| Money-out (payables, payments) | **1 hour** | Balances go stale; duplicate-payment risk is highest. |
| Money-in (customer invoicing) | **8 hours** | Lower blast radius; matches an owner's working day. |
| Document filing, status writes | **24 hours** | Low consequence, high convenience. |

**Expiry is a durable timer emitting `TimerFired`** (ADR-008 §2.3) — **never a background sweep**, never an inference from staleness.

> **An approval that has expired is not a weaker approval. It is not an approval.**

### 3.10 Supersession — **expressed by existing mechanisms; no new state**

**There is no `SUPERSEDED` approval state.** *(Wave 2 is completion, not expansion.)* Supersession decomposes exactly into two mechanisms that already exist:

| Case | What actually happens |
|---|---|
| A new proposal for the same commit key, **with different facts** | The facts differ ⇒ **the old approval is `VOID_ON_DRIFT`** (§3.12). The new proposal raises a new approval. **That *is* supersession.** |
| A new proposal for the same commit key, **with identical facts** | It is not a new proposal — it is a **duplicate**, and it is refused at PROPOSED by the **commit-key reservation** (ADR-009 §3). |

**Every supersession is either a drift-void or a duplicate. There is no third case, so there is no third state.**

### 3.11 Policy-version interaction

`policy_version` is **a material fact** (§3.2 #11) and is carried on the Effect Grant (ADR-004 §3.2).

> **A policy change voids in-flight approvals granted under the old policy.**

**You cannot act under a policy that no longer exists.** If the owner tightens the cap from £5,000 to £2,000 while a £3,000 payable sits awaiting approval, that payable **does not execute** — the approval is `VOID_ON_DRIFT` with the reason *"the policy changed."* *(A policy change that does not bind in-flight work is a policy change that does not mean anything.)*

### 3.12 Drift detection — the mechanism

**At checkpoint step 2 (ADR-004 §2.4), inside the atomic checkpoint:**

1. **Re-read every material fact from its authoritative source, LIVE.** **Never from a cache, never from the projection** (ADR-001 **C4**; this is a `CONSEQUENTIAL_FRESHNESS_READ` and it is structurally forbidden a cache).
2. Recompute the canonical payload under the approval's **stored** `fingerprint_version`.
3. **Compare hashes.** Equal ⇒ **no drift** ⇒ the checkpoint proceeds.
4. **Unequal ⇒ diff the canonical payloads field-by-field** ⇒ transition the Approval `GRANTED → VOID_ON_DRIFT`, emit `ApprovalVoided{drift_diff}`, transition the Pipeline `CHECKPOINT → VOIDED`. **No grant is minted. No effect occurs.**

**A re-read that FAILS is not "no drift."** An unavailable authoritative source ⇒ the checkpoint **fails closed** (`unknown ≠ consistent`, ADR-002 C5/C6). **We do not execute money against a source we could not read.**

### 3.13 The explanation — a required output, not a log line

**A drift-void MUST produce a human-readable explanation naming every changed field, its old and new value, and the provenance of each.**

> *"I did not invoice load 4471.*
> *When you approved it 41 minutes ago, the amount was **£2,850** (read from the TMS invoice screen at 09:14).*
> *It is now **£3,100** (same source, read just now).*
> *Nothing has been sent. Do you want me to invoice £3,100?"*

**This is generated from the canonical-payload diff (§3.5) — which is why the payload is retained and the hash alone is not.**

> **A system that blocks an action it cannot explain has merely relocated the owner's problem.** I3 (*explainable to an angry person*) applies to refusals, not only to actions.

### 3.14 Re-approval triggers

| Trigger | Result |
|---|---|
| Any material fact changed | `VOID_ON_DRIFT` + a **new proposal** carrying the diff |
| Policy version changed | `VOID_ON_DRIFT` (§3.11) |
| `provenance_class` of a material field changed | `VOID_ON_DRIFT` (§3.3) |
| Evidence condition degraded (`consistent → stale/unknown/conflicting`) | `VOID_ON_DRIFT` — **fail closed** |
| Approval TTL elapsed | `EXPIRED` |
| Brake engaged | `VOID_ON_BRAKE` |
| Human revoked | `REVOKED` |
| An open **Conflict** appears on a material field | `VOID_ON_DRIFT` — a `conflicting` field **blocks** (ADR-002 C6) |

**A re-approval is always a NEW approval with a NEW fingerprint.** **An approval is never "refreshed", "extended", or "re-validated in place."**

### 3.15 Replay protection

**Two layers, because the transport and the authority are different things.**

1. **Transport (Slack):** the button carries a **single-use HMAC token** bound to `(approval_id, channel, thread, user)`. A replayed HTTP callback fails the token check.
2. **Authority (the database):** the Approval transitions `GRANTED → CONSUMED` by an **atomic CAS**, in **the same transaction** that claims the Effect Grant (ADR-004 §3.5, ADR-008 §2.5).

> **A double-tap on the Slack button is not an error. It is idempotent.** The second tap finds `CONSUMED` and replies *"already done — invoice 560010, sent at 09:52."* **It does not raise, and it does not act.** *(An owner tapping twice because Slack was slow must never be punished with an error, and must never be rewarded with a second invoice.)*

### 3.16 Multi-step approvals (dual control)

For action classes requiring **N distinct authorized humans** (e.g. money-out above a cap):

- The Approval collects **`ApprovalSignature`** records: `(approval_id, actor_id, signed_fingerprint, signed_at)`.
- `REQUESTED → GRANTED` only when **quorum is met** by **distinct, authenticated** actors.
- ### **Every signature binds the SAME fingerprint.**
- ### **If a material fact drifts between signature 1 and signature 2, ALL signatures are void.** The approval returns to `REQUESTED` with a fresh fingerprint and **every human must sign again.**

> **A second approver who is shown different facts from the first approver is not a control. It is two people approving two different things and believing they agreed.**

`ApprovalSignature` is **not a new lifecycle** — it is an evidence record attached to the existing Approval machine (ADR-008 §3.4). *(No new primitive.)*

### 3.17 Audit history

Retained **permanently**, per approval: the full canonical payload, the fingerprint, `fingerprint_version`, `policy_version`, every signature with actor and timestamp, what was **rendered** to the human, every void/expiry/revocation **with its diff and reason**, the consuming pipeline instance and grant, and the final effect.

> **You must be able to reconstruct, years later, exactly what the human saw when they said yes.** That is the entire evidentiary point of an approval.

---

## 4. WHAT AN APPROVAL IS NOT *(ADR-003 — permanent, cannot graduate away)*

An approval is created **only** by an **authenticated, authorized human inside Neyma's trust boundary** (`OWNER_ASSERTED`, ADR-002 §2.3).

**It can NEVER be created by:** a model · a counterparty · inbound content · a document · a confidence score · a policy default · a retry handler · an agent · an admin tool.

> **A counterparty email saying *"per our call, you approved this detention"* is `MODEL_EXTRACTED` at best.** It is an **unverified counterparty claim and a fraud signal** — **not an approval**, and **no evidence can promote it** (ADR-002 R-P2).

---

## 5. ALTERNATIVES REJECTED

| Alternative | Rejected because |
|---|---|
| **Bind the approval to the action id only** *(status quo, F-01)* | **This is the defect.** It authorizes *"invoice load 4471"* — an instruction whose meaning changes when the world does. |
| **Re-read facts and proceed if "close enough"** (tolerance band) | **A tolerance is a licence to be wrong by a bounded amount, chosen by an engineer, applied to someone else's money.** There is no principled £ value. **Any drift voids.** |
| **Hash only, no canonical payload** | Cheaper — and it makes §3.13 impossible. **A system that can only say "something changed" has relocated the owner's problem, not solved it.** |
| **Partial approvals** | The human would be agreeing to a fact set **assembled after they looked**. That is F-01 wearing a friendlier interface. |
| **Approvals that never expire** | An approval is a statement about a moment. **A Friday approval executing on Monday is not consent; it is an assumption.** |
| **A `SUPERSEDED` approval state** | **Unnecessary** — supersession is exactly drift-void ∪ duplicate-refusal (§3.10). *Wave 2 is completion, not expansion.* |
| **Re-validate before the human gate** (the original spec) | Revalidating *before* the human decides answers the wrong question. **The window that matters is the one after they tap.** |

---

## 6. CONSEQUENCES

1. **F-01 is closed.** Drift cannot execute — **structurally**, at checkpoint step 2, inside the atomic checkpoint.
2. **F-22 (scope creep) is closed.** The target resource is inside the fingerprint.
3. **Owners will see re-approval prompts they did not see before.** **This is correct and must not be tuned away.** Each one is an occasion on which the old system would have silently acted on a fact the owner never agreed to.
4. **Cost:** a live re-read of every material fact before every effect. Slower. **Accepted** — it is the difference between an approval and a guess.
5. **A policy change now has teeth** (§3.11).
6. **Storage:** every approval retains its full canonical payload forever. **Accepted** — it is the evidence.

---

## 7. FAILURE MODES

| Failure | Behaviour |
|---|---|
| Authoritative source unreadable at checkpoint | **Fail closed.** No grant. `unknown ≠ no drift`. |
| Crash between `GRANTED` and consumption | Approval survives (ADR-008 §3.4). Recovery **re-runs the checkpoint** — including drift. |
| Crash after `CONSUMED`, before the effect is confirmed | **`NEEDS_VERIFICATION`** (ADR-004 §3.9). **The approval is NOT returned to `GRANTED`, and it is NOT reusable.** *An approval consumed by an attempt of unknown outcome is spent; only a human may establish reality.* |
| Two humans approve the same proposal simultaneously | **CAS.** One `CONSUMED`; the other is told *"already approved by <name>."* **Not an error.** |
| Fingerprint algorithm bug ships | Live approvals are unaffected (**pinned version**, §3.6). |
| Clock skew across processes | Timestamps in the fingerprint come from **the authoritative source's** observation record, not local wall time. TTLs use the **DB clock**, single-sourced. |
| Non-determinism in serialization (map order, float, locale) | ### **The single most dangerous bug class in this ADR** — it produces **false drift** (annoying) or **false no-drift** (**a wrong payment**). Killed by §3.4 + the property tests in §10. |

---

## 8. SECURITY CONSIDERATIONS

- **Fingerprint fields are runtime-supplied** (ADR-002 **R-P1**). **A model never contributes a value to the fingerprint** — it may only *propose* an intent, which the runtime then independently resolves from authoritative sources.
- **Injection cannot forge an approval.** A compromised model produces a bad `ProposedIntent`; the fingerprint is computed from **the runtime's own reads**, and the human still sees the real facts.
- **The approval token is single-use and actor-bound.** A replayed callback fails at the token *and* at the CAS.
- **Provenance is inside the fingerprint** (§3.3), closing the *swap-the-evidence-keep-the-number* laundering route.
- **Dual-control cannot be split across differing facts** (§3.16).
- **Denial-of-service via induced drift:** a hostile or flapping source could void approvals repeatedly. **This is safe-but-annoying**, and it is the correct trade: **a system that stops asking is a system that starts guessing.** Repeated drift on one entity raises an **Exception** (a flapping authoritative source is a real operational problem, and it gets a human).

---

## 9. OPERATIONAL CONSIDERATIONS

- **Drift-void rate is a first-class metric.** A rising rate means either the world is moving faster than the owner is tapping, or a source is flapping. **Both are things an operator must see.**
- **Time-to-approve** is a product metric: the longer a card sits, the likelier the drift.
- TTLs (§3.9) are **operator-tunable per action class** — but **not to infinity**, and never below the observed p99 read latency of the authoritative source.
- **Every drift-void must be explainable in one Slack message** (§3.13). If it cannot be, the fact set is too large — that is a design smell, not a UX problem.

---

## 10. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| ### **The F-01 test** | Approve £2,850 → mutate the TMS to £3,100 → resume. **Assert: NO effect, `VOID_ON_DRIFT`, and the explanation names amount, £2,850 → £3,100.** *This is the test the whole ADR exists for.* |
| **Canonical determinism (property test)** | 10⁵ randomized fact sets; serialize twice in different process/locale/map-order/JSON-lib conditions ⇒ **identical bytes**. |
| **Money never floats** | Any float reaching the serializer ⇒ **hard error**, not a coercion. |
| **`null` ≠ absent** | Two fact sets differing only in null-vs-absent ⇒ **different fingerprints**. |
| **Provenance drift** | Same amount, `provenance_class` changed ⇒ **`VOID_ON_DRIFT`**. |
| **Evidence degradation** | `consistent → stale` on a material field ⇒ **`VOID_ON_DRIFT`**. |
| **Policy drift** | Cap tightened while awaiting approval ⇒ **`VOID_ON_DRIFT`**, reason = policy. |
| **Scope creep (F-22)** | An approval for load 4471 presented for load 4472 ⇒ **refused** (and, at the adapter, **Sev-0** — ADR-004 §3.7). |
| **Double-tap idempotency** | Two Slack callbacks ⇒ **one** effect, second replies *"already done"*, **no error raised**. |
| **Unreadable source** | Authoritative source down at checkpoint ⇒ **fail closed, no grant.** |
| **Dual control drift** | Facts drift between signature 1 and 2 ⇒ **both signatures void**, both humans re-asked. |
| **Version pinning** | Change the fingerprint algorithm ⇒ **live approvals still validate** under their stored version. |
| **Consumed-then-unknown** | Crash after consumption ⇒ approval is **NOT** reusable; effect is `NEEDS_VERIFICATION`. |

---

## 11. MIGRATION CONSIDERATIONS

- **Today there is no fingerprint.** `operation_router` binds an approved amount into the write (the money fence) — which is **the right instinct and the ancestor of this mechanism** — but it does **not** revalidate the *other* material facts, and it does not detect drift in them.
- ⚠️ **Live finding (baseline `f0e801b`):** `_commit_identity` includes **`approved_amount`** (`operation_router.py:335`). **See ADR-009 §4 — this is a live double-billing hole**, and it interacts with this ADR: two approvals at two different amounts for the same load are, today, **two different commit keys**, and **both can commit**.
- The existing **single-use HMAC Slack token** already implements §3.15 layer 1. **Keep it.** Layer 2 (the DB CAS) is new.
- **No historical approvals need migrating.** Approvals are short-lived by construction; a cutover simply lets outstanding ones expire.

---

## 12. OPEN QUESTIONS

| # | Question | Status |
|---|---|---|
| **Q1** | The **TTL values** in §3.9 (1 h / 8 h / 24 h). | **`NEEDS VALIDATION` — customer.** *Ask a broker how long a rate is good for. That is the real number.* |
| **Q2** | **Which action classes require dual control**, and at what threshold. | **`NEEDS VALIDATION` — customer/policy.** Mechanism (§3.16) is complete and does not depend on the answer. |
| **Q3** | Should an owner be able to **pre-authorize** drift within a band for low-value classes (*"re-bill up to ±£25 without re-asking"*)? | **DEFERRED to ADR-010 (policy).** ⚠️ **Recommendation: NO for money-out.** It is a tolerance band by another name (§5). If it is ever allowed, it must be an **explicit, versioned policy**, per action class, with a cap — **never a default, and never a code constant.** |
