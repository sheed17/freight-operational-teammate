# Onboarding any TMS to the Neyma engine

Neyma is a **TMS-agnostic engine**. We do not integrate "an AscendTMS adapter"; we run a generic
browser-use agent that operates *whatever* TMS a client uses — like a human — driven by a per-TMS
**screen map** plus the engine's fixed safety spine. A new client's TMS is onboarded by *observing*
its screens into a screen map; the engine code does not change.

AscendTMS is our **sample / proving ground**, not the target.

## The two halves: engine (fixed) vs. screen map (per-TMS)

- **Engine (never changes per client):** Gmail intake → GPT-4o extraction → deterministic
  reconciliation → Slack review + approval → gated browser write (`enter_approved_payable`:
  confirm-before-submit, approved-amount binding, idempotency) → **deterministic** verify-by-readback
  → DONE/FAILED → Slack thread status. Plus the owner brake (`pause tms writes`).
- **Screen map (per-TMS, observed):** `configs/tms/<tms>_screen_map.json` — the screens, their URL
  patterns, navigation paths, field labels/selectors, forbidden controls, and the
  `automation_mode` (READ_ONLY → PREPARE_ONLY → APPROVED_WRITE) + `observation_status`
  (SEED_PENDING → NAV_OBSERVED → OBSERVED) safety ladder.

## Onboarding ladder for a new TMS

1. **Human-established session.** The client logs into their TMS in a Chrome the agent attaches to
   over CDP (`--remote-debugging-port=9222`). No credentials are ever stored.
2. **Observe (read-only).** `scripts/drive_real_tms.py --screen-id <screen>` captures each screen's
   real structure into an evidence artifact. Hard read-only: action-verb guard, domain allowlist,
   secret redaction. Promote a screen to `OBSERVED` only when its required read fields are confirmed.
3. **Build the deterministic readback.** Verify-by-readback must be deterministic — the TMS's API if
   it has one, else a selector-based DOM read. *Never* an LLM free-read for the safety gate. (The
   mock uses `http_payable_readback`; a real TMS uses API/selector.)
4. **Promote the write target** through `READ_ONLY → PREPARE_ONLY → APPROVED_WRITE`. The screen-map
   validator refuses a write mode unless the screen declares a `human_confirmation_point` and a
   `readback_verification_point`.
5. **One supervised gated write** on a sandbox/test load, confirm-before-submit on a live human click,
   amount bound to the Slack approval.

## What the real AscendTMS taught us (2026-06-26, live read via CDP)

Proven: the generic engine reads real, authenticated AscendTMS — the loads board
(`/loads`), Accounting Management (`/accounting`), and a load detail (`/loads/{id}/basics`).

Account/UI realities (these are *screen-map + plan* facts, not engine limits):
- **No standalone "enter payable amount" form.** AscendTMS is invoice/AR-AP centric
  (Invoices / Bills / Reconcile and Archive). The carrier payable is the **carrier pay on the load**,
  set on a load sub-tab (not `/basics`), then loads are "Sent to Accounting."
- **Carrier payment is Pro-plan gated** on the trial: *"Carrier Payment Processing… only available to
  subscribers of our Premium and Pro Plans."* The account is also routed through **Triumph factoring**
  (*"cannot submit carrier payments… completed loads can be factored from the Invoices tab"*).
- **Navigation:** load detail lives at `/loads/{id}/<tab>`; the dynamic loads grid is not reliably
  click-through for a generic agent — the screen map should encode the URL pattern / row selector so
  the engine navigates deterministically rather than re-deriving it each run.

Implication: a real carrier-pay write needs a TMS/plan with that screen **accessible** (upgrade or a
different TMS). The engine is ready; the gating is feature access. When a full-access TMS is in place,
run the ladder above and the same engine performs the seamless real write.

## Reliability note: "operate like a human"

Generic page reads work well. Dynamic-grid click-through and clean field extraction are the frontier
and improve via: (a) a stronger/purpose-tuned model (browser-use's own navigation model), (b) the
screen map encoding navigation, (c) tighter prompts — none of which change the engine architecture.
