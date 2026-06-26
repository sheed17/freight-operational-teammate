# Session Handoff — Neyma Freight Ops Engine

> **Purpose:** single source of truth when switching between Claude Code and Codex, so there is no
> confusion about what was done and what's next. **Update this at the end of every working session.**
> Append a dated entry to the log; keep the top "Current State" and "Next Up" sections current.

**Last updated:** 2026-06-19 (Claude Code session)

---

## TL;DR — where we are right now

- **Channels are LIVE and proven.** Real Slack posting + real Gmail SMTP send both confirmed end-to-end
  to the user's real workspace/inbox. Channel roles are locked: **Slack = headless UI (only human
  review/approval surface); email = inbound intake + carrier-facing follow-up only — the user is
  never emailed a review card.**
- **Stage 1 extraction gate PASSED on real GPT-4o.** Switched extraction to OpenAI
  (`EXTRACTION_PROVIDER=openai`, `OPENAI_MODEL=gpt-4o`). Full corpus (clean+dirty) cleared the four
  gate numbers — saved at `eval/results/real_20260618.json`. ⚠️ It scored 100%, which is
  *suspiciously perfect* — the synthetic "dirty" variants likely under-stress the model. This clears
  the **development** gate; the **production** gate is still real client invoices (golden set, not built).
- **Real extraction is now wired into the reconciliation loop (one entrypoint).**
  `src/freight_recon/extraction_bridge.py` + an optional `extractor=` param on
  `workflow.process_load_packet` make the loop run on *real* GPT-4o extractions with a confidence
  gate. **Default stays ground-truth** (so all tests stay deterministic + $0).

## Decision locked: "zero-API vs API" → the injection seam (use both by context)

- **Tests / CI / dev → zero-API** (default `extractor=None`, ground-truth). Keeps the suite fast,
  free, deterministic; the money logic is tested in isolation.
- **Production / operating → real API** (inject `extractor=lambda p: extract_from_pdf(p, cfg)`).
- The same `process_load_packet` code path serves both via the injected `extractor` parameter.

---

## Current State (built + proven)

| Layer | Status | Key files |
|---|---|---|
| Extraction (Stage 1) | ✅ gate PASSED on GPT-4o (dev/synthetic) | `eval/run_corpus_eval.py`, `eval/extraction.py` (now provider-aware), `src/freight_recon/extraction.py`, `eval/results/real_20260618.json` |
| **Real extraction → reconciliation wiring** | ✅ `process_load_packet` only; ⛔ `mailbox_workflow` NOT yet | `src/freight_recon/extraction_bridge.py`, `src/freight_recon/workflow.py`, `eval/tests/test_extraction_bridge.py` (8 tests) |
| Inbound mailbox spine (Stage 2) | ✅ local `.eml` watcher → ingest → workflow | `src/freight_recon/mailbox_intake.py`, `mailbox_workflow.py` |
| Ingestion (classify + link) | ✅ deterministic, scored vs hidden truth | `src/freight_recon/ingestion.py`, `email_corpus.py` |
| Reconciliation (Stage 3) | ✅ deterministic | `src/freight_recon/reconciliation.py` |
| Workflow / audit / idempotency (Stage 4) | ✅ + tool-permission registry | `src/freight_recon/workflow.py`, `tool_permissions.py` |
| Slack (headless UI, Stage 5) | ✅ LIVE posting proven; `/slack/actions` interactivity built | `slack_adapter.py`, `delivery_dispatch.py`, `action_callback.py` |
| Email transport | ✅ gated SMTP send proven (carrier-facing); user-review email DISABLED by contract | `email_adapter.py`, config `email.enabled: false` |
| TMS write (Stage 7) | ✅ MOCK only: confirm-before-submit + readback + idempotency + gated | `tms_write.py` |
| Browser-use / real TMS | ⛔ read-only skeleton vs mock only | `browser_use_adapter.py`, `screen_mapping.py`, `docs/ASCENDTMS_MAPPING.md` |

**Test suite:** ~222 tests (214 prior + 8 extraction-bridge). Confirm with `.venv/bin/python -m pytest eval/tests -q`.

**Agents available (`.claude/agents/` + `.codex/agents/`):** `intent-mapper`, `owner-operator-reviewer`,
`phase-code-reviewer`, `build-supervisor` / `principal-architect-supervisor`, `roadmap-steward`.
Spawn `phase-code-reviewer` + `owner-operator-reviewer` after each slice; `roadmap-steward` for direction.

---

## NEXT UP (prioritized) — updated after owner-operator review (CHANGES REQUESTED)

The extraction-wiring slice (`extraction_bridge.py` + `process_load_packet`) is architecturally
clean and tested, BUT the owner-operator review found it does not yet *deliver* to the human. Fix
A–D to make it real, then E–G for production.

**A. ✅ DONE — the Slack card renders the EXTRACTED billed values.** `process_load_packet` now
persists the extracted invoice side (`extracted_invoice` in the `extraction_recorded` audit event via
`extraction_bridge.serialize_invoice_side`), and `review.review_load_for_run(store, run, source_load)`
overlays it onto the load the card is built from (`apply_extracted_invoice`). The two card call sites
(`run_review.py`, `mailbox_workflow.py`) now call `review_load_for_run` first, so fields + variance +
money buttons reflect the real read. Ground-truth path (no extraction event) returns the load
unchanged. Tests: `test_review_card_renders_extracted_billed_values_not_source`,
`test_ground_truth_path_review_load_is_unchanged`.

**B. 🔴 BLOCKER (NEXT): wire `mailbox_workflow.py` real-extraction.** It has its own reconcile paths —
RECEIVED branch ~138–152 (stamps `source: "mailbox_packet_ground_truth"`) and refresh/trickle branch
~153–165 (`refresh_reconciliation`). The pilot/first-design-partner runner go through mailbox_workflow,
NOT process_load_packet. **Detail uncovered:** a mailbox packet's carrier-invoice PDF is an *embedded
attachment inside the preserved `.eml`* (`MailboxPacketRun.preserved_path` → `parse_eml` → attachments),
NOT a clean file path. Recommended approach:
  1. Refactor the real-extraction core out of `process_load_packet` into a shared helper (persist
     `extracted_invoice` → reconcile → confidence/link/total gate → `mark_reconciled`/`refresh_reconciliation`).
  2. Add `extractor=` to `run_mailbox_workflow`; resolve the carrier-invoice attachment bytes from the
     packet's `.eml` (write to temp PDF) and call the extractor; reuse the shared helper in both branches.
  3. Tests with an injected fake extractor (no API), incl. a trickle packet that resolves on a later email.

**C. ✅ DONE — carrier STATED total reconciled vs line items.** `process_load_packet` now compares the
extracted `total_amount` against `linehaul + fuel + accessorials`; mismatch > $0.01 forces NEEDS_REVIEW
with a clear reason. (Also confirmed independently by phase-code-reviewer as the pre-existing recon gap.)
Test: `test_total_inconsistent_with_line_items_forces_review`. **Carry this same check into mailbox (B).**

**D. 🟡 Surface per-field confidence + a prominent evidence link on the card.** The gate reason
reaches the card as a string, but the controller can't see WHICH field is shaky. Add an optional
per-field "uncertain"/confidence to `ReviewField`; show the carrier-invoice evidence link when the
gate fires.

**E. `--real-extraction` flag on `scripts/run_dogfood_pilot.py` / `run_first_design_partner.py`**
injecting `lambda p: extract_from_pdf(p, load_doc_type_config('carrier_invoice'))` so operating uses
GPT-4o end-to-end. (Depends on B.)

**F. ⛐ Production extraction gate on REAL invoices** — golden-set intake (`eval/add_to_golden_set.py`)
for real/Rasheed-approved invoices. The synthetic 100% is NOT the production gate. *(Needs real PDFs.)*

**G. ⛐ Browser-use on a real/sandbox TMS** — graduate `browser_use_adapter` from mock: read-only
first (verify-by-readback), then the gated write path. *(Needs sandbox TMS + human session + screen map.)*

**Operational/parallel:** ngrok the Slack click loop (`run_action_callback_server.py --client-config …`
+ Slack Interactivity URL `<ngrok>/slack/actions`); live Gmail/IMAP mailbox watcher; deployment
packaging (Docker + hosted callback ingress + secrets). Also close the field-dialect doc note in
AGENTS.md (bridge already normalizes for the link check) and align model-name docs (GPT-4o vs the
Anthropic default in MODEL_STRATEGY).

> **Critical path:** A → B → C/D (extraction actually delivers to the human) → E (operate on real
> extraction) → F → G (cross into production on real data + real TMS). Do NOT claim "the card shows
> what the carrier actually billed" until A lands.

## Open items / gotchas (don't trip on these)

- **`mailbox_workflow` is still ground-truth** — the live pilot does NOT yet extract for real. (Item 2.)
- **The 100% Stage-1 result is on synthetic docs.** Do not claim production-ready extraction.
- **`.env` holds live secrets** (Slack signing/bot tokens, `NEYMA_DELIVERY_SECRET_RASHEED_FIRST`, Gmail
  app password, `OPENAI_API_KEY`). Scripts do NOT auto-load `.env` — run `set -a; source .env; set +a`
  first. Gmail app password must be 16 chars **no spaces** or `source .env` breaks.
- **Outbound stays gated/off by default** in committed config. Live dispatch is always explicit.
- **Slack button clicks need ngrok** (posting works without it).

## How to run / verify

```bash
set -a; source .env; set +a                                   # load live secrets (scripts don't auto-load)
.venv/bin/python -m pytest eval/tests -q                      # full suite (zero API)
.venv/bin/python eval/run_corpus_eval.py --save eval/results/real_$(date +%Y%m%d).json   # real Stage 1 gate (OpenAI; spends $)
.venv/bin/python scripts/verify_first_design_partner_slack.py # Slack preflight (expect ready: true)
.venv/bin/python scripts/run_dogfood_pilot.py --text          # local end-to-end pilot (ground-truth)
```

## Conventions (keep consistent across Claude/Codex)

- Pydantic models everywhere; deterministic Python owns money/state; outbound + TMS-write gated + audited.
- New capability = module in `src/freight_recon/` + `scripts/` CLI + `eval/tests/` test + doc update.
- No model spend except extraction; keep tests zero-API via dependency injection.
- After each slice: `phase-code-reviewer` (code/safety) + `owner-operator-reviewer` (value/trust);
  `roadmap-steward` for "where are we / what next."

---

## Session log

### 2026-06-24 (Claude Code) — LIVE PRODUCT RUN + convergence note
- **Convergence:** while Claude built A+C, Codex (parallel) refactored them into a shared
  `extraction_bridge.reconciliation_from_extraction` (extracted_invoice persist + total-mismatch +
  confidence/link gate + fail-closed on malformed extraction), used by BOTH `process_load_packet`
  and `mailbox_workflow`. Codex also added: real IMAP pull (`imap_mailbox.py`), Gmail discovery
  (`inbox_discovery.py`), vision doc-linking (`document_identifier.py`), and the full product runner
  `scripts/run_gmail_to_slack_dogfood.py`. So **Builds A, B, C, E are DONE** on the real-product path.
  Suite green at **240**. workflow.py clean (no collision; `_decimal_or` lives in the bridge now).
- **LIVE END-TO-END RUN against the user's real Gmail (rsamady2@gmail.com):**
  `run_gmail_to_slack_dogfood.py --client-config rasheed_first_design_partner.yaml --real-extraction
  --provider openai --mailbox "Neyma-Test-Inbox" --query ALL --dispatch-mode LIVE`.
  - ⚠️ Pull from an **isolated Gmail label `Neyma-Test-Inbox`** (already seeded with 9 corpus emails) —
    NOT INBOX (INBOX has 55k unread real mail; never pull from it).
  - Real GPT-4o read the invoices; **LD-560004 caught a real fuel overbill: invoice $572 vs rate $447
    → VARIANCE/NEEDS_REVIEW**, card renders the extracted $572 (Build A live). Fail-safes worked
    (LD-560003 had 4 ambiguous invoices → held without extracting; 3 dirty docs → unlinked).
  - **4/5 review cards posted live** to review channel `C0BB8KG21J8`.
  - **1 failure:** LD-560003 routed to DIGEST channel `C08M7N494M1` → `channel_not_found` (the bot is
    NOT a member of the digest channel). Fix: invite the bot to `C08M7N494M1`, or collapse routing.
  - Flipped `slack.outbound_enabled: true` in `configs/clients/rasheed_first_design_partner.yaml` for
    the live pilot (carrier email stays gated). Flip back to `false` to re-arm the off-by-default gate.
- **SLACK CLICK LOOP CLOSED (live):** started `run_action_callback_server.py` (--db the gmail_to_slack
  workspace, --client-config rasheed) + a **cloudflared** tunnel (`brew install cloudflared`;
  `cloudflared tunnel --url http://127.0.0.1:8000` → trycloudflare URL). Set the Slack app Interactivity
  Request URL to `<tunnel>/slack/actions`. User clicked **Approve-Expected** on the LD-560004 card →
  signed action verified (Slack sig + single-use token) → applied → **LD-560004 APPROVED at the agreed
  $447 (the $125 overbill corrected)**. Follow-up **Approve-Full** click → `delivery_action_rejected`
  (run already decided); repeat click → `delivery_action_duplicate` (single-use). All audited.
  ⚠️ The trycloudflare URL is ephemeral (dies with the tunnel process) — re-tunnel + re-set the Slack
  URL next session, or stand up stable ingress.
- **Canonical loop now runs on real infra end-to-end EXCEPT execution.** Only remaining piece:
- **G IN PROGRESS — browser-use proven live.** Locked-in agent: `browser-use` 0.13.1 (installed;
  Chromium present). **Validated live in our stack:** real Chromium + `browser_use.beta.Agent` +
  `browser_use.ChatOpenAI(model="gpt-4o-mini")` read the mock TMS LD-560004 page and returned the
  correct carrier — **no `BROWSER_USE_API_KEY` needed** (uses `OPENAI_API_KEY`). Note: `gpt-4o` threw
  a transient `provider error`; `gpt-4o-mini` worked. Mock TMS site: `scripts/generate_mock_tms.py
  --corpus data/synthetic_corpus --db <gmail_to_slack db> --out <site>`; served on :8011.
  - Existing: `browser_use_adapter.py` is READ-ONLY (gated, audited; tasks say "do not write").
    `tms_write.py` `enter_approved_payable()` is the gated WRITE spine (APPROVED → prepare
    [confirm-before-submit] → submit → verify-by-readback → DONE) but writes to a JSON
    `MockTmsWriteLedger`, NOT through the browser. `enter_tms_payable.py` runs it.
  - **Remaining G build (next slice, money path → run reviewers):** (1) a *writable* mock TMS (form +
    stateful POST backend) so browser-use can enter a payable and read it back; (2) a BrowserUse write
    ledger implementing `write_payable`/`get_payable` (same seam as `MockTmsWriteLedger`, incl.
    idempotency/duplicate logic) that drives browser-use; (3) wire into `enter_approved_payable` via a
    `--browser` flag; tests with an injected fake `BrowserUseRunner` (no live browser). Then run:
    execute APPROVED LD-560004 @ $447 through the browser → readback → DONE.
  - The `NativeBrowserUseRunner` currently hardcodes `ChatBrowserUse()` (needs the missing key) — wire
    it to use `ChatOpenAI` when `BROWSER_USE_API_KEY` is absent.
- **G EXECUTION BUILT + TESTED; live write blocked on the browser-use model.** New this session:
  - `src/freight_recon/mock_tms_write_server.py` — a *writable* mock TMS (payable entry form + POST +
    readback table) that delegates writes to the proven `MockTmsWriteLedger` (idempotency/duplicate
    are the tested code). HTTP-verified: WRITTEN / IDEMPOTENT_REPLAY / DUPLICATE_BLOCKED.
    Run: `python -m freight_recon.mock_tms_write_server --site <mock_tms> --ledger <json> --port 8012`.
  - `browser_use_adapter.BrowserUseWriteLedger` — drives browser-use to type the approved amount +
    submit + read back, implementing the same `write_payable`/`get_payable` seam so the gated
    `enter_approved_payable` path drives the browser UNCHANGED. `NativeBrowserUseRunner` now uses
    `ChatOpenAI` when `BROWSER_USE_API_KEY` is absent.
  - `enter_tms_payable.py --browser --base-url ...` runs the gated write through the browser.
  - Tests: `eval/tests/test_browser_use_write.py` (5, fake runner) — confirm-before-submit,
    verify-by-readback, readback-mismatch→FAILED, fail-closed on unknown status. 19 TMS/browser tests green.
  - **MODEL FIX (no fork, no browser-use key):** model sweep settled it — `gpt-4.1-mini` reliably
    operates the form; `gpt-4o`/`gpt-4.1` throw the browser-use Rust-SDK `provider error`;
    `gpt-4o-mini` flails. `NativeBrowserUseRunner` now defaults to `gpt-4.1-mini`. Agent stack:
    **open-source `browser-use` 0.13.1 pip package (NOT forked) + local Chromium (Playwright) +
    OpenAI `gpt-4.1-mini` via `ChatOpenAI` + `OPENAI_API_KEY`. No `BROWSER_USE_API_KEY`, no cloud.**
  - Robustness: agent status-text reads are fuzzy, so `write_payable` falls back to the deterministic
    table readback when the status string is unknown (verify-by-readback still independently checks
    the amount before DONE). Confirmation page renders status as a prominent heading.
- **🎉 G COMPLETE — FULL CANONICAL LOOP CLOSED LIVE.** Ran
  `enter_tms_payable.py 2 --amount 4172.00 --browser --base-url http://127.0.0.1:8012 --db <gmail db>`:
  real Chromium + `gpt-4.1-mini` typed **$4172.00** into the TMS payable form, submitted, a second
  browser pass read it back (`verify:match=True`), run **LD-560004 → DONE**. Ledger:
  `LD-560004 = 4172.00, ref PV-12EABD82`. Trace: APPROVED→READY_FOR_ENTRY→prepared→ENTERING→
  submit:WRITTEN→verify:match=True→ENTERED→DONE. Fully audited (tms_write_prepared/submitted/verified).
  **End-to-end on real infra:** Gmail → GPT-4o extract → reconcile → live Slack → human Approve click
  → browser enters payable in TMS → readback verified → DONE.
  - NOTE: to re-run, reset the run state ENTERING/DONE → APPROVED via direct SQL
    (`UPDATE workflow_runs SET state='APPROVED' WHERE id=2`); the state machine forbids those
    transitions by design. Restart the writable TMS with a clean ledger first.
- **G reviewers done:** phase-code = CHANGES REQUESTED (fix-first); owner-operator = APPROVED WITH NITS.
  Both: architecture sound, fails safe (deterministic owns money, confirm-before-submit, readback-blocks-
  DONE, idempotency, audit all hold through the browser seam). **Two fix-firsts BEFORE a real TMS:**
  1. **Approved-amount binding (owner #1, deepest).** `enter_approved_payable(amount=...)` trusts the
     CLI `--amount`; nothing proves it equals the amount approved in Slack for that run. Fix: persist
     `approved_amount` on the run at the NEEDS_REVIEW→APPROVED transition (from the Slack action
     payload) and make `enter_approved_payable` use/enforce it — refuse/FAILED if `--amount` disagrees.
     CLI `--amount` becomes at most an assertion, never the authority.
  2. **Duplicate-mask in the fuzzy-status fallback (phase #1).** `BrowserUseWriteLedger.write_payable`
     infers WRITTEN from mere row existence on an unparseable status; a same-amount prior payable could
     mask a `DUPLICATE_BLOCKED`. Fix: add `idempotency_key` to the readback table
     (`render_payables_table`) and require it to match THIS submit's key before calling it WRITTEN.
  Plus NITs: amount range validation; status-fidelity ("WRITTEN (inferred)"); tests for
  DUPLICATE_BLOCKED/SESSION_EXPIRED round-trip through the browser seam; doc the slice in AGENTS.md.
  (Reverted `outbound_enabled` to false in the rasheed config — off-by-default; flip at runtime to post live.)
- **Still open:** the two G fix-firsts above (before real TMS); D (per-field confidence + evidence link
  on card); F (real-doc golden gate); fix digest channel `C08M7N494M1` (bot not a member); real/sandbox
  TMS swap (base_url + screen map + human-established session — currently mock only).

### 2026-06-18 → 06-19 (Claude Code)
- Locked channel roles (Slack=headless UI, email=inbound/carrier) across docs + rasheed config (`email.enabled: false`).
- Proved LIVE Slack post + LIVE Gmail SMTP send to the real workspace/inbox.
- Built gated SMTP transport (`email_adapter.SmtpEmailSender` + `delivery_dispatch` LIVE) + tests; added `/slack/actions` interactivity endpoint + security hardening (audited rejections, generic errors, 404 disabled).
- **Roadmap-steward finding:** operational loop was reading ground truth, not extracting → Stage 1 unproven.
- Switched extraction to OpenAI; **made `eval/extraction.py` provider-aware** (was Anthropic-only — the real bug); **Stage 1 gate PASSED on GPT-4o** (`eval/results/real_20260618.json`).
- Built `extraction_bridge.py` + optional real-extractor path in `process_load_packet` + 8 tests (clean→DONE, variance→review, low-confidence→review, link-mismatch→review, extraction-error→review). Default stays ground-truth.
- **Not finished (interrupted):** reviewers on the slice; `mailbox_workflow` real-extraction wiring; pilot `--real-extraction` flag.
