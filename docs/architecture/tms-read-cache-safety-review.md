# TMS Read Cache — Safety Review against ADR-001 C4

**Subject:** `src/freight_recon/tms_read_cache.py` (Stream B — untracked, unattributed, **NOT modified by this pass**)
**Governing rule:** ADR-001 **C4** — *"The projection is for **knowing**. The authoritative system is for **acting**. A consequential action MUST revalidate against the authoritative source at execution time."*
**Date:** 2026-07-09

---

## 1. HEADLINE

> ## **The cache does NOT currently serve a `CONSEQUENTIAL_FRESHNESS_READ`.**
>
> **Per instruction, `tms_read_cache.py` was NOT modified.**

It is safer than the audit feared. But it has **two disclosure violations** and **one serious latent footgun** that will become a money defect the first time someone wires it one line further.

---

## 2. WHAT IT ACTUALLY DOES

`TmsReadCache(path, ttl_seconds=300)` · `get(key, allow_stale=False)` · `put(key, value)`
Returns `CachedTmsRead(value, age_seconds, stale)`.

**It is a failure-fallback, not a read-through cache.** The live read is always attempted first. The cache is consulted **only** when the live read cannot be trusted:

| Trigger | Behaviour |
|---|---|
| Browser is busy (a write holds the lock) | serve cached |
| Invoices table absent (unrendered / logged-out page) | serve cached |
| Exception during the read | serve cached |
| Live read succeeds | **`put()` and return live** |

**Two properties that materially reduce the risk:**
1. **`allow_stale=False` at every call site.** Beyond the 300 s TTL the cache returns `None` — so the reader returns **`None` (honest "couldn't read")** rather than a stale value. **It does not manufacture a false all-clear.** This is `unknown ≠ absent` (I7, R10) correctly preserved.
2. **The live read is always tried first.** The cache never pre-empts a good read.

> **Credit where due:** the author clearly understood the false-clearing hazard. The docstring says so explicitly. This is not careless code.

---

## 3. CONSUMER CLASSIFICATION

**Only two consumers exist.** Both are built in `run_action_callback_server.py`.

| # | Consumer | Feeds | Classification | Verdict |
|---|---|---|---|---|
| 1 | `_build_receivables_reader(cache_path=…)` | `receivables_reader` → *"who owes us the most"*, the aged-AR digest, and the *"draft reminders"* prompt | **`DECISION_SUPPORT_READ`** — it **prepares and prioritizes work** (which customer to chase) | ⚠️ **VIOLATION — staleness is not disclosed** |
| 2 | `_build_tms_brief_reader(cache_path=…)` | `tms_brief_reader` → *"what's happening"* pocket brief | **`INFORMATIONAL_READ`** | ⚠️ **VIOLATION — no visible `as_of`** |

### 3.1 Readers that are **NOT** cached — and this is the finding that matters most

| Reader | Cached? | Why it matters |
|---|---|---|
| **`_build_load_amount_resolver`** | ❌ **No `cache_path` parameter** | **This is the reader that supplies the AMOUNT bound into a money action.** It performs a **live** read of `/loads`. |
| `_build_document_resolver` | ❌ | Filesystem. |
| `_build_load_state_reader` | ❌ | Live. |
| `_build_load_docs_reader` | ❌ | Live. |
| The agent's own reads during execution | ❌ | Direct CDP. |

**Therefore: no cached value can currently reach a consequential financial action.** The amount that gets fenced into a write is read live, at proposal time.

---

## 4. VIOLATIONS FOUND

### V-1 — `DECISION_SUPPORT_READ` does not disclose staleness · **MEDIUM**
The rule: *"may use cached data to prepare or prioritize work, **but must disclose staleness**."*

**The reader returns `cached.value` and throws away `age_seconds` and `stale`.** The owner is shown the aging digest with **no indication whatsoever** that it came from a cache after a failed live read.

**Concrete failure:** the browser is busy with a write. The owner asks *"who owes us the most?"* and is served a 4-minute-old snapshot **presented as current**. They act on it — draft reminders to a customer who paid three minutes ago.

**Mitigating:** the TTL is 300 s and AR aging is **day-granular**, so the practical error is usually nil. **The rule is still violated**, and the mitigation is luck, not design.

### V-2 — `INFORMATIONAL_READ` has no visible `as_of` · **LOW–MEDIUM**
The rule: *"may use cached data **with a visible `as_of` timestamp**."*
The brief renders no timestamp. **Honest health (§25.5) requires the system to say when it last actually saw the world.**

### V-3 — ⚠️ **LATENT FOOTGUN — HIGH** (the reason this review matters)

> **`_build_load_amount_resolver` sits directly beside two sibling readers that already take `cache_path`, with an identical signature shape.**
>
> **Adding `cache_path=…` to it is a one-line change** — visually consistent, obviously "correct" to a future engineer or coding agent tidying up an inconsistency — **and it would immediately begin feeding cached, possibly-stale amounts into the money fence.**

That is a **direct ADR-001 C4 violation**, and it would be **completely invisible in review** because it looks like a symmetry fix. *This is exactly the kind of defect that gets introduced by someone being helpful.*

**The cache is not currently unsafe. It is one plausible line away from being unsafe, and nothing in the code says so.**

---

## 5. RECOMMENDATIONS (**not executed — Stream B is frozen pending D1**)

| # | Action | Severity | Touches Stream B? |
|---|---|---|---|
| **R1** | **Make the amount resolver structurally un-cacheable.** It must not merely *lack* a `cache_path` — it must be **impossible** to give it one. Under the target architecture this is `CONSEQUENTIAL_FRESHNESS_READ`, and ADR-004's checkpoint revalidates live regardless. **Until then, an explicit refusal + a comment naming C4.** | **HIGH** | ✅ *(stop for approval)* |
| **R2** | Return the full `CachedTmsRead` (value **+ `age_seconds` + `stale`**) from the cached readers, and **render `as_of` in the owner-facing digest and brief.** | MEDIUM | ✅ |
| **R3** | Add a **read-classification tag** to every reader (`INFORMATIONAL` / `DECISION_SUPPORT` / `CONSEQUENTIAL`), enforced by a test asserting **no `CONSEQUENTIAL` reader is constructed with a cache**. | MEDIUM | ✅ |

**All three touch Stream B. Per instruction, this pass stops here for approval.**

---

## 6. VERDICT

| Question | Answer |
|---|---|
| Does the cache serve a `CONSEQUENTIAL_FRESHNESS_READ` today? | **NO** |
| Does it satisfy the mandatory pre-effect freshness checkpoint? | **It is never asked to — and it must never be.** |
| Was `tms_read_cache.py` modified in this pass? | **NO** (per instruction) |
| Is it safe to keep, provisionally? | **YES — with V-3 recorded as a HIGH latent risk.** |

> **The cache itself is well-built and its instincts are right.** The danger is not in what it does; it is in **how easy it would be to point it at the money.**
