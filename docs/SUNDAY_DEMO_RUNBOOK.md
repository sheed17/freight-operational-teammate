# Sunday Design-Partner Systems Demo Runbook

Goal: show the connected Neyma operating loop, not a dashboard:

```text
controlled inbox/email intake
-> document packet classification/linking
-> carrier invoice extraction/reconciliation
-> Slack review message with evidence
-> signed human action intake
-> safe TMS execution/readback on mock/reference TMS
-> audit/report
```

This is a supervised systems demo. Real TMS writes stay disabled. The TMS execution shown on Sunday
is against the local writable mock TMS or read-only AscendTMS/reference mapping, not a customer's
production system.

## Blessed Local Rehearsal

Run this before the meeting:

```bash
.venv/bin/python scripts/run_sunday_readiness.py --source synthetic --dispatch-mode LOCAL_OUTBOX --text
```

Expected result:

- `Ready: yes`
- focused integration tests pass
- review messages are created
- signed action loop applies
- mock TMS readback verifies
- mock TMS write reaches `DONE`
- report written to `data/active_workspace/sunday_readiness/sunday_readiness_report.json`

Serve the evidence site:

```bash
.venv/bin/python -m http.server 8000 --directory data/active_workspace/sunday_readiness/site
```

Open:

- `http://localhost:8000/operator/index.html`
- packet pages linked from the Sunday readiness report
- mock TMS pages under `http://localhost:8000/tms/`

## Concrete Sunday Walkthrough

Use the examples printed under `Operator Coverage` in the readiness report. With the default seed,
the strongest story is usually:

- Start with the operator console to show the daily work queue, not a dashboard-first product.
- Open the unauthorized accessorial example, usually `LD-560003`: show the detention/accessorial
  mismatch, the invoice evidence, the rate-con evidence, and the wrong-load/extraneous attachment.
- Open the duplicate invoice example, usually `LD-560007`: show why Neyma blocks payable entry until
  a human marks it duplicate or disputes it.
- Open the missing POD/backup example, usually `LD-560005` or `LD-560008`: show that the packet is
  not silently cleared when required backup is missing.
- Open the follow-up draft artifact from the report: show that `Dispute` and `Request Backup` lead
  to drafted carrier-facing work behind a send gate.
- Open the TMS write drill artifact: show that approved money reaches `DONE` only after mock TMS
  readback verifies the amount. State plainly that real TMS writes remain disabled.

## Controlled Gmail/Slack Rehearsal

Use only the controlled Gmail label. Do not point the runner at the full inbox.

```bash
.venv/bin/python scripts/run_sunday_readiness.py \
  --source gmail \
  --mailbox Neyma-Test-Inbox \
  --query ALL \
  --limit 20 \
  --real-extraction \
  --vision-linking \
  --provider openai \
  --model gpt-4o \
  --dispatch-mode DRY_RUN \
  --text
```

For live Slack posting, first verify Slack:

```bash
.venv/bin/python scripts/verify_first_design_partner_slack.py \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --json
```

Then run:

```bash
.venv/bin/python scripts/run_sunday_readiness.py \
  --source gmail \
  --mailbox Neyma-Test-Inbox \
  --query ALL \
  --limit 20 \
  --real-extraction \
  --vision-linking \
  --provider openai \
  --model gpt-4o \
  --dispatch-mode LIVE \
  --text
```

Live Slack button clicks require a callback tunnel:

```bash
.venv/bin/python scripts/run_action_callback_server.py \
  --workspace data/active_workspace/gmail_to_slack \
  --db data/active_workspace/gmail_to_slack/workflow.sqlite3 \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --port 8001
```

Tunnel `http://127.0.0.1:8001`, then set Slack Interactivity Request URL to:

```text
<tunnel-url>/slack/actions
```

## What To Say On Sunday

- Neyma lives where work arrives: the inbox.
- Slack is the human control surface for exceptions, approvals, and evidence.
- The packet page is the evidence canvas for anything the Slack card should not cram into a message.
- Money decisions are deterministic and human-gated.
- Browser/API/TMS execution happens only after approval, and completion requires readback verification.
- The real-client-specific work after Sunday is screen mapping, document quirks, SOP rules, and the
  exact TMS/API path for the slices he shows us.

## What Not To Claim Yet

- Do not claim production-ready extraction on arbitrary real freight documents.
- Do not claim autonomous real TMS writes.
- Do not claim Neyma already knows every trucking document workflow.
- Do not run against a broad real inbox.

## Sunday Acceptance Gate

The system is ready for the conversation when `run_sunday_readiness.py` reports:

- `focused_tests` passed
- Slack preflight passed or live Slack is intentionally disabled
- packet pages exist
- at least one review message exists
- a signed action applies
- mock TMS readback verifies
- mock TMS write verifies
