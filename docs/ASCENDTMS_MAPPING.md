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

As of the real-access mapping slice, `scripts/drive_real_tms.py` is an **observation recorder**,
not a general browser agent runner and not a write adapter. It requires a screen id from the typed
catalog, loads the catalog allowlist, rejects write/action verbs, adds a read-only prompt guard, and
writes an evidence artifact under:

```text
data/active_workspace/ascendtms_observations
```

Use it only with a human-established Chrome session:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/ascend-agent-chrome"
```

Then log into AscendTMS manually in that Chrome profile and run read-only observation:

```bash
.venv/bin/python scripts/drive_real_tms.py \
  --screen-id load_board \
  --task "Observe the load board. Return visible headings, table labels, nearby action controls, and whether fake/sandbox loads are present." \
  --max-steps 12
```

For screens still marked `SEED_PENDING_OBSERVATION`, add `--allow-seed-observation`. That flag only
allows evidence capture; it does not make the screen adapter-ready.

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

Each observation artifact should preserve:

- observed URL and page title;
- screenshot path if captured;
- visible labels/selectors;
- required fields and whether their values were readable;
- nearby controls that could mutate data;
- forbidden controls seen on the page;
- whether fake/sandbox data was used;
- notes about editable fields, modals, empty states, or session expiry.

After converting an artifact into a `ScreenObservation` JSON, apply it with:

```bash
.venv/bin/python scripts/record_tms_observation.py path/to/observation.json --apply --text
```

The recorder enforces catalog allowlisted domains and refuses to promote a screen to `OBSERVED`
unless every required read field is confirmed in the observation.

Example `ScreenObservation` JSON:

```json
{
  "screen_id": "load_board",
  "observed_url": "https://ascendtms.com/loads",
  "status": "OBSERVED",
  "observed_at": "2026-06-25T12:00:00Z",
  "observer": "codex",
  "title": "Loads",
  "navigation_path_seen": ["Loads", "View Loads"],
  "stable_selectors_seen": [
    "left navigation Loads",
    "Loads submenu: View Loads",
    "load reference column"
  ],
  "field_observations": [
    {
      "name": "load_id",
      "label_seen": "Load ID",
      "value_seen": "sandbox/fake load row visible",
      "selector_evidence": "load table reference column",
      "required_for_read_confirmed": true
    }
  ],
  "action_controls_seen": ["Build a Load", "Search Loads"],
  "forbidden_controls_seen": ["Build a Load", "Delete load if visible"],
  "screenshot_path": "data/active_workspace/ascendtms_observations/load_board.png",
  "notes": [
    "Read-only observation only; no fields changed.",
    "Use only fake/sandbox rows for mapping evidence."
  ]
}
```

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

`scripts/enter_tms_payable.py --browser` and `BrowserUseWriteLedger` remain mock/sandbox execution
tools. They are explicitly blocked from targeting `ascendtms.com`; real AscendTMS work stays
read-only until a customer/sandbox-specific write gate is designed and approved.

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
