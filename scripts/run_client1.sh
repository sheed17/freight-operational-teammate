#!/usr/bin/env bash
# Client-1 (owner-operated, SUPERVISED) launch — the everyday "always running" command.
# Supervised = Neyma proposes every money write and waits for your tap. No lane runs unattended
# (no --ar-autonomous) until you graduate it in Slack once you trust it: `/neyma graduate raise_invoice 5000`.
#
# Prereqs: Chrome up on :9222 logged into TruckingOffice; .env present; Slack Events URL set once.
# Usage:   ./scripts/run_client1.sh        (Ctrl-C stops the whole teammate; it self-heals crashed children)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

exec .venv/bin/python scripts/run_teammate.py \
  --client-config configs/clients/rasheed_first_design_partner.yaml \
  --enable-operation-router \
  --allowed-slack-user U0BBZ5RS9G8 \
  --allowed-slack-channel C0BB8KG21J8 \
  --operation-url-filter truckingoffice \
  --enable-ar-trigger --ar-no-require-pod \
  --tms-loads-url https://secure.truckingoffice.com/loads \
  --ar-interval-seconds 300
