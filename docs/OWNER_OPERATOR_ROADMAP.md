# Neyma — Owner-Operator Roadmap (the single source of truth)

**This is the canonical "where are we" doc.** When you ask "where are we," the answer is here. It maps
the whole vision, what's proven vs pending, and the ordered path to the finish line. Updated as each
slice ships — check the changelog at the bottom for the latest.

_Last updated: 2026-07-06._

---

## North Star — the experience

A teammate sitting inside the operation, working like a great ops hire:

> **Something happens** (TMS event, email, doc) → 🔔 **Neyma pings you with context** → **you just tell it
> what to do, in plain English** → **it does it, within the gates** → **it shows you exactly what it did.**

No commands to learn, no buttons to hunt. The owner reacts to a notification like a text from a trusted
employee. It gets more autonomous the way a hire does — by earning it on a specific task (graduation),
never by flipping one switch.

---

## Profit-Protection Domains

Neyma is not meant to stop at data entry. The durable product should become the 24/7 backend operating
system that protects margin and cash across four owner-visible domains:

1. **Carrier Payables + fraud mesh** — invoice/rate-con/accessorial reconciliation, duplicate-payment
   prevention, payout freezes, and draft-then-approve carrier disputes for unapproved detention,
   lumper, fuel, re-consignment, or other hidden charges.
2. **Detention + accessorial recovery radar** — GPS/ELD/Macropoint/project44-style events, geofence
   dwell-time detection, broker-specific detention SOP retrieval, timestamp proof packets, and
   broker notices before the claim window closes.
3. **Document extraction + compliance auditor** — inbound email/SMS/driver-upload harvesting, POD/BOL
   quality checks, signature/readability detection, refusal to file bad documents, and immediate
   carrier/driver remediation requests.
4. **Broker credit + underwriting defense** — MC/DOT-based broker checks, factoring/credit API lookups,
   days-to-pay/exposure thresholds, and owner alerts before accepting high-risk freight.

Current build order still starts with the supervised AR/AP/document spine because every domain above
reuses the same machinery: inbox intake, deterministic matching, Slack approval, browser/API execution,
readback, audit, and receipts.

---

## The proven spine (the hard parts — DONE, live-validated)

Everything below plugs into this. This is why the remaining work is breadth, not new hard problems.

- ✅ **Safe money writes on a live TMS** — proven on TruckingOffice (invoices #560009–560011).
- ✅ **Money fence** — the model never chooses an amount; it's the load's Total or a human-approved figure.
- ✅ **Verify-by-readback** — DONE only when the saved record is actually read back.
- ✅ **Commit-once** — no double-pay, enforced across restarts.
- ✅ **Autonomy + graduation** — a lane runs unattended only within the owner's ceiling / allowlist / daily cap.
- ✅ **POD-gating** — never bill before Proof of Delivery is proven (BOL ≠ POD).
- ✅ **Injection boundary** — inbound docs/emails are data, never instructions; only an authed owner commands.
- ✅ **Content moderation** — the shared knowledge store refuses slurs/abuse/CSAM (local floor + OpenAI).
- ✅ **Run receipts** — every run shows the path: read → clicked → filled → committed → verified.
- ✅ **Conversational front door** — reply to Neyma in plain English → answer or gated proposal.
- ✅ **Slack surface** — signed single-use tokens, user/channel allowlist, Events API resume, the brake.

---

## Coverage map — what an owner wants handled

Honest headline: **~40% of what an owner wants is handled; ~80% of the machinery to do all of it exists.**
We went deep on AR invoicing and proved the spine; the rest is assembly on that spine.

| # | Operation area | Coverage | State |
|---|---|---|---|
| 1 | **AR — invoicing** (bill delivered loads) | ~80% | ✅ proven live, POD-gated, autonomous, conversational |
| 1b | **AR — collections** (aging, dunning, payment application, short-pays) | ~15% | 🔨 **building now** |
| 2 | **AP — carrier settlement** (reconcile invoice vs rate con → pay) | ~40% | ⚠️ built, not proven live (needs broker TMS acct) |
| 3 | **Exception / profit radar** (delivered-not-invoiced, POD missing, overdue, dup, detention/accessorial leakage, insurance expiry) | ~25% | ⚠️ POD-missing + dedup only |
| 4 | **Documents + compliance** (file POD/BOL, quality-check signatures/readability, match rate cons, carrier packets/compliance) | ~30% | ⚠️ FileSafe mapped, extraction exists, auto-filing not built |
| 5 | **Broker credit defense** (MC/DOT checks, days-to-pay, exposure limits, factoring/credit APIs) | ~0% | ❌ not started |
| 6 | **Long tail** (check calls, load status, margin-per-load, P&L/aging reports) | ~5% | ❌ not started |

---

## Ordered build plan → the finish line

Each slice: **pure parse (tested) → proposal/digest → gated action → live-prove.** Outward-facing actions
(emailing a customer) default to **draft-then-approve**; money actions keep the fence + graduation.

- [ ] **1. AR collections** ← _in progress_
  - [x] `receivables_from_invoices_table` — reads `/invoices` by content (drift-safe); unpaid = Balance Due > 0. **Live-validated: 13 unpaid receivables read correctly, incl. partial payments.**
  - [x] `aged_unpaid` + `render_aging_digest` — outstanding-AR digest ("10 unpaid invoices outstanding, $27,681.50") with past-due labels only when payment terms are configured. **Live-validated.**
  - [x] Wired to the conversational surface: "what's outstanding / who owes us / aging" → live outstanding-AR digest (read-only, via `receivables_reader`)
  - [ ] Gated reminder action (draft-then-approve dunning note)
  - [ ] Live-prove the digest through Slack (ask "who owes us" → digest in-thread)
- [ ] **2. Exception / profit radar** — on the same reads: delivered-not-invoiced, invoice overdue,
  duplicates, detention/accessorial leakage, missing POD, and later insurance/authority expiry → one
  "needs your attention" surface
- [ ] **3. AP reconciliation + fraud mesh** — prove the built rate-con-vs-carrier-invoice →
  record_payable path live, then harden duplicate-pay and unapproved-accessorial detection
- [ ] **4. Document auto-filing + compliance** — file POD/BOL to FileSafe, quality-check signatures/
  readability, match rate cons, monitor carrier packet expiries
- [ ] **5. Broker credit defense** — MC/DOT lookup, factoring/credit source integration, exposure limit
  check, Slack alert before accepting risky freight
- [ ] **6. Long tail** — margin-per-load, aging/P&L surfacing, status/check-calls

### Productionization gate (parallel track — needs infra/host, not new capability)
- [ ] Always-on host + continuous multi-hour unattended run
- [ ] Multi-tenant store + hosted browser pool + onboarding automation
- [ ] Observability dashboards, alerting, tenant-isolation guarantees

---

## Changelog (most recent first)

- **2026-07-06** — AR collections shipped (reader + aged digest, live-validated: 13 unpaid, $27,681.50
  aged) and wired to the conversational surface ("who owes us / what's outstanding" → live aged-AR
  digest). Full suite 619 green.
- **2026-07-06** — Conversational front door shipped: reply in plain English → answer or gated proposal
  (`152b259`); "bill load N" resolves the amount from the TMS itself (resolver). Owner-operator roadmap
  locked as the source of truth (`7085358`).
- **2026-07-06** — Autonomous AR runner: graduated loads auto-invoice unattended, fenced+capped+receipted (`714a774`).
- **2026-07-05** — Run receipts show the full path (`2b1eaff`); detail-page POD decision logic (`fa7d502`).
- **2026-07-05** — POD-gated billing (`174e3c4`); knowledge-base content moderation (`61dbc2b`).
- **2026-07-04/05** — AR loop proven live end-to-end twice (invoices #560010, #560011).

---

## Where are we, in one line

**Spine proven + assistant front door live + AR collections reading live (invoice + aging both work).
Building breadth across the back office. ~45% of owner-desired operations covered, on ~80%-built
machinery. Next: gated dunning reminders (outward-facing → draft-then-approve), then exception radar.**
