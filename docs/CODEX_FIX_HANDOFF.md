# Neyma — Codex Fix Handoff (review round, `demos` @ 2f2eb14)

Consolidated, de-duplicated findings from four review agents (money-safety spine audit,
phase code review, owner-operator product review, roadmap-steward). Ordered by fix priority.
Each item: exact location, the defect, why it matters, and the fix. **Money-path items P0–P1 must
land before any lane is graduated to unattended/concurrent operation or before a real-money
supervised write is trusted.** The Slack production path is otherwise structurally sound
(signatures, single-use HMAC tokens, channel/thread binding, fail-closed authz, verified-vs-reported
ROI, per-tenant isolation all verified).

Three agents independently flagged the money-field keyword gap and the store-concurrency issue —
treat those as high-confidence, not artifacts.

---

## P0 — must fix before trusting a real-money supervised write

### P0-1 · Resume can double-commit (no cross-run commit-once guard)
- **Where:** `src/freight_recon/operator_agent.py:117` (`self._committed` reset per run),
  `src/freight_recon/thread_reply.py:23,55`, `src/freight_recon/action_callback.py:1032`
- **Defect:** commit-once (`self._committed`) is scoped to a single `agent.run()` and reset to `False`
  every run. Resume builds a *fresh* agent, so the guard starts empty. Trigger (no attacker; a flaky
  TMS causes it): Save succeeds → read-back is slow/fails → model ESCALATEs per its own prompt → the
  record already exists → owner replies "try again" → resume runs a fresh agent with `commit=True` →
  **second identical invoice/payable.** `FAILED` is likewise resumable with the same exposure. The only
  thing preventing the double-write today is the LLM noticing "already exists" — money correctness must
  not rest on LLM judgment.
- **Fix:** deterministic, cross-run commit-once. On a successful consequential action, write a durable
  idempotency claim keyed to `(tenant, lane, load_ref, party, approved_amount)` — reuse the SQLite
  `operation_action_claims` pattern (`workflow.py:450-475`), not a JSON file. Before any resumed/
  re-approved run drives to Save, check the claim and return `DONE` "already committed" if present.
  Also record `committed: true` on the escalation payload when `_committed` was true, and make
  `find_resumable_operation` treat such payloads as **verify-only** (resume may READ-to-confirm, never
  re-Save).

### P0-2 · Money fence only covers 4 field-name keywords
- **Where:** `src/freight_recon/operator_agent.py:72-74` (`is_money_field`)
- **Defect:** substitution of the human-approved amount fires only when the model-chosen `target`
  contains `amount|price|total|charge`. Freight TMSs label money fields `Rate`, `Line Haul`, `Freight`,
  `Settlement`, `Balance Due`, `Cost`, `Pay`, `Value`, `Accessorial`. For any of those the fence is
  skipped and **the model's own number is typed into the money field** — the exact thing the fence
  exists to prevent. Not hit by the two shipped lanes today (goals say "the amount field"), but latent
  the moment a real TMS labels differently.
- **Fix:** invert authority — the fence should validate by **value**, not target-name. Intercept every
  `TYPE` whose value parses as currency/number: substitute the approved amount if the field is the
  lane's designated money field; ESCALATE if it's an unexpected numeric write. Drive the designated
  money-field identity from lane/tenant config (config-over-code), not a hardcoded substring list.
  Add a regression test with a `Rate`/`Line Haul` field.

---

## P1 — fix before graduating any lane to unattended / concurrent runs

### P1-1 · Shared JSON stores race + non-atomic writes (defeats the daily-cap money guardrail)
- **Where:** `src/freight_recon/lane_graduation.py:51`, `knowledge.py:59`, `agent_memory.py:58`,
  `ops_control.py:36` — all plain `path.write_text`; check-then-record at
  `operation_router.py:129` vs `:159`
- **Defect:** the callback spawns a daemon thread per Slack request. Two concurrent autonomous runs of
  a `daily_cap=1` lane can both pass `autonomy_allows` (each reads `runs=0`) before either calls
  `record_autonomous_run` — the check-then-record is not atomic, so the cap (a money guardrail on
  autonomous spend) is exceeded. Separately, non-atomic `write_text` truncates-then-writes: a crash/
  interleave mid-write can silently wipe **all learned facts** (`_read` swallows `ValueError → {}`).
- **Fix:** (1) atomic writes everywhere — temp file in same dir + `os.replace`. (2) Move the daily-cap
  counter into the SQLite store (WAL + `busy_timeout` + atomic claim already exist) so record-and-
  enforce is a single transaction; make it increment-then-check, not check-then-increment.

### P1-2 · Resume trusts the amount from the audit row, not the re-verified signed token
- **Where:** `src/freight_recon/thread_reply.py:51-56`, `action_callback.py:1026,1032`
- **Defect:** the button path re-verifies the approved amount from the HMAC-signed operation token; the
  **resume** path reads the amount out of the `slack_operation_applied` audit payload and commits off a
  self-granted approval. A consequential COMMIT is authorized from a DB row, not the signed artifact the
  human actually approved.
- **Fix:** on resume, re-derive/re-verify the approved amount from the original signed token (persist a
  token-fingerprint→amount binding) and confirm it equals the resumed amount before allowing
  `commit=True`. If they can't be reconciled, resume in verify/prepare mode only.

### P1-3 · Graduation guardrails are dead code on every wired path
- **Where:** `operation_router.py:126-140`, `action_callback.py:940-943,1032`
- **Defect:** the autonomy branch (and all of `lane_graduation.autonomy_allows` — ceiling/allowlist/
  daily-cap) is reachable only when `approve is None`, but both wired call sites always pass an explicit
  `approve`. So the advertised guardrails never evaluate in production. Fail-safe today (everything
  treated as supervised), but the guardrails provide zero enforcement.
- **Fix:** decide intent. If graduation is meant to be live, add an autonomous entry point that calls
  `router.run(intent)` with `approve=None` and enforce the cap atomically (P1-1). If not yet live, mark
  it clearly as unwired so it isn't mistaken for an active control.

---

## P2 — correctness / invariant-hardening (not money-decision holes, but soften stated invariants)

### P2-1 · Live drive CLI crashes — `build_agent` missing `prepare_only`
- **Where:** `scripts/run_operate_request.py:80`
- **Defect:** `OperationRouter.run` always calls `build_agent(..., prepare_only=prepare_only)` but this
  CLI's factory is `(*, approved_amount=None, approve=None)` → `TypeError` on every invocation.
  Reproduced directly. Not the Slack production path; it's the documented single-command live-drive tool.
- **Fix:** add `prepare_only: bool = False` to the signature and pass it through. **Add a smoke test that
  constructs the router with each real `build_agent` factory and asserts the signature accepts
  `prepare_only`** (this class of drift is what let it rot).

### P2-2 · NL operate parses the amount from model-rewritten text
- **Where:** `action_callback.py:681,1102,1155` (`_extract_command_amount` on `routed["operate"]`),
  `nl_command.py:43`
- **Defect:** `interpret_slash` returns the request as the model's paraphrase; the amount on the approval
  button is then extracted from that model string. Still human-gated (owner taps Approve), but amount
  provenance is softened — a model that alters a number would surface it.
- **Fix:** extract the amount from the **original owner text**, never the routed paraphrase. Add a test:
  a model reply that injects an amount into `request` must not become the proposed amount.

### P2-3 · Correction loop stores raw reply text (can contain a dollar figure) as a fact
- **Where:** `action_callback.py:1008` (`_learn_correction`)
- **Defect:** persists `operator_guidance` (raw Slack reply) verbatim as a BUSINESS fact. "it's order
  1002, pay $4,500" is stored as-is, contradicting the "facts carry no amounts" invariant. Never *used*
  as an amount (fence still substitutes only the approved figure), so not a money hole — a data-invariant
  leak. Recipes and derived SYSTEM facts already strip values; only this free-text path leaks.
- **Fix:** redact currency tokens before learning (or only learn corrections matching an entity-mapping
  shape and drop amounts). Test: a reply containing "$" yields a fact with the amount removed.

### P2-4 · `find_resumable_operation` is thread-scoped, not action-scoped
- **Where:** `thread_reply.py:36-42`
- **Defect:** "last match wins" across all events in a `thread_ts`. Two ops in one thread → a reply
  resumes whichever escalated last. Combined with P0-1, widens wrong-op / already-committed resume.
- **Fix:** scope resumability to a specific `action_id`; exclude any op whose commit already succeeded
  (P0-1 fix).

---

## P3 — tests / nits

- **Pin the anti-double-pay invariant with tests** (`operator_agent.py:170`): (a) actuator fails the
  first Save click then succeeds → assert ONE approval call, agent reaches DONE; (b) model emits a second
  consequential action after a successful commit → assert no second click, status DONE.
- **Multi-tenant TODO:** the correction/learn paths hardcode `tenant="default"`
  (`action_callback.py:1009`). Fine for single-tenant dogfood; thread the real tenant before multi-tenant.
- **ROI hours-saved estimate** sits next to real recovered dollars (`roi_ledger.py:196`) — keep, but
  render it below the dollars and let the owner tune minutes-per-task, so a rich-looking estimate never
  makes the (honest) dollar figure look soft.

---

## Product asks (owner-operator — NOT safety; schedule separately, do not let them block P0–P1)

These turn Neyma from "smart button" into "biller" on the path the owner actually types into. Verdict was
APPROVED WITH NITS — he'd run it daily supervised now.

1. **Feed the rate-con/load amount into the NL/slash operate path.** Today "invoice the Northbound load"
   routes correctly but then asks the owner to type the amount. The deterministic rate-con-derived amount
   already exists on the AP auto-propose path (`operation_proposal.py:110`,
   `proposals_for_clean_matches`) — reuse it so the owner approves a number Neyma *found*, not one he keys.
2. **Add the AR (customer-invoice) half of the auto-propose loop:** clean delivered load + POD → "Invoice
   customer $X [Approve & run]", amount from the load. Turn `--propose-clean-payables` (and the new AR
   equivalent) **on by default** in supervised mode. This is the DSO/cash win; today the hands-off loop
   only closes on AP.
3. **Put approval-decision evidence on the receipt/card:** which load record it wrote to (the ref read
   back — guards wrong-load attachment, which the money fence does not cover), the rate-con authorization
   basis for any accessorial/detention, and a **factoring/NOA flag** on the carrier (paying a factored
   carrier direct = pay the wrong party, eat it twice) — force human review before any payable on a
   factored carrier.

---

## How to verify a fix landed
- Targeted suites: `.venv/bin/python -m pytest eval/tests/test_{operator_agent,operation_router,lane_graduation,thread_reply,roi_ledger,action_callback,knowledge}.py -q`
- Repro that must now pass: constructing `OperationRouter` against each real `build_agent` factory
  accepts `prepare_only` (P2-1).
- New regressions to add: P0-1 (resume-after-commit refuses re-Save), P0-2 (`Rate`/`Line Haul` field
  fenced), P1-1 (concurrent daily-cap runs cannot exceed cap), P2-2/P2-3 (amount provenance / currency
  scrub), P3 (commit-once + failed-commit-retry).
- Do not weaken any existing money-path assertion to make a fix pass.
