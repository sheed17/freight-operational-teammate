# Verified metrics

Every figure on this page was reproduced on **2026-10-08** from commit
**`8ee5bf62d92a`** (branch `p5/u5-1-g2-spec-correction`) on macOS with Python 3.14.4. For each one:
the exact command, what the number measures, and what it does **not** show.

Ground rules for reading them:

- **All freight data is synthetic.** Every load, company, person and message was invented as
  development input. A count of loads processed is a count of fixtures, not of customers, shipments
  or revenue.
- **Shadow execution is not production.** Nothing here was deployed, and no figure describes live
  traffic.
- **A passing check is evidence only if it could have failed.** Where that was demonstrated, it is
  noted.

---

## 1. Test suite

| | |
|---|---|
| **Command** | `.venv/bin/python -m pytest eval --collect-only -q` |
| **Result** | **4,373 tests collected** across 187 test modules |
| **Measures** | The size of the canonical population `pytest eval` runs |
| **Limits** | A count of tests says nothing about their quality; see mutation testing below |

| | |
|---|---|
| **Command** | `.venv/bin/python -m pytest eval -q -p no:cacheprovider` |
| **Tree** | `8ee5bf6` plus the portfolio README and demo script (no runtime file changed) |
| **Result** | **4,352 passed, 20 failed, 1 skipped** in 17 min 21 s |
| **The 20 failures** | All twenty raise `PermissionError: [Errno 1] Operation not permitted` at `socket.bind`. They start a local HTTP callback server (19 in `test_action_callback.py`, 1 in `test_p4_deployed_governed_route.py`), and the sandbox this run executed in forbids binding a local port. They exercise code this change did not touch. |
| **The skip** | `test_phase0_guard_integrity.py` skips deliberately when no red-by-design cases remain |
| **Limits** | **This is not a clean green run and is not reported as one.** Those 20 tests were not exercised. Re-run them outside a sandbox before citing a full-suite pass: `.venv/bin/python -m pytest eval/tests/test_action_callback.py eval/tests/test_p4_deployed_governed_route.py -q`. Local Python was 3.14; CI's supported interpreters are 3.11 and 3.12. The state of CI on GitHub for this commit was not checked — the four newest commits are unpushed. |

| | |
|---|---|
| **Command** | `.venv/bin/python -m pytest eval/tests/test_p9_freight_domain_ships_dark.py eval/tests/test_p9_freight_histories.py eval/tests/test_p9_freight_interpretation.py eval/tests/test_p9_inference_gateway.py eval/tests/test_p9_load_loop.py eval/tests/test_p9_load_work.py -q` |
| **Tree** | `8ee5bf6`, clean |
| **Result** | **282 passed** in 4 min 22 s |
| **Measures** | The freight-domain spine, inference boundary, work engine and load loop, including the regressions for the case-study bug |

## 2. Mutation testing of the code

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/mutate_p9_load_work.py` |
| **Tree** | `8ee5bf6`, run against an isolated `git archive` export so the working tree was never modified |
| **Result** | **102 of 102 mutants CAUGHT** |
| **Measures** | Each mutant is a hand-written edit that reintroduces one specific, previously real defect in the work engine or load loop, paired with the test that must fail under it. `CAUGHT` requires that test to be green before the edit, red under it, and green again after a byte-verified in-memory restore. |
| **Limits** | These are targeted mutants chosen by the author, not a mutation score from an automated tool over all code. It shows that 102 named guards can fail; it does not measure overall test adequacy. The repository has 33 other batteries (`scripts/mutate_*.py`) that were **not** re-run for this page. |

## 3. Adversarial evaluation of the inputs

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/run_freight_corpus.py --loop --attack` |
| **Result** | **393 mutated histories, 8,153 audited evaluations, 0 findings** |
| **Breakdown** | never_arrives 252 · reordered 40 · arrives_late 20 · duplicate_arrival 20 · late_redelivery 20 · restart 20 · same_load_at_another_brokerage 20 · repeated_promise 1 |
| **Measures** | A deterministic layer rewrites each complete load history into hostile variants. After every evaluation an audit oracle, written independently of the detectors, re-derives from the canonical record whether the load is quiet while anything is owed, waited for or disputed. |
| **Limits** | The mutation operators and the oracle were written by the same project that wrote the code. Zero findings means the system is consistent with its own stated invariants under these perturbations — not that it handles real freight correctly. |

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/run_freight_corpus.py --attack` |
| **Result** | **164 mutated histories, 1,719 audited evaluations, 0 findings** (the fifteen through-time work histories) |

## 4. Replay and restart determinism

| | |
|---|---|
| **Evidence** | (a) `restart` 20, `reordered` 40 and `duplicate_arrival` 20 mutants in the layer above, all with 0 findings. (b) 44 tests in `eval/tests/test_p5_replay_and_audit.py` and 7 replay/restart/duplicate tests in `eval/tests/test_p9_load_loop.py`, all passing in the runs in section 1. (c) Two consecutive runs of `docs/portfolio/demo/disputed_delivery.py` produced byte-identical output (137 lines). |
| **Measures** | Replaying a history, delivering every record twice, reordering records and restarting mid-history produce the same operating pictures and neither lose nor invent work |
| **Limits** | Single process, SQLite, synthetic histories. No concurrency, crash-recovery or long-running soak test was run for this page. |

## 5. The continuous load loop

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/run_freight_corpus.py --loop` |
| **Result** | 21 histories · 22 loads · 425 records · 4,802 evaluations · 331 recorded moments · 10 deadlines passed in silence · **513 labeled checks, 0 failed** · 0 audit findings · 0 cross-tenant mappings · **0 external-effect rows** |
| **Also reported** | 21 loads billing-ready, 19 quiet, 2 waiting on a human, 7 human touches in total (0.318 per load), 16 loads with zero touches, 29 proposals drafted |
| **Measures** | Complete loads, booked to customer billing-ready, running side by side in one database across two brokerages |
| **Limits** | "Human touches per load" describes how the fixtures were written. **It is not a measured labor saving** and must not be quoted as one. "Proposals" are drafted text; none was sent. |

## 6. The freight-domain spine and work engine

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/run_freight_corpus.py` |
| **Result** | 20 histories · 198 records · 23 canonical loads · 132 external mappings recorded, 122 resolved exactly · 3 ambiguous mappings held for a human · 3 conflicts raised · 23 expectations raised, 6 overdue, 1 indeterminate · 13 reconciliations computed, 4 discrepant · 0 cross-tenant mappings · 0 external-effect rows |
| **Measures** | Twenty deliberately hostile histories across three brokerages in one database |

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/run_freight_corpus.py --work` |
| **Result** | 15 histories · 1,227 state evaluations · 114 raw signals folded into 66 unique needs (48 duplicates suppressed) · 58 labeled checkpoints, 278 labeled checks, none failed |
| **Measures** | Work is derived from its cause, so several rows describing one missing POD are one piece of work |

## 7. Model interpretation

| | |
|---|---|
| **Command** | `.venv/bin/python scripts/run_freight_interpretation_eval.py --stage all` |
| **Mode** | **Replay.** 110 recorded readings from `gpt-6-luna` at low reasoning effort; this run made 0 live calls and spent 0 tokens |
| **Result** | Labeled messages 24/24 fully correct, 209/209 fields · correlation cases 6/6 · commitments 4/4 · the twenty hostile histories fed as **raw text** reached 264/264 labeled outcomes · nine raw-language scenarios 88/88 · per-message agreement with the structured fixtures **20/22** · 5 items dropped by the grounding check · 176 pieces of work settled deterministically without a model, 110 sent to one |
| **Tokens** | 237,821 input and 26,393 output across all recorded readings |
| **Measures** | That typed readings, after grounding and deterministic normalisation, reproduce the labeled outcomes of the corpus |
| **Limits** | Small, synthetic, authored in-house, labeled by the same project, read by one model, and **replayed from recordings** — this run verified the scoring and the replay path, not that the model returns the same readings today. The two disagreements are the model reporting an extra `IN_TRANSIT` status alongside `LOADED`. These numbers show the pipeline is wired correctly. **They are not an accuracy claim about real freight messages.** |

## 8. The case-study bug, before and after

| | |
|---|---|
| **Command** | `.venv/bin/python docs/portfolio/demo/disputed_delivery.py` |
| **On `8ee5bf6`** | Exit 0. After the human's decision the delivery watch is owed again; the missed window is detected at 15:01Z. |
| **On `ee9f6b8`** (same script, isolated export) | Exit 1. The load reads `QUIET`, next step `NOTHING`, from the human's decision through the missed appointment. |
| **Measures** | That the reported defect is real and reproducible, and that the fix changes the behaviour |
| **Limits** | One scenario. The wider regression set is described in the [case study](CASE_STUDY.md). |

| | |
|---|---|
| **Command** | In a temporary directory: `git archive 9359798 eval scripts pyproject.toml \| tar -x`, then `git archive ee9f6b8 src \| tar -x`, then `python -m pytest eval/tests/test_p9_load_loop.py -q` |
| **Result** | **12 failed, 31 passed** |
| **Measures** | The fix commit's tests run against the pre-fix source. The 12 failures are the regressions added with the fix; the 31 passes are the tests that existed before it — the suite was green while the defect was live. |
| **Limits** | Covers the first of three related repairs. The later two (`e1a84f5`, `8ee5bf6`) were not re-run this way; their red-before-fix counts are stated in their commit messages and were not independently reproduced here. |

## 9. Size and history

| | |
|---|---|
| **Commands** | `git rev-list --count HEAD` · `git log --reverse --format=%ad --date=short \| head -1` · `find src -name '*.py' \| xargs cat \| wc -l` |
| **Result** | 434 commits from 2026-06-11 to 2026-10-07 · about 81,000 lines of Python in `src/`, 90,000 in `eval/`, 44,000 in `scripts/` · 19 architecture decision records · 118 canonical event contracts · 23 migrations · 34 mutation batteries |
| **Limits** | Line counts measure volume, not value. **417 of the 434 commits carry an AI co-author trailer**: this codebase was written with AI coding agents under the founder's direction. See [`CAREER_NOTES.md`](CAREER_NOTES.md) for how to describe that accurately. |

---

## Numbers that do not exist

So that nobody goes looking, or invents them:

- No customer, pilot or design-partner usage figures. The repository records no deployment.
- No time-saved, cost-saved, accuracy-in-production or revenue figures.
- No throughput, latency or load-test figures.
- No model accuracy on real freight messages.
- No third-party security audit or penetration test.
