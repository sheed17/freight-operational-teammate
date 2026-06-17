# Customer Channel Onboarding Runbook

Integrating a new customer's Slack and/or email is a **repeatable config-and-secrets runbook**, not
a code change. The transports (`slack_adapter`, `email_adapter`) and the signed action intake are
fixed; per-customer wiring lives entirely in the customer's client config plus environment secrets.

Secrets are referenced by **environment-variable name** only — values never live in the repo.
Signed action tokens are bearer credentials. They may appear in live Slack buttons or email action
links, but normal logs, audits, and generated artifacts must store only redacted token fingerprints.

## One-time per customer

1. **Add the `delivery:` block** to `configs/clients/<customer>.yaml`. Copy the block from
   `configs/clients/neyma_test_freight.yaml` and rename the env vars per customer (suffix with the
   customer id), e.g.:

   ```yaml
   delivery:
     default_channel: slack
     action_token_secret_env: NEYMA_DELIVERY_SECRET_ACME
     slack:
       enabled: true
       outbound_enabled: false      # flip on only after dry-run dispatch passes
       signing_secret_env: NEYMA_SLACK_SIGNING_SECRET_ACME
       bot_token_env: NEYMA_SLACK_BOT_TOKEN_ACME
       default_channel_id: C0XXXXX
       routing:
         IMMEDIATE_PING: C0XXXXX     # critical → ping channel
         CHANNEL_POST: C0XXXXX       # medium → team channel
         DIGEST_ONLY: C0YYYYY        # low → digest channel
     email:
       enabled: true
       sender: neyma@acme-freight.example
       to: [controller@acme-freight.example]
       action_base_url: https://app.neyma.example/email/action
       outbound_enabled: false       # flip on only when the gated SMTP transport is wired
   ```

2. **Provision the secrets** in the deployment environment (never in the repo):
   - `action_token_secret_env` — a strong random HMAC secret for signing action tokens.
   - Slack: `signing_secret_env` (Slack app signing secret), `bot_token_env` (`xoxb-…` bot token).
   - Email: an optional `from_env` if the sender address is itself a secret/per-env value.

3. **Preflight** — confirm the config is well-formed and every named secret resolves, without
   sending anything:

   ```bash
   .venv/bin/python scripts/verify_channels.py --client-config configs/clients/acme_freight.yaml
   ```

   `ready: true` means the customer is wired. Any `MISS` line names the exact missing env var.

4. **Dry-run dispatch** — render and route review messages without sending:

   ```bash
   .venv/bin/python scripts/dispatch_review.py \
     --client-config configs/clients/acme_freight.yaml \
     --mode DRY_RUN \
     --text
   ```

   This records `delivery_dispatch_attempted` audit events and writes redacted dispatch attempts
   to `data/active_workspace/delivery_dispatch_attempts.json`.

5. **Slack app setup** (Slack channel only): create a Slack app, enable interactivity with the
   request URL pointing at the Neyma callback endpoint, and install it to the customer workspace.
   The endpoint verifies the request signature (`slack_adapter.verify_slack_signature`) and feeds
   the button token into the signed intake. Default channel ids in the config are the Slack channel
   ids the bot is invited to.

## Local callback dogfood

Before exposing any public callback URL, run the local callback server against the active dogfood
workspace:

```bash
.venv/bin/python scripts/run_action_callback_server.py --allow-local-dev-secret
```

It serves:

```text
GET  /email/action?token=<signed-token>
POST /actions/signed {"token": "<signed-token>"}
```

This is a local-only bridge for testing link clicks and webhook-shaped callbacks. It does not send
email, post to Slack, store credentials, or bypass workflow state; accepted actions still flow
through `delivery.submit_signed_action` and `apply_review_action`. Production must use a deployment
secret and an externally hosted callback endpoint behind the same intake. The fixed local dogfood
secret is fail-closed to loopback hosts only; do not expose it on `0.0.0.0` or a network interface.

## At runtime

```python
from freight_recon.channels import load_delivery_config, build_channel_adapters

config = load_delivery_config("configs/clients/acme_freight.yaml")
adapters = build_channel_adapters(store, config)   # {ChannelType.SLACK: ..., ChannelType.EMAIL: ...}
```

`build_channel_adapters` builds only the channels whose secrets resolve, with the customer's
action-token signer. Posting to a real workspace / sending real email stays behind the
`outbound_enabled` flag and the tool-permission registry.

Use `delivery_dispatch.dispatch_delivery_message` as the send boundary. Supported modes:

- `DRY_RUN` — route and audit only; no Slack API call, no email file.
- `LOCAL_OUTBOX` — render local email `.eml` artifacts intentionally; Slack stays local.
- `LIVE` — Slack may call `chat.postMessage` only when `slack.outbound_enabled: true`, the bot
  token resolves, and workflow-state tool permission allows the post. SMTP email send is still not
  wired; live email remains blocked until a gated SMTP transport is added.

The dispatcher currently broadcasts to every enabled configured channel. `default_channel` is the
preferred primary channel for future fallback behavior, not an exclusive routing selector yet.

## Safety invariants (unchanged per customer)

- Two independent HMAC layers: the channel request signature (Slack `v0` / email link is the token
  itself) and the Neyma action token (expiring, single-use).
- Every action routes through `delivery.submit_signed_action` → `apply_review_action` → the
  workflow state machine. A channel can never bypass workflow state or decide money.
- No customer credentials are stored; only env-var names live in config.
- Production signing fails closed when the action-token secret is missing. Local dogfood scripts
  may opt into the fixed local secret explicitly; channel onboarding must not.
- Outbound send is off by default and gated.
