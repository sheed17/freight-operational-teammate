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

After the secrets in §1 are set, the launcher brings up all three local processes wired to one
workspace (the path-mismatch landmine is removed by construction):

```bash
.venv/bin/python scripts/run_teammate.py \
  --client-config "$CLIENT_CONFIG" \
  --daily-digest-hour 7 --query UNSEEN
```
Then add stable ingress (§5) and point the Slack app's Request URLs at it. Ctrl-C stops the group.
The sections below are the same processes run individually (useful for debugging one at a time).

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

## 5. Stable ingress (replaces the rotating quick-tunnel)

Quick `cloudflared tunnel --url http://127.0.0.1:8001` gives a **new random URL each restart** — fine
for a demo, not for a deploy. For a stable URL use a cloudflared **named tunnel** bound to a domain, an
**ngrok reserved domain**, or a real HTTPS host. Then set, in the Slack app (api.slack.com):
- **Interactivity** Request URL → `https://<stable-host>/slack/actions`
- **Slash Commands** Request URL → `https://<stable-host>/slack/commands`

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
