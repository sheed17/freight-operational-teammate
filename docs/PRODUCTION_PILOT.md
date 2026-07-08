# Production Pilot — running Neyma as one, and exactly what's left

This is the definitive "how do we run the pilot" doc: the single command that brings up the three
pillars as one service, what is proven vs pending, and the precise inputs **you** must supply to go
live with a design partner.

## The three pillars — state

| Pillar | What it does | State |
|---|---|---|
| **Browser agent** | drives the client's TMS to write invoices/payments | ✅ **production-grade, live-validated** on TruckingOffice — perception, settle, commit-gating, verify-before-DONE, read-back, **amount reconciliation**, **macro-replay (learn once, replay across records)**, failure taxonomy, screenshot-on-escalation. Real committed money writes; safety held throughout. |
| **Slack** | proposals, approvals, thread-reply resume, status | ✅ **production-ready** — signed actions, single-use tokens, channel/user allowlist, proven live |
| **Watcher (inbox)** | read mail → **triage** → extract → reconcile → propose | ⚠️ **wired + triage now activatable, not yet run continuously** — Inbox Brain + reconciliation + clean-payable proposals; the **email-triage relevance gate is now wired into the live path** (`--enable-triage`); runs on the existing Gmail creds |

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

### The AR loop (real-TMS sourced — this is the write that's proven live)

Add `--enable-ar-trigger` to source proposals from the **live TMS** instead of (or alongside) the
inbox: a supervised child periodically reads the TMS `/loads`, and posts one **`Invoice [Approve &
run]`** button per delivered-but-un-invoiced load at that load's Total. A tap drives the exact
`raise_invoice` write that's already proven live on TruckingOffice (invoice #560009, #560010, partial
payments, cross-record replay).

**POD gate (owner SOP):** by default the trigger will **not** bill a load until its POD (Proof of
Delivery) is proven. It checks the loads list first; if the list cannot show POD status, it inspects the
load detail/documents area and accepts only delivery proof such as POD or signed BOL. A rate con alone
does not count. If the detail page is unreadable or no proof is present, Neyma posts a POD exception
instead of a money button. For a controlled demo only, set an explicit exception and pass
**`--ar-no-require-pod`** to bill on delivered status alone.

```bash
set -a; source .env; set +a          # so IMAP/Slack/ngrok/OpenAI secrets are present
.venv/bin/python scripts/run_teammate.py \
  --client-config configs/clients/<partner>.yaml \
  --enable-operation-router \
  --allowed-slack-user <SLACK_USER_ID> \
  --allowed-slack-channel <SLACK_CHANNEL_ID> \
  --operation-url-filter truckingoffice \
  --enable-ar-trigger \
  --enable-triage \
  --tms-loads-url https://secure.truckingoffice.com/loads \
  --ar-interval-seconds 300
```

For a demo where the owner explicitly accepts billing on delivered status even without readable
delivery-proof documents, add `--ar-no-require-pod`.

**Shared-browser coordination is built in:** the write agent marks `workspace/browser.busy` while it
operates; the AR trigger reads the same marker and *defers* a cycle rather than navigating the tab
mid-write. Both share the workspace `workflow.sqlite3`, so a still-un-invoiced load isn't re-proposed
every cycle. Prereq for the demo: one delivered-but-un-invoiced load in the TMS, and a Chrome on
`--remote-debugging-port=9222` logged in.

**Session readiness is explicit:** `/neyma status` and the pilot readiness rollup check CDP reachability,
the configured TMS URL filter, and login/session-expired pages. A missing browser, wrong tab, or expired
session is **NO_GO**, not a soft warning; the owner must re-auth before Neyma operates the TMS.

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

Before treating Slack as the owner's live control surface, run the onboarding gate:

```bash
set -a; source .env; set +a
.venv/bin/python scripts/verify_owner_onboarding.py \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --allowed-slack-user <SLACK_USER_ID> \
  --allowed-slack-channel <SLACK_CHANNEL_ID> \
  --operation-url-filter <tms-domain-substring>
```

After `run_teammate` is running and Chrome is logged into the TMS on CDP, run the live gate:

```bash
.venv/bin/python scripts/verify_owner_onboarding.py \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --allowed-slack-user <SLACK_USER_ID> \
  --allowed-slack-channel <SLACK_CHANNEL_ID> \
  --operation-url-filter <tms-domain-substring> \
  --require-running \
  --callback-url https://$NGROK_STATIC_DOMAIN/slack/commands \
  --require-public-ingress
```

Only when this reports `Owner onboarding readiness: READY` should the owner start using `/neyma`
as the daily control surface. A localhost callback probe is acceptable for local process debugging,
but it is not owner-ready because Slack must reach Neyma through the public Request URL.

## Remaining autonomous work (ordered) — before "continuous, hands-off"

1. ~~Activate email-triage~~ **DONE** — `run_teammate.py` now exposes `--enable-triage` /
   `--triage-model` and forwards it into the Gmail loop, which threads the triage completer through
   `run_mailbox_workflow` → `run_mailbox_intake` for real-inbox noise rejection and fuzzy links.
2. **Prove the full loop end-to-end, continuously** — one real document: mail → triaged → proposed →
   approved → written → receipt, unattended across a cycle. Every segment is proven; the *chain as a
   running service* is not.
3. **Reliability at volume** — many docs + unhappy paths (session expiry mid-run, ambiguous records,
   duplicates). Browser session health now fails readiness closed before work starts; mid-run failures still
   need real-load proving through the failure taxonomy + verify-before-DONE + commit-once spine.
4. ~~Fix `parse_eml` on RFC2047-encoded subjects~~ **DONE** — encoded real-carrier subjects are decoded
   before triage/linking.

## Honest readiness

**~65–70% to a supervised design-partner pilot** — and the shape matters more than the number: the
**hardest, most load-bearing pillar (the browser agent) is done and live-proven**, which was the whole
risk. What remains is integration + activation + deployment + the user-gated inputs above — normal work,
not novel capability.

**The single highest-leverage next move: prove the full loop once, continuously.** The **AR loop
(`--enable-ar-trigger`) is the shortest path to that proof** — it needs no inbox, just the TMS the
write is already proven against: create one un-invoiced load, run `run_teammate`, and the trigger →
Slack button → tap → money-fenced write → receipt chain runs as one supervised service (reader and
writer already coordinated on the shared browser). The mail-sourced AP loop follows the same spine
once a partner channel + creds are in.
