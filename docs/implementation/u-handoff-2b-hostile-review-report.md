> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-HANDOFF-2B — Second Hostile Formal CLI Handoff-Readiness Review — Preserved Evidence

## Preservation record — read this before the report body

This file preserves the independent hostile review **U-HANDOFF-2B**, the review that
U-HANDOFF-1's acceptance contract required before the handoff gate could close. It was produced
by an independent session (branch `hostile-review-fe7843d`) against commit
`fe7843d2abdb1260cfc71c958c3fea76a15df56e` and delivered to the adjudicating session by founder
paste on 2026-07-20. The adjudication of this evidence is
[`u-handoff-1d-final-adjudication-review.md`](u-handoff-1d-final-adjudication-review.md).

**Completeness — stated exactly, because this repository does not overstate evidence:**

- **Received:** the report title; §1 (limitation statement) through §15 (production-authority
  result) complete; §16 (the false-confidence mutation battery) through attack row **46**
  complete, plus the first half of row 47's text.
- **Not received:** the transport truncated the message at row 47 of the 60-attack table with the
  literal marker `[Message truncated - exceeded 50,000 character limit]`. The founder delivered
  the report twice; the session transcript confirms both deliveries truncated at the identical
  byte. The remaining attack rows (47–60), every section after §16 — including the §19
  low-severity findings that §12 references — and the verdict line itself are therefore **not in
  this file**.
- **Verdict attestation:** the verdict `READY FOR FINAL ZIP INSPECTION` was not received inside
  the report body. It is attested twice by the founder's U-HANDOFF-1D instructions ("The
  independent hostile review U-HANDOFF-2B concluded: READY FOR FINAL ZIP INSPECTION") and by the
  founder's description of the source file ("ends with: READY FOR FINAL ZIP INSPECTION … no
  critical or high findings, no blockers"). The adjudication treats the verdict as
  **founder-attested**, and the evidence base as the received sections plus the adjudicating
  session's own re-execution of the canonical finalizer, suite and clean-clone gate — not the
  attestation alone.
- **Exclusions:** unrelated material present in the same paste (content from other conversations)
  was **not** preserved here. Only the report text, verbatim from its title to the truncation
  marker, appears below.

**Independent verification performed by the adjudicating session (U-HANDOFF-1D):** every
repository-checkable claim in the received sections was re-verified mechanically — HEAD, trees,
the exact five-file metadata diff (§2), the gate receipt's commit/tree binding and clone counts
(§5), the 1233-node manifest identity (§7), the 3 discovered skip sites (§8), and the exact
10-module control-guard population (§9). All matched. The finalizer, suite and clean-clone gate
were then re-executed end-to-end by the adjudicating session itself. See the adjudication review
for the full disposition.

---

## Verbatim received text

```text
U-HANDOFF-2B — Second Hostile Formal CLI Handoff-Readiness Review

1. Limitation statement

This review used only checked-in repository content: tracked documents, source, local Git history, repository scripts, tests, guards, fixtures and manifests. No web search, external connector, prior-session memory, or founder explanation outside the checkout was used. It was read-only with respect to tracked content: I created only ignored execution artifacts (a .venv, temp clones spawned by the canonical gate, __pycache__, and scratchpad files outside the repo). Every mutation was performed with an in-memory save/finally harness that restores byte-identically and purges bytecode; Git reset/checkout/restore/stash/clean were never used to undo a mutation. The finalizer's own status writes were reverted by restoring a pre-run file snapshot (a plain copy, not Git). Final tracked tree confirmed byte-identical to the starting tree.

2. Starting HEAD, tree and cleanliness

- Branch hostile-review-fe7843d
- HEAD fe7843d2abdb1260cfc71c958c3fea76a15df56e (metadata commit)
- Tree a26404f0e19aeb2e2b99ac6a67dc2c0a8851870a
- Working tree clean
- Content commit d3c85f3974ef7624b6588c3479c7ad5f3935c657; content tree b5a987df36b940d475c66f5021cba6e593121c07
- Metadata commit fe7843d changed exactly the five status files (CURRENT.md, GATE-RESULT.json, IMPLEMENTATION-REGISTRY.yaml, SUITE-RESULT.json, u-handoff-1c-…-review.md) and nothing else — verified by git diff --name-only d3c85f3 fe7843d. The two-commit convention holds.

3. Bootstrap result

Followed the documented path exactly. scripts/check_env.py on the host (Python 3.10.8) correctly failed fast with the exact detected/required versions — the H-1 bootstrap correction working. Recreated the venv with Python 3.13.5; check_env passed inside it; pip install -e ".[dev]" succeeded; all 11 declared imports (pydantic instructor anthropic openai fitz yaml dotenv reportlab PIL websocket pytest) import cleanly.

4. Canonical finalizer result

Ran scripts/finalize_status.py end-to-end as a fresh formal agent would (~13 min). It executed everything it attests to and observed exit statuses directly. Traced all 14 required properties: it (1) refuses a dirty tree first, (2) resolves commit/tree itself via git rev-parse, (3) runs the complete suite in-process, (4) runs the clean-clone gate and reads only the record that run produced, (5) executes the control guards + AC-SAFE-012/013 + AC-SEC-001 explicitly, (6) observes process exit statuses, (7) writes receipts only after execution, (8) never reads a pre-existing suite artifact (load_artifact absent from the script), (9) offers no count/artifact/trust/skip/filter flag, (10–12) refuses skipping/filtering/deselection and aborts before any status write on any failed step, (13) binds status to the content commit/tree, (14) leaves the checkout clean. Output: status finalized from EXECUTED results: 1232/0/1 on fe7843d2a (a26404f0e). It reproduced the recorded status onto the current commit. I restored the four status files it rewrote from a pre-run snapshot; tree byte-identical afterward.

5. Clean-clone result

Executed by the finalizer via scripts/clean_clone_gate.py: fresh git clone of committed state, no data/active_workspace in the clone, host + venv Python floor, declared-deps-only install, complete canonical suite in the clone = {passed: 1232, failed: 0, skipped: 1, collected: 1233}, control guards + AC gates green, clone tree still clean. CLEAN-CLONE GATE: PASS. Authoring-checkout and clean-clone results are identical.

6. Exact suite result

1232 passed · 0 failed · 1 skipped · 0 deselected · 1233 collected · exit 0. Recomputed by the finalizer's own run (duration ~378 s). unexecuted_nodes=0, rogue_nodes=0, xfail_nodes=0.

7. Exact node-manifest result

TEST-NODE-MANIFEST.json records 1233 exact node identities (node_count == len(node_ids), all unique, all eval/…::), with manifest_sha256, config_sha256, runner_sha256 bindings. Live collection under the isolated config matches by identity (missing 0, extra 0).

8. Exact approved-skip result

expected_canonical_run_skips = exactly one node: test_phase0_guard_integrity.py::test_the_red_by_design_cases_are_strict_xfails (conditional, self-describing). static_sites lists two skip-capable constructs (the above, plus the test_status_reality dirty-tree skip that is deliberately forbidden as a canonical-run outcome). AST discovery over all 107 canonical test modules finds exactly 3 skip/xfail sites, all accounted for; 0 importorskip, 0 module-level pytestmark.

9. Exact control-guard population

Discovered dynamically (by reference, not enumeration): 10 control-guard modules — test_bootstrap_hermeticity, test_docs_control_system, test_false_green_defenses, test_phase0_baseline_manifest, test_phase0_entry_points, test_phase0_errata_guards, test_phase0_identifiers, test_phase2_guard_registry, test_status_reality, test_tool_access_policy. The finalizer/gate explicitly re-run the five core control guards. (The repository's "166 control guards" phrasing does not appear verbatim in tracked files; the guard population is the discovered set above and the suite counts are the machine-maintained block — no stale figure survives.)

10. Dynamic-discovery result

eval/control/inventory.py derives every population from git ls-files, the authority map's own classification rows, documented family rules, and AST/collection — never a typed filename list. I planted representative files in each family (a map-classified current-authority doc, a review-family doc, a root roadmap, a test module) and confirmed each entered the correct population without editing inventory.py: tracked_textual, current_authority, review_family, historical, banner_required, test_modules, control_guards all returned true. The meta-guard test_no_control_guard_hand_enumerates_a_file_population distinguishes prohibited discovery-by-filename (a planted 3-path literal was flagged) from legitimate fixed specs (the same literal annotated FIXED-SPECIFICATION was allowed). Fixed specs (HANDOFF-01…13, P0…P14, the checkpoint steps, the 7+1+3 table partition) are correctly exempt.

11. Authority-resolution result

No current-authority document contains a live contradiction. CLAUDE.md, PRODUCT.md, ARCHITECTURE.md, docs/CANONICAL-DOCUMENTS.md, CURRENT.md, the registry and PHASE-OUTPUTS all use the corrected "13 of 134 … COUNT NEEDS ADJUDICATION" figure and the P0–P14 program, and each labels the old "24" as retired and the 8-stage roadmap as superseded. The authority map states the precedence rule ("No HISTORICAL document ever outranks a CANONICAL one") and names the chain root. No brittle *.py:NNNN citations in current-authority docs. registry.md and the root roadmaps carry their banners.

12. Historical-banner result

Every superseded/quarantined map-classified document and every implementation review carries a disarming banner in its first block, physically preceding stale text — verified mechanically by the position-aware guard and by direct inspection of the "READY TO BEGIN" / "24 of 134" / stale-suite-total repetitions (all sit below line-1 banners). Two low-severity gaps noted in §19.

13. Safety-graph result

Mechanically verified against the registry: P0/P1/P2 COMPLETE; U-HANDOFF-1 is the only READY unit; P3 BLOCKED, deps [P2, U-HANDOFF-1]; P4 deps [P3]; every P4–P14 has P3 as a transitive ancestor and every P5–P14 has P4; every P4–P14 keeps its direct predecessor; unlocked_by/blocks/next_units_unlocked mirror dependencies exactly; no cycles, no dangling deps, no disconnected islands (every phase reaches P0); no later READY phase. P3 is unimplemented in src/ (no checkpoint/witness/CAS symbol; only a forward-reference comment). A subsequent formal repository-adjudication step can safely complete U-HANDOFF-1 and unlock P3.

14. Product-identity result

A fresh agent is led to the correct understanding across all five docs: Neyma is an operational execution layer for small and medium freight brokerages, coordinating exactly eleven loops (W1–W11, guarded as an exact set), with invoice work explicitly named as a first implemented surface, not the product (PRODUCT.md §12). The invoice-processor / extraction / TMS-chatbot / Slack / browser-wrapper / AP-reconciliation readings are all explicitly rejected. Unvalidated freight rules are governed by OPEN-VALIDATION-ITEMS.md (fail-closed, stop-and-ask); founder product decisions vs customer operational rules carry different authority (tool-policy §4, accountable-source fields, ADR-003 as permanent product truth).

15. Production-authority result

TOOL-ACCESS-POLICY.md grants broad research/tool access, states plainly that tool access is not action authority ("Possession of a tool or credential is never authorization to execute a consequential effect"), carries the mandatory five-class missing-context taxonomy, and forbids interpreting access as permission to write a TMS/accounting system, move money, send communications, contact customers/carriers, rotate credentials, retry UNKNOWN_OUTCOME, or manufacture design-partner evidence. test_tool_access_policy.py enforces these bidirectionally. No live credentials are committed (.env gitignored, .env.example stubs only). The six R-07 live-write paths are disclosed and centrally adjudicated in EFFECT-PATH-INVENTORY.yaml, cross-flagged OPEN — NOT CONTAINED everywhere an agent reads.

16. Every false-confidence mutation and result

All 60 attacks defended. Each mutation was proven faithful (the mutant genuinely misbehaves absent the defense), attributed to a guard, seen to fail non-zero, and restored byte-identically.

┌───────┬───────────────────────────────────────────────────────────┬──────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│   #   │                          Attack                           │        Result        │                                           Defending mechanism                                            │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1     │ Perfect green suite artifact                              │ DEFENDED             │ finalizer never reads a pre-existing artifact; execution replaces it                                     │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2     │ Perfect clean-clone receipt                               │ DEFENDED             │ gate result bound to commit/tree; wrong-commit refused                                                   │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3     │ Consume pre-existing receipt                              │ DEFENDED             │ _receipt_baselines freshness: "predates this invocation"                                                 │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4     │ Artifact from another commit                              │ DEFENDED             │ artifact_consistency_errors commit check                                                                 │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5     │ Artifact from another tree                                │ DEFENDED             │ tree check                                                                                               │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6     │ Failed suite, matching total                              │ DEFENDED             │ validator + in-process "did not pass cleanly"                                                            │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 7–11  │ -k / marker / --deselect / --ignore / --ignore-glob in    │ DEFENDED             │ _config_is_clean rejects filtering tokens                                                                │
│       │ config                                                    │                      │                                                                                                          │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 12    │ Changed testpaths                                         │ DEFENDED             │ config testpaths check                                                                                   │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 13    │ PYTEST_ADDOPTS filtering                                  │ DEFENDED             │ runner clears env (1233 vs 121 unprotected)                                                              │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 14    │ pyproject addopts suppression                             │ DEFENDED             │ explicit -c path ignores pyproject (1233 vs 121 bare)                                                    │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 15    │ Conftest collection plugin                                │ DEFENDED             │ node-identity divergence (138 nodes removed → refused)                                                   │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 16    │ Same-count substitution                                   │ DEFENDED             │ identity comparison (count unchanged, still refused)                                                     │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 17    │ Rogue test added                                          │ DEFENDED             │ extra-node identity refusal                                                                              │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 18    │ Missing test node                                         │ DEFENDED             │ missing-node identity refusal                                                                            │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 19    │ Collect-only as execution                                 │ DEFENDED             │ unexecuted_nodes + skip-set errors                                                                       │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 20–23 │ Skip a status/docs/tool-access/hermeticity guard          │ DEFENDED             │ node-identity divergence and/or static skip-site guard                                                   │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 24    │ Imperative pytest.skip()                                  │ DEFENDED             │ static site guard (unaliased) + runtime exact-skip-set (unit + real-run proofs)                          │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 25    │ pytest.importorskip()                                     │ DEFENDED             │ static site + module-machinery guards                                                                    │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 26    │ Unapproved xfail                                          │ DEFENDED             │ static site guard + runtime xfail-outcome check                                                          │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 27    │ Remove approved skip                                      │ DEFENDED             │ static set-equality (vanished/unapproved both ways)                                                      │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 28    │ Change approved skip reason                               │ DEFENDED             │ reason-anchor binding to source message                                                                  │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 29    │ Module-level pytestmark                                   │ DEFENDED             │ static site + machinery guards                                                                           │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 30–32 │ Dirty / staged / untracked-file tree                      │ DEFENDED             │ finalizer + runner refuse before any test                                                                │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 33–34 │ Tree change after suite/gate execution                    │ DEFENDED             │ committed-state checks SKIP (machine-visible, non-approved) + finalizer dirty refusal + gate reproduces  │
│       │                                                           │                      │ from commit                                                                                              │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 35    │ Result without running suite                              │ DEFENDED             │ throwing executor aborts; status untouched                                                               │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 36    │ Result without running gate                               │ DEFENDED             │ gate failure aborts                                                                                      │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 37    │ Clean-clone count mismatch                                │ DEFENDED             │ gate _fail decisive; finalizer refuses failed gate record                                                │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 38    │ Clean-clone manifest mismatch                             │ DEFENDED             │ gate _fail decisive; finalizer refuses                                                                   │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 39    │ Stale registry meta                                       │ DEFENDED             │ mirror guard: "disagrees with CURRENT.md"                                                                │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 40    │ Second READY unit                                         │ DEFENDED             │ exactly-one-READY + incomplete-deps guard                                                                │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 41    │ P5 bypasses P4                                            │ DEFENDED             │ transitive-ancestry (caught on lost P3)                                                                  │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 42    │ Each P6–P14 bypasses predecessor                          │ DEFENDED             │ all 9 individually caught                                                                                │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 43    │ P4 loses P3 ancestry                                      │ DEFENDED             │ ancestry guard                                                                                           │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 44    │ P5 loses P4 ancestry                                      │ DEFENDED             │ ancestry guard                                                                                           │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 45    │ Insert P15 outside wall                                   │ DEFENDED             │ discovered phase set + ancestry                                                                          │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 46    │ Missing reverse edge                                      │ DEFENDED             │ full-graph consistency (blocks vs dependents)                                                            │
├───────┼───────────────────────────────────────────────────────────┼──────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 47    │ Retired-24 in planted control doc                         │ DEFENDED             │ discovered current-authori

[Message truncated - exceeded 50,000 character limit]```
