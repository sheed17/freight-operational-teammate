# Working-Tree Separation Plan

**Purpose:** hunk-level attribution of every uncommitted change found in the working tree at
`974031d`, so that Stream A can be committed to the trusted baseline and Stream B can be preserved
outside it without loss.

**Governing decision:** **D1** — *"Preserve Stream B, but do not treat it as part of the trusted
baseline yet. Its provenance is unknown... Do not attribute Stream B's implementation to this
architecture-reset session. Do not discard it."*

**Date:** 2026-07-13 · **Baseline before separation:** `974031d`

---

## 1. HOW ATTRIBUTION WAS ESTABLISHED

Three independent forms of evidence were used. **No hunk was classified by assumption.**

| Evidence | What it proves |
|---|---|
| **Symbol reachability** | Does the hunk reference a Stream A symbol (`upload_file`, `set_file_input`, `_build_document_resolver`, `load_state_reader`, `load_docs_reader`, `_is_complaint`) or a Stream B symbol (`TmsReadCache`, `cache_path`, `--corpus`, `assign unlinked`)? |
| **File mtimes** *(recovered from the mtime-preserving preservation tar — `cp` had already destroyed them in the snapshot)* | **When** the change was written, relative to the last known-session commit `591d2de` (**Jul 8, 14:54**). |
| **Behavioural coherence** | Does the change belong to a single, self-consistent piece of work? |

### 1.1 The timeline — three distinct bursts on Jul 8

```
  14:54   591d2de   last known-session commit
  ────────────────────────────────────────────────────────────────
  15:02   cdp_session.py                    ┐ STREAM A  (document upload)
  15:11   test_conversational_surface.py    ┘           ← see §4, the UNKNOWN
  ────────────────────────────────────────────────────────────────
  15:49   tms_read_cache.py    (new)        ┐
  15:49   imap_mailbox.py                   │
  15:50   test_imap_mailbox.py (new)        │ STREAM B  — one coherent
  16:11   test_mailbox_intake.py            │           34-minute burst
  16:12   mailbox_intake.py                 │
  16:22   test_ops_control.py               │
  16:23   ops_control.py                    ┘
  ────────────────────────────────────────────────────────────────
  23:13   operator_agent.py                 ┐ STREAM A  (document fence)
  23:14   operation_router.py               │
  23:18   test_operator_agent.py            ┘
  ────────────────────────────────────────────────────────────────
  Jul 12  action_callback.py, test_action_callback.py, run_teammate.py
          (this session: dogfood fixes retained + D2/D4 safety pass)
```

**Stream B is a single, contiguous, self-consistent 34-minute burst that touches no Stream A symbol
and is touched by no Stream A symbol.** That is what made a clean separation possible.

---

## 2. HUNK-LEVEL CLASSIFICATION

### 2.1 STREAM_A — attributable, tested, live-verified → **committed to baseline** (`034b055`)

| File | Lines | Behavior change | Evidence | Independent? | Tests | Live-verified |
|---|---|---|---|---|---|---|
| `cdp_session.py` | +37 | `set_file_input()` via `DOM.setFileInputFiles` | Jul 8 15:02 burst; upload symbol | ✅ | yes | ✅ **live** — real TruckingOffice "Attach BOL" form |
| `cdp_actuator.py` | +12 | `upload_file` actuator verb | calls `set_file_input` | dep: `cdp_session` | yes | ✅ live |
| `operator_agent.py` | +24 | `UPLOAD` action + **document fence** (runtime supplies the file; fail-closed without one) | Jul 8 23:13 burst | dep: `cdp_actuator` | yes (+26 in `test_operator_agent`) | ✅ live |
| `operation_router.py` | +21 | `document_for` / `requires_document` — binds the document at propose time | Jul 8 23:14 burst | dep: `operator_agent` | yes | ✅ live |
| `action_callback.py` | +225 | 6 dogfood fixes: already-invoiced guard, per-load story, propose-time doc fence, complaint detection, doc-status query; D4 dead-radar removal | Jul 12; **zero** cache references | ✅ | yes | ✅ live (Slack) |
| `ar_collections.py` | +5 | `_REF_LIKE` token parsing (customer-name misparse) | dogfood fix #4 | ✅ | yes | ✅ live |
| `run_action_callback_server.py` | +153 *(of +171)* | `import re`; `_build_document_resolver` (**fail-closed**: never substitutes a different doc type); `_build_load_state_reader`; `_build_load_docs_reader`; their wiring | see §3 — **mixed file, split by line** | yes | ✅ live |
| `test_operator_agent.py` | +26 | upload fence tests | tests Stream A only | ✅ | — | n/a |

### 2.2 STREAM_B — provenance unknown, **NOT** in the baseline → preserved on `preserve/pre-reset-readiness-hardening`

| File | Lines | Behavior change | Evidence | Independent? | Tests | Live-verified |
|---|---|---|---|---|---|---|
| `imap_mailbox.py` | +57 | **B1** — IMAP retry (3 attempts, 2 s sleep) around a new `_pull_imap_messages_once` | Jul 8 15:49 burst | ✅ | `test_imap_mailbox.py` (new) | ❌ **none** |
| `tms_read_cache.py` | **new** | **B2** — durable read cache (`put`/`get`, 300 s TTL) | Jul 8 15:49 burst | ✅ | via `test_action_callback` | ❌ none |
| `run_action_callback_server.py` | +18 *(of +171)* | **B2** — `cache_path` on `_build_receivables_reader` / `_build_tms_brief_reader` + 2 call-site args | see §3 | dep: `tms_read_cache` | yes | ❌ none |
| `test_action_callback.py` | +20 | **B2** — cached-reader-when-browser-busy test | imports `TmsReadCache` | dep: B2 | — | n/a |
| `mailbox_intake.py` | +90 | **B3** — `_refresh_existing_message_routing`: recompute routing for **all** preserved messages **every cycle** | Jul 8 16:12 burst | ✅ | `test_mailbox_intake.py` (+39) | ❌ none |
| `run_teammate.py` | +5 | **B3** — `--corpus` forwarding to the Gmail loop | supports B3 | dep: B3 | `test_run_teammate` (+10) | ❌ none |
| `ops_control.py` | +107 | **B4** — `assign unlinked N to <LOAD>`; `never bill without POD` SOP; `show unresolved`; `why did you do that?` audit; `what did we invoice today?` | Jul 8 16:23 burst | ✅ | `test_ops_control.py` (+93) | ❌ none |
| `test_mailbox_intake.py` · `test_ops_control.py` · `test_run_teammate.py` · `test_imap_mailbox.py` | +39/+93/+10/new | tests for B1–B4 | — | dep: B1–B4 | — | n/a |

### 2.3 APPROVED_SAFETY_FIX — **already committed** at `974031d`
D2 mock-execution-path removal; D4 dead-radar removal. *(Not re-litigated here.)*

### 2.4 GENERATED / ARTIFACT
`docs/MVP_DEMO_SCORECARD.md` — untracked demo artifact. **D5: preserve, do not delete.** Held on the
preservation branch, out of the baseline.

---

## 3. THE ONE MIXED FILE — `scripts/run_action_callback_server.py`

**This is the only file containing hunks from two streams.**

One hunk was genuinely mixed, because Git groups adjacent additions:

```
@@ -155,2 +157,15 @@
             lock_path=(workspace / "browser.busy") if workspace else None,
+            cache_path=(workspace / "tms_read_cache.json") if workspace else None,   ← STREAM_B
+        )
+        load_state_reader = _build_load_state_reader(                                ← STREAM_A
+            ...
+        load_docs_reader = _build_load_docs_reader(                                  ← STREAM_A
+            ...
```

**Classification: `MIXED_HUNK` — but *not* `REQUIRES_MANUAL_SPLIT` in the semantic sense.** The two
streams are adjacent, not entangled: they touch **different call sites of different functions**. Git
merged them into one hunk purely by proximity.

**Resolution — split by construction, not by `git add -p`:**

* **Stream A version** = working tree, with `_build_receivables_reader` and `_build_tms_brief_reader`
  restored to their `HEAD` (uncached) bodies and both `cache_path=` call-site args dropped.
* **Stream B version** = `HEAD`, with only those two reader bodies replaced and the two `cache_path=`
  args re-inserted.

**Losslessness proven arithmetically:**

| Version | Lines |
|---|---|
| `HEAD` | 483 |
| Stream A only | 636 *(+153)* |
| Stream B only | 501 *(+18)* |
| Working tree (A+B) | **654** *(+171 = 153 + 18)* ✅ |

**No line is claimed twice; no line is dropped.** Both versions were asserted to parse, to contain all
of their own symbols, and to contain **none** of the other stream's.

---

## 4. UNKNOWN — `eval/tests/test_conversational_surface.py` (+48)

**Classification: `UNKNOWN`. Held OUT of the baseline.**

| Question | Answer |
|---|---|
| References any Stream A symbol? | **No** |
| References any Stream B symbol? | **No** |
| What does it test? | Conversational routing that **already exists in HEAD**: typed-operation customer binding, `approved_amount`/`party` invariants, pending-op challenge short-circuit. |
| mtime | **Jul 8, 15:11** — inside the *Stream A* burst (`cdp_session` 15:02), and **38 minutes before** the Stream B burst begins (15:49). |

> **The temporal and symbolic evidence both point to Stream A.** But attribution by clustering is
> *evidence*, not proof, and I cannot claim it was live-verified. **Attribution is precisely what I was
> instructed not to guess** — so it is preserved in its own clearly-labelled commit and left for a human
> to promote. It is test-only; excluding it costs the baseline no production behavior.

**Recommendation:** promote to the baseline (one `git cherry-pick`), after you confirm it is yours.

---

## 5. RESULT

| Stream | Destination | Commit |
|---|---|---|
| **A** | baseline (`demos`) | `034b055` |
| **B** | `preserve/pre-reset-readiness-hardening` | `9bf31d0` |
| **UNKNOWN** | `preserve/pre-reset-readiness-hardening` | *(separate commit, labelled)* |
| **Artifact (D5)** | `preserve/pre-reset-readiness-hardening` | *(separate commit)* |
| **Safety fix (D2/D4)** | baseline | `974031d` *(pre-existing)* |
| **Architecture docs** | baseline | *(this commit)* |

**Full suite on the clean baseline: 673 passed, 0 failed.** Stream A carries **no** hidden dependency
on Stream B — which is the strongest available proof that the split is correct.
