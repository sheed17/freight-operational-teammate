# Neyma — Production Handoff & Honest Readiness Verdict

_Handoff date: 2026-07-06. Read this before deploying. It says what's genuinely ready, what isn't,
how to run it always-on, and where the honest risks are. No overclaiming._

---

## The verdict, plainly

**Good to go for a SUPERVISED, single-design-partner AR pilot on an always-on host.** The hard,
risky part — safe money writes inside a real TMS, driven from Slack, with the fence and gates —
is proven live and repeatable.

**NOT yet good to go for hands-off, multi-tenant, "set it and forget it" production.** It has never
run for days on a server, several operations are built-but-unproven, and it runs against a local
browser. Those are known, ordinary gaps — not hidden risk — listed below.

If someone asks "can I put this in front of one freight customer, with me watching, and have it
invoice their delivered loads and tell them what's owed?" — **yes.** If they ask "can it run my whole
back office unattended across many customers?" — **not yet; here's the list.**

---

## What is PROVEN (live, repeatable)

- **Invoice delivered loads** — end-to-end on TruckingOffice, 3 times (invoices #560009–560011):
  TMS trigger → Slack card → approve → the agent fills + saves → **verified by readback** → receipt.
- **See what's owed** — "who owes us money?" returns a live aged-AR digest, read straight off `/invoices`.
- **Record a customer payment** — proven live: applied $184.50 to invoice #560003, cleared it to $0,
  verified by readback (found + fixed a search-submit-vs-commit bug in the process).
- **Conversational control** — reply to Neyma in plain English (or `/neyma`): reads answered, controls
  work ("pause tms writes" → brake), money actions proposed with the fence intact.
- **Safety spine** — money fence (amount never model-chosen), verify-by-readback, commit-once (no
  double-pay across restarts), POD-gating, injection boundary, content moderation, per-lane autonomy
  with dollar/party/daily caps. All enforced by real signals, all live-validated.
- **621 automated tests green.**

## What is BUILT but NOT yet live-proven

Each routes correctly and runs through the same safe spine, but has not been watched succeed on a
real TMS write. **Do not represent these as proven until each is driven live once:**

- `adjust_invoice` (credit / short-pay) — WRITE proven live (applied a fenced $50 credit to #560009 via
  TruckingOffice's write-off; balance $2,000 -> $1,950, verified). Agent escalates on an over-strict
  verify message instead of DONE — a tuning item, not a failure.
- `record_payable` (AP) — needs a broker TMS account to prove.
- `file_document` (attach POD/BOL to a load) — FileSafe target mapped; drive pending.
- `create_load` — LIVE FINDING: TruckingOffice's Add-Load is multi-entity (customer + shipper + consignee
  addresses via autocomplete finders, creating new ones is a sub-workflow). The agent safely ESCALATES
  (never invents load data) but the happy path needs pre-existing addresses or a composite flow. Harder
  op class than the clean single-form writes.
- `update_status`, `check_call` (dispatcher ops) — routed + bounded goals; drive pending.
- Detail-page POD verification (decision logic done; the FileSafe DOM read is pending a real attached doc).

---

## How to run it always-on

### What YOU must provision
1. **An always-on host** — a small always-up Linux VM (or a Mac mini). This is the single biggest gap:
   today it runs on a laptop.
2. **A browser that stays up on the host** — a headless Chrome started with
   `--remote-debugging-port=9222`, logged into the customer's TMS, kept alive (see supervision below).
3. **Secrets in `.env`** on the host (Slack bot token + signing secret, action secret, ngrok token +
   static domain, OpenAI key). The preflight refuses to start if any are missing.
4. **The customer's Slack** — a channel + the owner's user id for the allowlist.
5. **The customer's TMS login** in that Chrome (API-first where one exists; the browser agent is the floor).

### Launch (one command, supervises all children)
```bash
set -a; source .env; set +a
.venv/bin/python scripts/run_teammate.py \
  --client-config configs/clients/<partner>.yaml \
  --enable-operation-router \
  --allowed-slack-user <OWNER_SLACK_ID> --allowed-slack-channel <CHANNEL_ID> \
  --operation-url-filter <tms-domain> \
  --enable-ar-trigger --ar-interval-seconds 300
```
Add `--ar-autonomous` only after the owner has graduated a lane (`/neyma graduate raise_invoice <cap>`).
Add `--ar-no-require-pod` only if the TMS list can't show POD (e.g. TruckingOffice) and the owner accepts it.

### Keep it up (process supervision)
`run_teammate` supervises its children within one process, but the process itself and Chrome need an
OS-level supervisor so a crash or reboot self-heals. Minimal `systemd` unit:
```ini
[Unit]
Description=Neyma teammate
After=network-online.target
[Service]
WorkingDirectory=/opt/neyma
ExecStart=/opt/neyma/.venv/bin/python scripts/run_teammate.py <args as above>
Restart=always
RestartSec=10
EnvironmentFile=/opt/neyma/.env
[Install]
WantedBy=multi-user.target
```
Run Chrome under its own always-restart unit (or a `--user-data-dir` kept warm) so the debug port is
always there. ngrok is already supervised as a child on the static domain.

---

## Resilience already in place (what survives a crash/restart)
- **Commit-once** — a reserved/committed operation is never repeated after a restart (SQLite-backed).
- **Dedup** — Slack event retries and re-proposed loads don't double-act.
- **SQLite WAL + 30s busy_timeout** — the callback, loop, and AR trigger share one DB concurrently.
- **Heartbeat + liveness watchdog** — the callback watches the loop's heartbeat and pings Slack if it
  goes stale.
- **Browser-lock** — the periodic reader defers while a write holds the shared browser.
- **Fail-closed everywhere** — an unreadable page, missing amount, or unproven POD stops and asks; it
  never guesses.

## Known gaps / risks for hands-off always-on (the honest list)
1. **Never run for days on a server.** Longest-duration + reconnect-after-Chrome-death path is unproven.
2. **Local browser, single tenant.** No hosted headless-browser pool; no multi-tenant DB/isolation.
3. **Unproven operation lanes** (above) — prove each live before relying on it.
4. **Slack Events subscription is required** for thread-reply/`submit` — a per-app setup step (documented
   in the pilot doc); if it lapses, replies silently vanish.
5. **Model/API dependence** — TMS-driving + NL routing call OpenAI; an outage degrades to escalation,
   not a wrong write (the fence holds), but it does pause work.
6. **No dashboards/alerting beyond the heartbeat watchdog.**

---

## Go / no-go
| Use case | Verdict |
|---|---|
| One design partner, owner-supervised, AR invoicing + aging on an always-on host | ✅ go |
| Same, with a graduated lane running unattended within caps | ✅ go, after one live autonomous proof |
| Hands-off across many customers (multi-tenant product) | ⛔ not yet — see gaps 1–2 |
| AP / carrier settlement | ⛔ needs a broker TMS account + a live proof |

**Bottom line: deploy it for one partner, watch it, and prove the remaining lanes one at a time on their
live TMS. That's the honest finish line — the wedge is real and safe; the breadth and the always-on
hardening are ordinary work from here.**
