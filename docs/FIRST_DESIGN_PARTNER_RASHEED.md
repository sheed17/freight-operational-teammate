# Rasheed First Design Partner Runbook

Rasheed/Neyma Test Freight is the first supervised design partner. The goal is to experience Neyma
as a real freight operations teammate while keeping external risk low.

## Tool Connection Order

1. **Local proof first**
   ```bash
   .venv/bin/python scripts/run_first_design_partner.py --dispatch-mode LOCAL_OUTBOX --text
   ```

   This proves synthetic email ingestion, Slack-shaped review messages, local review artifacts,
   signed actions, callback handling, daily summaries, audit logs, and mock TMS verification.

2. **Connect Slack first**

   Ask Rasheed for:

   ```text
   NEYMA_DELIVERY_SECRET_RASHEED_FIRST
   NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST
   NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST
   Slack review channel ID
   Optional Slack digest channel ID
   ```

   Then update `configs/clients/rasheed_first_design_partner.yaml` channel IDs and run:

   ```bash
   .venv/bin/python scripts/verify_first_design_partner_slack.py
   ```

   Only after that returns `ready: true`, run:

   ```bash
   .venv/bin/python scripts/run_first_design_partner.py --dispatch-mode LIVE_SLACK --text
   ```

   Live Slack mode posts review cards only to Slack. Email is not a user review channel.

3. **Controlled email ingestion second**

   Use a test inbox or alias. The first email step is ingestion only: synthetic carrier emails and
   attachments flow into Neyma. Carrier-facing outbound stays draft-only behind the send gate.

4. **Real TMS read-only mapping third**

   Use the partner/customer system only for read-only screen mapping. Real writes stay disabled.

## Safety Defaults

- Carrier sends: disabled.
- Real TMS write: disabled.
- User review email: disabled by product contract.
- Carrier-facing email send: draft-only until a separate send gate is enabled.
- Slack live posting: only with `--dispatch-mode LIVE_SLACK` and real Slack env vars.
- TMS session: human-established only.
- Mock TMS write drill: allowed only as local verification and labeled mock-only.

## Completion Gate

The first-design-partner run is green when:

- Synthetic email ingestion scores cleanly.
- Slack review attempts are created.
- Local review artifacts are created when running local modes.
- Signed action and callback action both apply.
- Daily summary exists.
- Audit events exist.
- Mock TMS readback passes.
- Mock-only TMS write verification passes.
- No carrier sends happen.
- No real TMS writes happen.
