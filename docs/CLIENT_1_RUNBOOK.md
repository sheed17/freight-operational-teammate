# Client-1 Runbook — running Neyma for yourself, supervised, and iterating

You are the first client. Run it on real work, supervised, and we harden it from your feedback. This
is the whole daily loop, kept short.

## Start / stop
- **Start:** `./scripts/run_client1.sh` (keep the terminal open — you'll see the logs).
- **Stop:** `Ctrl-C` (stops the whole teammate cleanly).
- Prereqs each time: Chrome up on `--remote-debugging-port=9222` and **logged into TruckingOffice**;
  `.env` present. If a child crashes, it **self-heals** (restarts with backoff) — you don't babysit crashes.
- POD safety: the default keeps the POD gate ON. Neyma checks the load list, then the load detail/docs
  area for POD or signed BOL. If it cannot prove delivery, it posts a POD exception instead of a money
  button. For a controlled demo only, run `NEYMA_CLIENT1_ALLOW_NO_POD_GATE=1 ./scripts/run_client1.sh`.

## What it does while running (supervised)
- Periodically reads the TMS and **posts an "Invoice [Approve & run]" button** for each delivered, un-billed load.
- Answers you in Slack. It **never moves money without your tap** — every invoice/payment is a proposal you approve.

## How you drive it — just talk in Slack
Reply in a Neyma thread, or `/neyma <message>`:
- **"who owes us money?"** → live outstanding-AR digest read from the TMS.
- **"what have you done today?"** → activity timeline. **"how did we do this week?"** → ROI.
- **"record a $184.50 payment on invoice 560003"** → proposes it → you approve → it applies + verifies.
- **"bill load 105"** → it fetches the amount from the TMS → proposes → you approve.
- **"pause tms writes" / "resume tms writes"** → the brake (kills/restores all writes instantly).
- To let one thing run without a tap once you trust it: **`/neyma graduate raise_invoice 5000`**
  (auto up to $5k/invoice). Undo with **`/neyma supervise raise_invoice`**. Start with everything supervised.

## The iteration loop ("nah, this needs to be better")
When something is wrong or should work differently, capture it so we fix it fast:
1. In Slack, note it in the thread (so the context + receipt are attached), or jot it in `docs/ITERATION_LOG.md`.
2. Format that helps most: **what you asked → what it did → what it should have done.**
3. We then do the proven loop: drive it live → find the cause → fix → prove on your TMS → ship.

Every run posts a **receipt with the full trace** (read → clicked → filled → committed → verified), so
"what did it actually do" is always answerable.

## What to expect (honest)
- **Proven live, use freely:** invoicing, recording payments, short-pay credits, outstanding-AR/"who owes us", the
  conversational surface.
- **Rough edges (the backlog we burn down together):** `create_load` is multi-entity and hard;
  `adjust_invoice` writes correctly but over-escalates on its success check; the email/inbox brain isn't
  live yet; multi-day continuous uptime is unproven — so **watch it the first stretch**.
- **Safety:** the worst case is "it stops and asks you," never a silent wrong money write. Keep lanes
  supervised until each earns your trust.

## Putting it in front of domain folks
Once you've run it a week and it feels right, demo the proven surface (invoice-on-delivery + "who owes
us" + record-payment, all from Slack). Collect their "it should also…" as new lanes/feedback — same
iteration loop. Don't demo the rough-edge ops until they're driven + proven.
