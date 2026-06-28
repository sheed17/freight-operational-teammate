# Neyma always-on deployment runbook

How to run Neyma as a continuous "teammate that sits in the inbox all day." The critical rule:
**every process below must share ONE workspace** so the Slack `status` surface reads the same DB and
heartbeat the loop is actually writing. Mismatched paths make `status` report confident falsehoods.

## 0. One canonical workspace (non-negotiable)

```bash
export WS="$PWD/data/active_workspace/gmail_to_slack_service"
export CLIENT_CONFIG="configs/clients/rasheed_first_design_partner.yaml"
```

All processes use `--workspace "$WS"`. The loop writes `$WS/workflow.sqlite3`,
`$WS/teammate_status.json`, and `$WS/ops_control.json`; the callback server is pointed at the **same**
files. If they diverge, the callback prints a loud `WARNING:` at startup — do not ignore it.

## Quick start (one command)

After the secrets in §1 are set, the launcher brings up all local processes wired to one
workspace (the path-mismatch landmine is removed by construction):

```bash
set -a; . ./.env; set +a   # load secrets (preflight + children + NGROK_* read the env)
.venv/bin/python scripts/run_teammate.py \
  --client-config "$CLIENT_CONFIG" \
  --daily-digest-hour 7 --query UNSEEN
```
This supervises **four** children sharing one workspace: site, callback, loop, **and the ngrok
tunnel** (when `NGROK_STATIC_DOMAIN` is set and `ngrok` is on PATH; `--no-ngrok` to opt out). Folding
ingress into the same supervisor removes the failure where the app is up but the tunnel is dead (or
vice-versa) — the exact desync behind Slack's "the app did not respond". A startup **credential
preflight** refuses to launch if a required secret is missing. ngrok forwards to `127.0.0.1`
explicitly (a bare port can resolve to IPv6 `[::1]` and miss the IPv4-bound callback → `ERR_NGROK_8012`).
Point the Slack app's Request URLs at the fixed domain once (§5). Ctrl-C stops the whole group.

> Run this in a terminal you control (or a process manager) for durable always-on — the supervisor
> must outlive your shell session. The sections below are the same processes run individually (debugging).

## 1. Secrets (`.env`, never committed)

```
NEYMA_IMAP_USERNAME / NEYMA_IMAP_PASSWORD        # Gmail app password (BODY.PEEK only)
OPENAI_API_KEY                                   # extraction + browser-use
NEYMA_DELIVERY_SECRET                            # signs Slack/email action tokens
NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST              # bot token (xoxb-…)
NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST         # verifies inbound Slack requests
```

## 2. Process A — the always-on Gmail loop (writes the heartbeat + drives work)

```bash
.venv/bin/python scripts/run_gmail_to_slack_loop.py \
  --workspace "$WS" --interval-seconds 300 \
  --client-config "$CLIENT_CONFIG" --daily-digest-hour 7 \
  -- --client-config "$CLIENT_CONFIG" --real-extraction --provider openai \
     --mailbox "Neyma-Test-Inbox" --query UNSEEN \
     --dispatch-mode LIVE --enable-live-slack-outbound
```
`--client-config` on the loop makes Neyma post to the digest channel: proactive **failure/recovery
alerts**, a per-cycle **"N new items need review" nudge** when a cycle surfaces work, and the
**daily digest** once a day at `--daily-digest-hour` (so you run no separate cron). Args after `--`
are forwarded to the per-cycle runner.

## 3. Process B — the static packet site (the card links)

```bash
.venv/bin/python -m http.server 8000 --directory "$WS/site"
```

## 4. Process C — the callback server (Slack clicks + `status` command + auto-execution)

Pointed at the **same workspace's** DB + heartbeat as the loop:
```bash
.venv/bin/python scripts/run_action_callback_server.py \
  --host 127.0.0.1 --port 8001 \
  --workspace "$WS" \
  --db "$WS/workflow.sqlite3" \
  --status-file "$WS/teammate_status.json" \
  --client-config "$CLIENT_CONFIG" \
  --auto-enter-approved-mock-tms
```
`--auto-enter-approved-mock-tms` makes an APPROVE_* click auto-run the **mock-gated** payable entry and
narrate it into the load's Slack thread. (Real-TMS write is intentionally NOT enabled here.)

## 5. Stable ingress (fixed URL — set Slack once, never again)

A `cloudflared` quick tunnel hands out a **new random URL each restart**. Use a fixed endpoint instead.
We use an **ngrok free static domain** (`NGROK_AUTHTOKEN` + `NGROK_STATIC_DOMAIN` in `.env`):

```bash
ngrok config add-authtoken "$NGROK_AUTHTOKEN"
ngrok http --domain="$NGROK_STATIC_DOMAIN" 8001          # always forwards to the callback port
```
This URL is permanent, so set the Slack app (api.slack.com) Request URLs **once**:
- **Interactivity** Request URL → `https://$NGROK_STATIC_DOMAIN/slack/actions`
- **Slash Commands** Request URL → `https://$NGROK_STATIC_DOMAIN/slack/commands`

(Production alternative: a cloudflared **named tunnel** bound to a domain you own, or a real HTTPS host.)

## 6. Daily digest (scheduled)

```bash
.venv/bin/python scripts/generate_daily_summary.py \
  --db "$WS/workflow.sqlite3" --payloads "$WS/review_payloads.json" \
  --post-slack --client-config "$CLIENT_CONFIG"
```
Run on a cron (e.g. 7am local). "Recovered" counts only at verified DONE.

## 7. Operating from Slack (no JSON, no SSH)

- `status` or `what is neyma doing` → Gmail-poll health + TMS-writes brake + items waiting on you.
- `pause tms writes` / `resume tms writes` → the brake.
- `show unresolved`, `status <LOAD-ID>`.
- Neyma proactively posts to the digest channel when polling **fails** and when it **recovers**.

## Health expectations

- Healthy: `status` shows 🟢, last cycle within the poll interval.
- Stuck: 🟡 if no cycle within ~3× the interval (the loop records `interval_seconds` in the heartbeat).
- Failing: 🔴 with consecutive-failure count; a digest-channel alert was already posted.
