# Live-Write Proof — the one gate to Finish Line 1

**Goal:** complete ONE clean end-to-end write in a live TMS: a Slack-approved operation the agent
prepares (fills the form, stops before Save), the human commits, and the agent reads the saved record
back — receipt shows `DONE (verified)` with the real record number. Supervised. One load. Once.

**Why it's the gate:** everything else (engine, safety spine, Watch front door, learning) is built and
green in tests but unproven against a real TMS. Until this happens once, the product is a demo. After
it, you can honestly put it in front of a design partner.

---

## Pre-flight (done — findings)

The new commit-once guard needs `load_ref` **and** `party` on the intent to allow a commit (else it
fail-closes: *"missing load reference or party for commit-once protection"*). Traced end-to-end:

| Path | Carries `load_ref` | Carries `party` | Safe to commit? |
|---|---|---|---|
| **Manual `propose_operation_to_slack.py`** (`--customer/--carrier` + `--load-ref`) | ✅ | ✅ | **YES — use this for the first proof** |
| **AP clean-payable auto-propose** (`proposals_for_clean_matches`) | ✅ | ✅ (carrier) | YES |
| **AR invoice auto-propose** (Inbox Brain `proposal_from_assessment`) | ✅ | ❌ (no customer) | NO — fail-closes. Follow-up: thread `customer` through `InboxAssessment`. |

The signed approval token encodes the full `intent` (`model_dump`), so `params` round-trip through
Approve → verify → `router.run`. Confirmed: the manual and AP paths reach `_commit_identity` complete.

**Decision:** run the first proof via `propose_operation_to_slack.py` — you control lane, party,
load-ref, and amount explicitly; nothing relies on auto-propose or extraction.

---

## The go-sequence

### 1. Chrome logged into the TMS, with CDP open
Start Chrome with remote debugging and log into the TMS yourself (Neyma attaches; it never logs in):
```bash
# macOS example — use a dedicated profile so it doesn't collide with your normal Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/neyma-cdp-profile
```
Navigate to the TMS and log in. Confirm CDP is up: `curl -s http://localhost:9222/json/version` returns JSON.

### 2. Callback server with the operation router (supervised = prepare-then-commit)
```bash
.venv/bin/python scripts/run_action_callback_server.py \
  --workspace data/active_workspace/gmail_to_slack \
  --db data/active_workspace/gmail_to_slack/workflow.sqlite3 \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --port 8001 \
  --enable-operation-router \
  --allowed-slack-user U0BBZ5RS9G8 \
  --allowed-slack-channel C0BB8KG21J8 \
  --operation-cdp-url http://localhost:9222 \
  --operation-url-filter <tms-domain-substring> \
  --operation-model gpt-5.5 \
  --operation-max-steps 40
```
- `--operation-url-filter` (e.g. `transporters` or `truckingoffice`) pins the agent to the right tab.
- `--operation-model gpt-5.5` is now the default (the purpose-built agentic driver); the flag is
  explicit here only for clarity. `--operation-max-steps 40` is the default too — enough headroom for a
  cold run that orients on an unfamiliar TMS and drives a multi-step flow without a false cut-off.
- No prepare flag needed: with a graduation policy present and the lane ungraduated, a money lane
  **prepares** by default (fills, stops before Save). You commit.

### 3. Tunnel + Slack interactivity URL
Tunnel `http://127.0.0.1:8001` (ngrok), set Slack Interactivity Request URL to `<tunnel-url>/slack/actions`
and the Events Request URL to `<tunnel-url>/slack/events` (the thread-reply commit path).

### 4. Post the proposal (you pick the load + amount)
```bash
.venv/bin/python scripts/propose_operation_to_slack.py \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --channel C0BB8KG21J8 \
  --lane record_payable \
  --carrier "<carrier name exactly as in the TMS>" \
  --load-ref "<load/order ref, e.g. LD-560001>" \
  --amount <the rate-con/agreed amount, e.g. 2850.00>
```
For an AR invoice instead: `--lane raise_invoice --customer "<customer>"` (same `--load-ref`/`--amount`).
The amount is the human-approved figure — the model never chooses it.

### 5. Approve → it prepares → you commit
- Tap **Approve & run** in Slack. The agent drives the TMS and **stops before Save** (PREPARED —
  "everything is staged; reply 'submit' to commit").
- Look at the staged form in the TMS. If it's right, reply **`submit`** in the thread. The agent clicks
  Save, then READs the saved record back.
- Receipt should read `✅ Done — <record #>, $<amount> (verified)`.

---

## Success / abort criteria

**Success:** receipt says `DONE (verified)` AND you can see the record in the TMS with the right party,
load, and amount. The commit-once claim now exists — a repeat approval returns `DONE` "refusing to
repeat," which is the safety working.

**Abort / expected safe stops (not failures):**
- `PREPARED` and it looks wrong → do NOT reply submit; reply with a correction or fix the load, re-run.
- `ESCALATED — missing load reference or party` → the proposal didn't carry both; re-post via the manual
  script with `--carrier/--customer` + `--load-ref` (see pre-flight table).
- `ESCALATED — needs approval` on an amount → the money fence working; the amount wasn't bound.
- Readback mismatch → lands `FAILED`, never a false `DONE`. That's the verify gate doing its job.

**Watch for:** wrong-load attachment (right amount, wrong load). The receipt shows the record it wrote;
confirm the load ref on it matches what you intended before trusting it.

---

## Follow-ups this proof surfaces (not blockers)
- AR invoice auto-propose fail-closes on missing `party` — thread `customer` through `InboxAssessment` /
  `proposal_from_assessment` so the hands-off AR loop works (the owner-operator DSO ask).
- `parse_eml` chokes on RFC2047-encoded subjects — fix before activating triage on a real inbox.
