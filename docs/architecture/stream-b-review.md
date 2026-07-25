# Stream B Review — Four Independent Changesets

**Subject:** the pre-reset readiness-hardening work preserved on `preserve/pre-reset-readiness-hardening` (`9bf31d0`).
**Provenance:** **UNKNOWN.** Written Jul 8, 15:49–16:23, in a single 34-minute burst.
**Standing:** **NOT approved for the baseline.** Reviewed as four independent promotion candidates.
**Date:** 2026-07-13

> **Rule applied throughout:** *"Do not promote any Stream B change merely because tests pass."*
> **Every one of B1–B4 has passing tests. Two of them are broken anyway.** That is the point of this review.

---

## HEADLINE

> ## **B3 and B4 are mutually destructive. Together they silently overwrite a human decision with a machine inference — every intake cycle.**
>
> They were written **11 minutes apart, in the same burst, by the same author.** Neither test suite
> exercises the other's code path, so both pass. **This is the exact failure ADR-002 exists to prevent,
> already present in the tree.**

| | Changeset | Consequential? | Verdict |
|---|---|---|---|
| **B1** | IMAP retry | No | **PROMOTE_AFTER_FIXES** |
| **B2** | TMS read cache | **Not today — one line away** | **PROMOTE_AFTER_FIXES** *(guard first)* |
| **B3** | Mailbox routing refresh | **YES** | 🔴 **REDESIGN** |
| **B4** | Ops-control assign-unlinked | **YES** | 🔴 **PROMOTE_AFTER_FIXES** *(blocked on B3)* |

---

## B1 — IMAP retry behavior · `imap_mailbox.py` (+57)

**Problem it appears to solve.** A transient IMAP failure (dropped socket, Gmail throttle, timeout) aborted an entire mailbox pull, so a cycle silently fetched nothing.

**Before → after.** `pull_imap_messages` was a single attempt. It is now a retry wrapper (`max_attempts=3`, `retry_sleep_seconds=2.0`) around an extracted `_pull_imap_messages_once`, retrying on `_TRANSIENT_IMAP_ERRORS`, then raising `RuntimeError` with the last error.

**Safety implications — the good news, established by reading, not assuming:**
* The `.eml` write is **content-addressed** (`_filename_for_message` → `{digest}_{subject}.eml`) and guarded by `if path.exists(): continue`. **A retry cannot duplicate a message.** Retry is idempotent with respect to the inbox directory. This is genuinely correct and non-obvious — credit to the author.
* `BODY.PEEK[]` means a retry does not consume the `UNSEEN` flag.
* Bounded: 3 attempts, fixed 2 s sleep. No unbounded loop.

**Correctness risk — the defect:**

> **`imaplib.IMAP4.error` is in the "transient" set. It is not transient.** It is the **base class** for IMAP protocol and **authentication** errors — bad credentials, a bad mailbox name, a malformed command.

**Failure mode:** `.env` has a stale `NEYMA_IMAP_PASSWORD`. Neyma now retries the failed login **3× every cycle, forever**, instead of failing loudly once. Against Gmail this invites rate-limiting or a security block, and it converts *a clear, fixable misconfiguration* into *an intermittent-looking transient* — the most expensive kind of bug to diagnose. It also violates **fail-closed-and-say-so**: a permanent error must be reported as permanent.

*(Minor: `socket.error` **is** `OSError` in Python 3 — a redundant alias, harmless.)*

**Tests present:** `test_imap_mailbox.py` (new) — covers the retry-then-succeed path.
**Tests missing:** an **authentication failure must not be retried**. No test asserts that. No test asserts idempotency across a retry (the property that actually makes this safe).

**Changes consequential behavior:** ❌ No — read-only ingestion.

### **Verdict: PROMOTE_AFTER_FIXES**
1. Narrow `_TRANSIENT_IMAP_ERRORS` to genuinely transient failures (`IMAP4.abort`, `OSError`, `TimeoutError`). **Exclude `IMAP4.error`**, or explicitly exclude authentication failures from retry.
2. Add the two missing tests — especially **"an auth failure raises immediately."**

---

## B2 — TMS read cache · `tms_read_cache.py` (new) + two cached readers

**Full analysis: `docs/architecture/tms-read-cache-safety-review.md`.** Summary here.

**Problem it appears to solve.** Slack slash commands have a hard ~3 s response window; an authenticated TMS page can be slow or locked by a concurrent write. Without a fallback the owner gets a timeout — or worse, a blank page read as "nothing owed."

**Before → after.** New `TmsReadCache` (JSON, 300 s TTL, atomic `tmp`+`replace` write). `_build_receivables_reader` and `_build_tms_brief_reader` gain an optional `cache_path`; on **browser-busy / table-absent / exception** they serve the last verified snapshot.

**Safety implications — the good news:**
* **It is a failure-fallback, not a read-through cache.** The live read is always attempted first.
* **`allow_stale=False` at every call site.** Past the TTL it returns `None` — an honest *"couldn't read"* — rather than a stale value. **It does not manufacture a false all-clear.** `unknown ≠ absent` (I7/I8) is correctly preserved. The author understood the hazard and said so in the docstring.
* `put()` is atomic.

**Correctness risks:**
* **V-1 (MEDIUM)** — `DECISION_SUPPORT_READ` must *disclose staleness*. The reader returns `cached.value` and **discards `age_seconds` and `stale`**. The owner sees the aged-AR digest with **no indication** it came from a cache. Mitigating: the TTL is 300 s and AR aging is day-granular — so the practical error is usually nil. **The mitigation is luck, not design.**
* **V-2 (LOW–MED)** — `INFORMATIONAL_READ` must carry a visible `as_of`. The brief renders no timestamp.
* **`put()` is read-modify-write on the whole JSON dict with no cross-process lock.** The callback server and the teammate loop can both write; a concurrent `put` of a *different* key can be lost (last-writer-wins). Cache-only impact, but real.

### **V-3 — the latent footgun · HIGH.** *(the reason this review matters)*

> **`_build_load_amount_resolver` — the reader that supplies the AMOUNT bound into a money action — has no `cache_path`, and sits directly between two siblings that do, with an identical signature shape.**
>
> **Adding `cache_path=…` to it is a one-line change.** It is visually consistent. It looks like a symmetry fix. It would be **invisible in review**. And it would immediately begin feeding **cached, possibly-stale amounts into the money fence** — a direct **ADR-001 C4** violation.

**The cache is not unsafe. It is one plausible line away from being unsafe, and nothing in the code says so.** *This is exactly the defect that gets introduced by someone being helpful.*

**Tests present:** cached-reader-when-browser-busy. **Tests missing:** stale-past-TTL returns `None`; staleness is disclosed; **and nothing structurally prevents V-3.**

**Changes consequential behavior:** **Not today.** No cached value can currently reach a financial action.

### **Verdict: PROMOTE_AFTER_FIXES — but land the V-3 guard FIRST, independently.**
The guard is shipped in this baseline commit ahead of B2 (see §"Consequential Read Boundary"). **The tripwire must exist before the mine.**

---

## B3 — Mailbox routing refresh · `mailbox_intake.py` (+90) 🔴

**Problem it appears to solve.** Stated plainly, and correctly, in the author's own docstring:

> *"Durable mailbox state should not fossilize stale linker decisions. During a pilot, the load source-of-truth and linker logic can improve; preserved emails must then be re-routed before packet assembly so obvious freight work does not stay stuck as UNLINKED."*

**This instinct is right.** A projection *should* be rebuilt when the deriving logic improves. That is **exactly** ADR-002's model of projected state.

**Before → after.** Every intake cycle, `_refresh_existing_message_routing` re-parses **every** preserved `.eml` and recomputes its routing:

```python
routing = _routing_for_parsed_message(parsed, index)
record.hinted_load_id  = routing["hinted_load_id"]     # unconditional overwrite
record.linked_load_ids = routing["linked_load_ids"]    # unconditional overwrite
if record.triage_route == ROUTE_PROCESS and record.packet_load_id and not routing["packet_load_id"]:
    continue                                            # partial guard
record.packet_load_id  = routing["packet_load_id"]     # overwrite
```

### The defect — **an inference overwriting native state**

**ADR-002 is explicit: projected state is derived and rebuildable; Neyma-native state (bindings, human decisions) is authoritative and must never be overwritten by an inference.** *"An inference is native state and must never masquerade as projected truth."*

**A routing decision made by the linker is projected state.** ✅ Rebuilding it is correct.
**A routing decision made by the owner is a binding — Neyma-native state.** ❌ **Rebuilding it destroys it.**

**B3 cannot tell the two apart. It rebuilds both.**

**And B4 — written 11 minutes later — creates human bindings in exactly these three fields:**

```python
record["hinted_load_id"]  = load_id      # ← B3 overwrites UNCONDITIONALLY
record["linked_load_ids"] = [load_id]    # ← B3 overwrites UNCONDITIONALLY
record["packet_load_id"]  = load_id      # ← B3 overwrites (see branches below)
```

**Branch analysis. There is no branch in which the owner's assignment fully survives:**

| Record state after the owner runs `assign unlinked 2 to LD-4471` | Next intake cycle |
|---|---|
| `triage_route != ROUTE_PROCESS` *(the normal case — it was **unlinked**, which is **why** the owner had to assign it, and **B4 does not set `triage_route`**)* | Guard's first clause is **False** → `continue` never fires → **`packet_load_id` overwritten by the linker (typically back to empty). The assignment is silently reverted.** |
| `ROUTE_PROCESS` + linker finds **nothing** | `packet_load_id` survives — but `hinted_load_id` and `linked_load_ids` are **still clobbered**. **State is now internally inconsistent.** |
| `ROUTE_PROCESS` + linker finds a **different** load | **The owner's binding is overwritten by the machine's guess.** |

**Failure scenario, concretely.** A rate confirmation arrives with the load number only inside a PDF the extractor can't read. Neyma buckets it `UNLINKED`. The owner sees it, and types `assign unlinked 2 to LD-4471`. Neyma replies confirming it, **and writes an audit event**. Ninety seconds later the intake loop runs, re-parses the same `.eml`, finds no load reference, and **puts the message back in `UNLINKED`.** The owner's correction is gone. The audit log says they made it. **Nothing says it was undone.**

> **The owner corrects the machine. The machine un-corrects itself, silently, and the audit trail still claims the correction stands.** That is worse than the feature not existing — the owner *stops re-checking* work they believe they already fixed.

**Tests present:** `test_mailbox_intake_refreshes_stale_preserved_routing` — asserts the refresh **does** overwrite. It **encodes the defect as the expected behavior.**
**Tests missing:** *the interaction with B4.* **No test in either suite touches the other's code path.** That is why both are green.

**Changes consequential behavior:** ✅ **YES** — it determines which load a document is attached to, which is a precondition for billing.

### **Verdict: 🔴 REDESIGN**
Not `PROMOTE_AFTER_FIXES`: the bug is not a missing guard, it is **a missing distinction**. The record has no field expressing *who decided this*, so no guard can be written. The redesign:
1. **Provenance on the routing decision** — `routing_source: LINKER | OWNER`, plus `decided_at` and `decided_by` (ADR-001 field-level provenance; ADR-002 native vs projected).
2. **The refresh rebuilds only `LINKER`-sourced routing.** An `OWNER` binding is native state — **never** recomputed.
3. **If the linker later disagrees with an owner binding, that is a `conflicting` observation** — surface it to the owner as an exception. **Never silently resolve it.** (Operating Model I8: *missing evidence and contradictory evidence are different states.*)

---

## B4 — Ops-control assign-unlinked · `ops_control.py` (+107) 🔴

**Problem it appears to solve.** Real, and worth solving: the owner could see `UNLINKED` mail but had no way to **act** on it, and no way to ask *"what needs me?"* or *"why did you do that?"*. Adds: `assign unlinked N to <LOAD>`, `show unresolved`, `what did we invoice today?`, `why did you do that?` (audit), and a `never bill without POD` SOP.

**Safety implications:**

**1. It is destroyed by B3.** See above. **As it stands, `assign unlinked` does not durably work.** It writes state, audits it, tells the owner it worked — and the next intake cycle reverts it.

**2. Ordinal binding into a mutable list · MEDIUM.**
`^assign\s+unlinked\s+(\d+)\s+to\s+([A-Za-z]{2,4}-?\d{1,6})$` — **`N` is a positional index into a list the owner was shown earlier.** The unlinked list is re-derived every cycle. **If new mail arrives between the render and the command, `unlinked 2` is now a *different email*.** The owner binds a document to a load they never looked at. **A human decision must be bound to a stable identity (the message-id), not to a screen position.** *(This is the same class of error as the money fence: the identity that gets acted on must be the identity the human approved.)*

**3. The SOP is a suggestion wearing a rule's clothing · MEDIUM.**
`never bill without POD` → `knowledge.learn(..., kind=PROCEDURE)`. Procedures are consumed at `operator_agent.py:188` via `recall_procedures(...)` and **appended to the model's prompt**. Neyma replies:

> `:clipboard: Noted the procedure for raise_invoice: Never bill without POD/BOL proof.`

**The owner reads that as "I have installed a rule." What was installed is a sentence in an LLM prompt.**

The *actual* POD gate is the **code-level document fence** (Stream A, propose-time) — that one is real. So this is **not currently unsafe**. But it is a **false-assurance surface**: it invites the owner to trust an advisory string as a control, and if the code fence were ever removed the owner would still believe the rule was in force. **A control the owner believes in must be enforced in code, or it must not claim to be a control.**

**Tests present:** +93 lines — assign-unlinked writes state and audits; unresolved shows run-ids; retry-without-operation does not guess (**good**); why-question routes to audit.
**Tests missing:** the B3 interaction; ordinal-shift mis-binding; that the SOP actually gates anything.

**Changes consequential behavior:** ✅ **YES** — an assignment decides which load a document belongs to.

### **Verdict: 🔴 PROMOTE_AFTER_FIXES — blocked on B3**
1. **Ship only after B3's provenance redesign**, and mark the binding `routing_source = OWNER`.
2. **Bind by message-id, not ordinal.** Render a stable short handle; accept that handle.
3. **Fix the SOP reply to say what actually happened** — *"I'll keep this in mind"* is honest; *"Noted the procedure"* implies enforcement. Better still: make `never bill without POD` compile to the **real** document-fence policy, and only then claim it as a rule.
4. `show unresolved` / `why did you do that?` / `what did we invoice today?` are **read-only and independently promotable now.** They can be cherry-picked ahead of the rest.

---

## THE CONSEQUENTIAL READ BOUNDARY (V-3) — proposal

**Requirement:** *"The money-sensitive resolver must be structurally unable to accept a cache source. Do not rely only on comments."*

**Three reader classes, distinguished by their *constructor*, not by convention:**

| Class | May accept | Must return | Example |
|---|---|---|---|
| `INFORMATIONAL_READ` | cache path, cached observation, stale fallback | value **+ visible `as_of`** | TMS pocket brief |
| `DECISION_SUPPORT_READ` | cache path, cached observation | value **+ `as_of` + `stale` flag** — **disclosure is mandatory** | aged-AR digest |
| `CONSEQUENTIAL_FRESHNESS_READ` | **live source only.** No `cache_path`, no cached observation, no stale fallback, **no generic read provider** *(a generic provider is a cache in disguise)* | a **live observation** with `observed_at`; **`None` on failure — never a fallback** | **the load-amount resolver** |

**Enforcement — shipped in this commit, ahead of B2:**
`eval/tests/test_consequential_read_boundary.py` fails if any reader on the `CONSEQUENTIAL` register
acquires a cache-shaped constructor parameter (`cache*`, `stale*`, `cached*`, `*read_provider*`,
`fallback*`) or references a cache symbol in its body.

**It is a structural test, not a comment.** It is deliberately landed **before** B2, so the mine cannot
be laid without tripping the wire. Under ADR-004 this becomes redundant — the pre-effect checkpoint
revalidates against the authoritative source regardless — but **ADR-004 is not built yet, and B2 is one
line away today.**

---

## SUMMARY

| | Changeset | Consequential | Tests pass | Verdict |
|---|---|---|---|---|
| **B1** | IMAP retry | No | ✅ | **PROMOTE_AFTER_FIXES** — don't retry auth failures |
| **B2** | TMS read cache | Not today | ✅ | **PROMOTE_AFTER_FIXES** — V-3 guard first *(shipped)*, then disclose staleness |
| **B3** | Mailbox routing refresh | **YES** | ✅ | 🔴 **REDESIGN** — needs routing provenance; today an inference overwrites a human decision |
| **B4** | Ops-control assign-unlinked | **YES** | ✅ | 🔴 **PROMOTE_AFTER_FIXES** — blocked on B3; bind by message-id; SOP must not claim enforcement |

> **All four have green tests. Two of them silently destroy the owner's work.**
> Tests passing was never evidence. This is what the architecture reset is *for*.
