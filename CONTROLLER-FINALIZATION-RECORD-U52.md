# P5 U5.2 — controller's finalization record

## Certification chain executed

Five candidates, four rejections, three fresh reviewers and three separate adjudicators, no role
reused across builder / reviewer / adjudicator, and no builder certifying itself.

| # | candidate | parent | verdict | preserved |
|---|---|---|---|---|
| 1 | `f01d942` | `eda3a6d` | REJECT — targeted remediation required | `refs/preserve/p5-u52-rejected-candidate-f01d942` · review `405f5cf6` · adjudication `b384949d` |
| 2 | `a6005a8` | `eda3a6d` | REJECT — targeted remediation required | `refs/preserve/p5-u52r-rejected-candidate-a6005a8` · review `444ff5ab` · adjudication `e1ae22d7` |
| 3 | `2ccf5e1` | `eda3a6d` | **ACCEPT WITH NONBLOCKING FINDINGS**, upheld | review `8e423263` · adjudication `d1cbf117` |

All three candidates are **siblings on `eda3a6d`**, never descendants of a rejected one — Option A,
matching the U5.1 precedent where `38b4bda`, `1ae365a` and `d59b740` are all siblings on `6e8127d`.

## Finalization

- Content commit `2ccf5e1ff88302703834d68706a7e4b221a43d89`, tree `0d8942ac`
- Metadata commit `c74407aec874a55c6145a18b5d1a2a0fa891581c`, **sole parent** `2ccf5e1`, no merge
- `scripts/finalize_status.py` run **exactly once**, exit 0; the five status files it rewrote are the
  only contents of the metadata commit
- Executed suite 2135 passed / 0 failed / 1 skipped / 2136 collected
- Clean-clone gate **PASS**, all nine steps, including the complete canonical suite in the clean clone
  at 2135/0/1
- `test_status_reality.py`: 7 passed, 0 skipped
- Nothing pushed; `main` still at `152574e`; no protected ref moved

## Invariants verified after the commit

Canonical F1–F13 events **105**, digest `1485bd6f0f6dd02b` · classification
`PRODUCER 117 / CONSUMES 9 / NON_PRODUCING 6 / DELEGATES_TO 2 / EVENT_REQUIRED 0` = **134** ·
P5 `READY / NOT_STARTED / NO_CHECKPOINT` with **14 criteria all PENDING, none scored** ·
P4 `COMPLETE / COMPLETE / PHASE_ACCEPTANCE_COMPLETE` with 14 PASS · `src/` byte-unchanged versus
`eda3a6d` · `PROGRAM-WEIGHTS.yaml` byte-unchanged · R-07 CONTAINED · Phase-8 gate registration
`DEFERRED BY FOUNDER DECISION to U8.1 / P8` · **zero** `GateRegistry(` constructions in `src/` ·
first-parent topology metadata → content → metadata → content.

## A-3 — found by the controller during post-finalization verification

The U5.2 sub-unit record still carries
`record_type: CONTENT_CANDIDATE_AWAITING_FRESH_INDEPENDENT_REVIEW`. That claim is now **stale**: the
fresh independent review (`8e423263`, ACCEPT WITH NONBLOCKING FINDINGS) and the separate targeted
adjudication (`d1cbf117`, UPHOLD ACCEPT, finalization YES) have both been performed and preserved,
and the candidate has been finalized.

**This is R4-A recurring, in the same structural position and for the same reason.** R4-A was U5.1's
identically stale `record_type`, found by the controller at exactly this point in the cycle and
corrected by U5.2. The cause is not carelessness: the correct value cannot be known until the review
and adjudication complete, which is necessarily *after* the content commit is sealed, and the
`record_type` is hand-authored registry content that `finalize_status.py` does not generate.
Correcting it would require either a second content commit — forbidden by PROGRESS-PROTOCOL §10,
which permits `HEAD` to be only the content commit or the single metadata commit above it — or
smuggling unreviewed prose into a status-metadata commit, which is the discipline this repository
exists to protect.

No guard catches it and the full suite is green with it in place.

**Owed to the next G2-adjacent unit, together with A-1 and A-2.** It should be corrected first, for
the same reason U5.2 corrected R4-A first: a reader of the registry today is told this candidate is
still awaiting a review that has in fact been completed, adjudicated and finalized.

**Structural note for whoever owns it.** This has now happened on two consecutive units. The defect is
in the *protocol*, not in either unit: any `record_type` that describes a candidate's certification
state is unwritable at the only moment the topology allows content to be written. A durable fix — for
instance, making the certification state a finalizer-derived status field rather than hand-authored
registry prose, or recording it only in the preserved governance refs where it already lives
truthfully — belongs to whichever unit is authorized for `scripts/finalize_status.py` and
`STATUS_METADATA_FILES`. Recording it as a third instance of the same residual, without proposing
that fix, would be recording the symptom.

## Residuals owed to the next G2-adjacent unit

Carried in the adjudication at `refs/preserve/p5-u52r2-targeted-adjudication-2ccf5e1`, which is the
authoritative record for them:

- **A-2 (F-2)** — five uncatchable discharge-path rules, three enumerated; the two MINTED §3
  corroboration checks are the sole defence against a sec-3-only re-attribution and are asserted by no
  node. **Owed by the first unit that amends `ADJUDICATED_EVENT_REQUIRED` or
  `FOUNDER_AUTHORIZED_DISCHARGES`, BEFORE it amends either.**
- **A-1** — the guard quotes the audit as saying `"remains available and unused"`; this candidate's own
  R-05 remediation deleted that sentence, so the audit contains it zero times.
- **A-3** — the stale `record_type` above, plus the structural fix.
- **F-3** — the registered-`durable_write` *requirement* is a mutation MISS; only the datum is caught.
- **F-4** — two caller-side rules each a MISS, both verified to fail closed on a neighbouring rule.
- **F-5** — the commit says the renumbering touched 13 registry sites; the count is 12.
- **F-1** — the commit message states `21 of 28` where the truth is `19`, twice measured. No in-tree
  counterpart exists; corrected by the adjudication record, nothing further owed.
- Carried forward unchanged: **R-02**, **G2-D15**, **G2-D16**, **G2-D4/D6/D8/D9/D10**, and the
  **PL-11c → OutcomeUnknown** residual.

## Not verified by anyone in this cycle

No clean-clone measurement exists from the builder, either reviewer or either adjudicator —
`clean_clone_gate.py` is the finalizer's own artifact and none of them ran it. The finalizer ran it
itself and it passed. The seven minted payloads, schemas and family contracts were upheld by three
adjudications and are byte-identical across all three candidates, but were not re-derived after the
first. The CONSUMES relation matrix beyond the `BrakeReleased` cases, `ADJUDICATED_UNDECLARED_ACCEPTS`
and the carried `PL-11c → OutcomeUnknown` residual were not re-cut. Whether founder decisions D1, D2
and D3 were actually made cannot be established from inside a repository.
