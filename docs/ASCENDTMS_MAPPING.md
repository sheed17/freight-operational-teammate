# AscendTMS Reference Mapping Plan

AscendTMS is a realistic reference TMS-style UI for Neyma's internal dogfood work. It is **not**
the assumed production integration and not "the real deal." Treat it as a reference pattern for
real freight screens, navigation concepts, and failure modes while Neyma's actual production
browser-use agents remain customer-system specific.

## Why It Matters

Neyma's product direction is existing-system operation. The customer should not have to live in a
new dashboard for routine work; Neyma should read email/PDF packets, coordinate review in Slack,
and operate the customer's TMS/accounting screens when approved.

AscendTMS gives the project a real freight UI reference before a design partner:

- Loads.
- Customers.
- Carriers.
- Accounting/payables.
- Document management.
- Notes/status fields.
- Settings and company profile.

## Current Rule

AscendTMS access is read-only reference exploration plus fake sandbox data entry when explicitly
needed for mapping. Neyma must not submit real payments, send real customer/carrier communications,
change billing, invite users, or operate on real company data.

Production browser-use agents will navigate inside each customer's actual TMS/accounting/email
systems. Each customer system needs its own screen map, domain allowlist, permission gate, and
readback contract. The AscendTMS catalog is a reference catalog that helps shape those contracts
and the mock TMS, not a promise that AscendTMS is the launch integration.

## Mapping Targets

Capture each target as a screen map with:

- URL pattern.
- Navigation path.
- Primary purpose.
- Stable labels/selectors visible to browser agents.
- Fields Neyma needs to read.
- Fields Neyma may eventually prepare for write.
- Human confirmation point.
- Readback verification point.
- Failure modes.

The typed seed catalog lives at:

```text
configs/tms/ascendtms_screen_map.json
```

Validate it with:

```bash
.venv/bin/python scripts/validate_screen_map.py
.venv/bin/python scripts/validate_screen_map.py --summary
```

This catalog is a mixed-evidence **reference** contract. The organization/settings screen and the
primary navigation tree have been observed through Computer Use in the logged-in trial account.
Deeper screen internals such as load detail fields, document rows, carrier profile details, and
accounting payable rows still require direct observation before they influence any customer-specific
browser-use adapter.

Per-screen provenance lives in each screen's `observation_status` and `observation_evidence`:

```text
OBSERVED = screen content and route observed
NAV_OBSERVED = route/navigation observed, screen internals still pending
SEED_PENDING_OBSERVATION = product assumption only
```

Only `OBSERVED` + `READ_ONLY` reference screens may influence a real read-only browser-use mapping.
Screens marked `NAV_OBSERVED` or `SEED_PENDING_OBSERVATION` are blocked from customer adapter
targeting until their internals are observed and the relevant catalog is updated with evidence.

Initial screens:

1. Organization/settings profile.
2. Load board/search.
3. Load detail.
4. Documents tab or document management.
5. Carrier profile.
6. Customer profile.
7. Accounting/payables queue.
8. Notes/activity/history.

## Adapter Ladder

```text
manual screen map
→ mock TMS updated to mirror useful reference concepts
→ Playwright/local checks against mock TMS
→ browser-use read-only against mock TMS
→ browser-use read-only against reference/sandbox TMS patterns
→ customer-specific screen map from the customer's actual system
→ browser-use read-only inside the customer's system
→ approved prepare-only write in mock TMS
→ approved sandbox/customer write drill only after gates
```

The adapter contract stays the same:

```text
read_load(load_id)
read_payable(load_id)
attach_document(load_id, file)
prepare_payable(...)
submit_payable(...)
verify_payable(...)
```

## Browser-Agent Model Policy

Use the cheapest model that passes evals for read-only screen mapping, but keep stronger models
available for hard screen reasoning. A browser model may locate fields and execute approved steps;
it may not decide money, approve variances, or mark completion without deterministic readback.

## Production Gate

Any customer-system browser-use work cannot graduate beyond read-only until these are true:

- Domain allowlist is configured.
- Session is human-established; no stored TMS credentials.
- Tool permission registry allows the action in the current state.
- Prepare step writes nothing and shows exact intended values.
- Submit step requires explicit human approval.
- Readback verification matches intended values.
- Audit trail records every screen action and decision.
