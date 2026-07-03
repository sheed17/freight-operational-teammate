# Production Pilot — running Neyma as one, and exactly what's left

This is the definitive "how do we run the pilot" doc: the single command that brings up the three
pillars as one service, what is proven vs pending, and the precise inputs **you** must supply to go
live with a design partner.

## The three pillars — state

| Pillar | What it does | State |
|---|---|---|
| **Browser agent** | drives the client's TMS to write invoices/payments | ✅ **production-grade, live-validated** on TruckingOffice — perception, settle, commit-gating, verify-before-DONE, read-back, **amount reconciliation**, **macro-replay (learn once, replay across records)**, failure taxonomy, screenshot-on-escalation. Real committed money writes; safety held throughout. |
| **Slack** | proposals, approvals, thread-reply resume, status | ✅ **production-ready** — signed actions, single-use tokens, channel/user allowlist, proven live |
| **Watcher (inbox)** | read mail → extract → reconcile → propose | ⚠️ **wired, not yet run continuously** — Inbox Brain + reconciliation + clean-payable proposals exist; **email-triage relevance gate is built but not activated**; needs mailbox creds |

## The one command (runs all three as one)

`run_teammate.py` brings up — on ONE workspace/DB/heartbeat — the callback server (Slack → OperationRouter
→ the hardened agent → browser write), the Gmail poll loop (mail → extract → reconcile → post
"Record payable [Approve & run]" buttons), an ngrok tunnel on the fixed domain, and the packet site:

```bash
.venv/bin/python scripts/run_teammate.py \
  --client-config configs/clients/<partner>.yaml \
  --enable-operation-router \
  --allowed-slack-user <SLACK_USER_ID> \
  --allowed-slack-channel <SLACK_CHANNEL_ID> \
  --operation-url-filter <tms-domain-substring> \
  --propose-clean-payables
```

The full loop it runs: **mail arrives → extract → reconcile against the rate con → post an Approve
button in Slack → owner taps → callback → OperationRouter → the proven browser agent writes the record
→ readback-verified receipt.** Every seam in that chain is individually proven; what's unproven is the
*whole chain running continuously on a real inbox* (below).

## What YOU must supply to go live (the gate)

1. **Mailbox credentials** — ALREADY SATISFIED for dogfood. The preflight and the processor both fall
   back to `NEYMA_SMTP_USERNAME/PASSWORD` (the same Gmail account, which has IMAP), and those are in
   `.env`. The only catch: **`run_teammate` must be launched with `.env` sourced** (`set -a; source .env;
   set +a`) — the earlier "IMAP missing" failure was an unsourced shell, not a missing secret. For a
   *new* partner, set their `NEYMA_IMAP_USERNAME/PASSWORD`.
2. **A design-partner Slack channel + the owner's user id** — for `--allowed-slack-channel` /
   `--allowed-slack-user` (only that owner, that channel, can approve).
3. **The partner's TMS** — logged into a Chrome started with `--remote-debugging-port=9222`
   (`--operation-url-filter` pins the agent to it). API-first where one exists (accounting API for AR is
   often better than the TMS screen); the browser agent is the universal floor.
4. **An always-on host** — the machine (or VM) that runs `run_teammate` continuously. ngrok static
   domain (`NGROK_STATIC_DOMAIN`) + `NGROK_AUTHTOKEN` are already set, so the Slack Request URL stays
   stable across restarts.

## Remaining autonomous work (ordered) — before "continuous, hands-off"

1. **Activate email-triage on the inner processing** — pass a `triage_completer` (gpt-5.4) into the live
   intake so noise is filtered and fuzzy carrier/customer links resolve (built in `email_triage.py`,
   opt-in; the live dogfood processor doesn't pass it yet). Turns "works on a labeled test inbox" into
   "survives a real billing inbox."
2. **Prove the full loop end-to-end, continuously** — one real document: mail → triaged → proposed →
   approved → written → receipt, unattended across a cycle. Every segment is proven; the *chain as a
   running service* is not.
3. **Reliability at volume** — many docs + unhappy paths (session expiry mid-run, ambiguous records,
   duplicates). The failure taxonomy + verify-before-DONE + commit-once handle these; they need real-load
   proving.
4. **Fix `parse_eml` on RFC2047-encoded subjects** (real carrier emails will have them) before the live
   inbox.

## Honest readiness

**~65–70% to a supervised design-partner pilot** — and the shape matters more than the number: the
**hardest, most load-bearing pillar (the browser agent) is done and live-proven**, which was the whole
risk. What remains is integration + activation + deployment + the user-gated inputs above — normal work,
not novel capability.

**The single highest-leverage next move: get mailbox creds + a partner channel in, then run
`run_teammate` and prove the full loop once, continuously.** Everything upstream of that is ready.
