# Design Partner Deployment Package

This package turns the completed internal dogfood system into a supervised design-partner pilot.
It is intentionally not a production launch plan. Live sends and real TMS writes stay gated/off by
default until the partner-specific gates prove they are safe.

## Source Artifacts

- Internal pilot ledger: `data/active_workspace/pilot_session/pilot_session_ledger.json`
- Internal pilot summary: `data/active_workspace/pilot_session/pilot_session_summary.txt`
- Client config template: `configs/clients/design_partner_template.yaml`
- Channel runbook: `docs/CHANNEL_ONBOARDING.md`
- Screen mapping reference: `docs/ASCENDTMS_MAPPING.md`
- Data-arrival execution plan: `docs/WHEN_DESIGN_PARTNER_DATA_ARRIVES.md`

## Pilot Scope

Start with supervised carrier invoice reconciliation:

```text
carrier invoice/email/PDF
-> classify/link packet
-> extract required invoice fields
-> reconcile against rate confirmation or load/payable export
-> post review message to Slack
-> human approves, disputes, requests backup, edits, or marks duplicate
-> Neyma drafts carrier follow-up behind a send gate when needed
-> Neyma records decision and daily summary
```

Out of scope for the first design-partner pilot:

- Autonomous TMS writes.
- Real payment execution.
- User review emails. Slack is the human review UI.
- Ungated carrier-facing emails.
- Claims of production extraction readiness before partner-document eval passes.
- Browser automation beyond read-only customer-system mapping.

## Onboarding Runbook

1. **Confirm partner scope**
   - Carrier invoice reconciliation only.
   - Historical closed-load data first.
   - Supervised review.
   - No autonomous TMS write.

2. **Create partner config**
   - Copy `configs/clients/design_partner_template.yaml` to
     `configs/clients/<partner_id>.yaml`.
   - Replace placeholders, but keep `outbound_enabled: false`, `live_write_enabled: false`, and
     `tms_write_enabled: false`.
   - Use env-var names for secrets. Never commit secret values.

3. **Collect pilot data**
   - 20-50 closed-load carrier invoice PDFs.
   - Matching rate confirmations or exported load/payable data.
   - Examples with detention, lumper, fuel, linehaul, duplicates, and missing backup.
   - Written permission for testing/configuration only.

4. **Run internal go/no-go evidence**
   ```bash
   .venv/bin/python scripts/run_internal_pilot_session.py --days 7 --loads-per-day 18 --text
   .venv/bin/python scripts/verify_design_partner_package.py \
     --client-config configs/clients/design_partner_template.yaml \
     --pilot-ledger data/active_workspace/pilot_session/pilot_session_ledger.json
   ```

5. **Preflight delivery config**
   ```bash
   .venv/bin/python scripts/verify_channels.py --client-config configs/clients/<partner_id>.yaml
   ```

   Missing env vars are expected before deployment. The config must still parse and remain safe by
   default.

6. **Dry-run review delivery**
   ```bash
   .venv/bin/python scripts/dispatch_review.py \
     --client-config configs/clients/<partner_id>.yaml \
     --mode DRY_RUN \
     --text
   ```

7. **Customer-system screen mapping**
   - Identify the partner's TMS/accounting system.
   - Create a partner-specific screen map from observed screens.
   - Start read-only.
   - Record URL patterns, navigation path, stable labels/selectors, allowed actions, forbidden
     actions, failure modes, and readback points.
   - Do not reuse the AscendTMS reference catalog as a customer adapter.

8. **Historical pilot**
   - Run partner historical invoices.
   - Review every exception with the partner.
   - Record corrections as eval cases.
   - Tune config/rules.
   - Do not enable live sends or real TMS writes.

9. **Live supervised pilot**
   - Controlled input only: forwarded mailbox, upload folder, or watched inbox.
   - Human approval for every consequential action.
   - Daily summary reviewed with the partner.
   - Keep TMS write disabled.

## Secrets And Environment Checklist

Required per partner:

```text
NEYMA_DELIVERY_SECRET_<PARTNER_ID>
NEYMA_SLACK_SIGNING_SECRET_<PARTNER_ID>     if Slack enabled
NEYMA_SLACK_BOT_TOKEN_<PARTNER_ID>         if Slack live posting enabled later
```

Rules:

- Env var names may live in YAML.
- Secret values never live in the repo.
- Production action-token signing fails closed without the configured delivery secret.
- Local dogfood secret is loopback-only and must not be used for a partner.

## Pilot Success Metrics

Track these in the historical pilot and first live supervised week:

- Required-field extraction accuracy: load/PRO, linehaul, total.
- Dangerous overconfidence count on required fields.
- Packet link accuracy.
- Document type accuracy.
- Variances caught.
- Missing backup caught.
- Duplicate candidates.
- False positive rate.
- Human correction rate.
- Review time per invoice.
- Confirmed recovered or avoided overpayment.
- Unresolved exception aging.

## Rollback And Safety Plan

Rollback means Neyma stops acting and the partner returns to current manual review.

Immediate rollback triggers:

- Any raw action token appears in persisted artifacts.
- Any live send happens when `outbound_enabled` is false.
- Any real TMS write is attempted.
- A workflow action bypasses signed intake or audit.
- Partner reports review messages are confusing enough to risk incorrect approval.
- Extraction on partner docs fails the agreed gate.

Rollback steps:

1. Stop the Neyma process.
2. Disable channel outbound flags.
3. Revoke Slack secrets and any carrier-email secrets if exposed.
4. Preserve workflow DB and audit logs.
5. Export unresolved packets for manual review.
6. Record incident notes and add regression tests before resuming.

## Go/No-Go

Go to supervised design-partner pilot only when:

- Internal 7-day dogfood ledger is green.
- Partner config verifies and keeps carrier sends/writes disabled.
- Partner data-use permission is recorded.
- Historical partner eval passes required gates.
- Review messages include evidence links and exact money actions.
- Customer-system screen mapping is read-only and customer-specific.
- Rollback plan is understood by Neyma and the partner.
