# Adapter Family 02 — TMS Adapter *(A4)*

*Registry: `adapters/registry.md`. The system-of-record adapter — the proving ground (TruckingOffice, live, browser-actuated).*

**Purpose.** Read/write the customer's TMS — loads, invoices, payables, documents, status, appointments — as **projected Observations** (in) and **`CONSEQUENTIAL_EFFECT` writes** (out) through the Action Pipeline. **Not.** ### **NOT authoritative for real-world completion (a TMS status field is a claim, not proof — CD-15); NOT the owner of any domain entity (it is a projection source + an effect target); NOT reachable directly.** **Direction.** bidirectional. **Vendors.** TruckingOffice (live, via A15 Browser), transporters.io (n=2 proof), API-based TMSs — same contract; ### **the write model must be flow-aware, not single-form-shaped (per the transporters.io finding).** **Auth.** ### **`human_established_session_only` — Neyma NEVER holds TMS credentials; the human logs in, Neyma attaches (via A15).** **Mapping.** every load/invoice/... binds via **External Entity Mapping**; ### **the TMS `load_ref`/invoice number is trusted ONLY within `(tenant, TMS)` (H19: two tenants, same external load id ⇒ no collision).**

## Capability contracts
| Op | name | action class | class | verification | Commit Key / Material Facts | notes |
|---|---|---|---|---|---|---|
| A4-1 | `read_loads` | — | ### **`DECISION_SUPPORT_READ`** | n/a | — | the AR/ready-to-bill digest; ### **cached fallback allowed WITH disclosed `as_of`+`stale` (V-1)** |
| A4-2 | `read_load_amount` | — | ### **`CONSEQUENTIAL_FRESHNESS_READ`** | n/a | — | ### **the amount bound into a money action — LIVE ONLY; the reader's constructor CANNOT accept a cache (V-3); this is the read the checkpoint step-3 consumes** |
| A4-3 | `read_invoice_status` (at checkpoint) | — | `CONSEQUENTIAL_FRESHNESS_READ` | n/a | — | already-invoiced guard; live |
| A4-4 | `enter_customer_invoice` | `RAISE_INVOICE` | ### **`CONSEQUENTIAL_EFFECT`** | ### **READBACK_VERIFIABLE** | CK = `(tenant, RAISE_INVOICE, tms, load:<id>, create_invoice, occ="")` — ### **amount NOT in CK**; MF = {load, customer, amount, packet digests, provenance} | requires grant+witness; POD-gated (CD-3) |
| A4-5 | `enter_carrier_payable` | `RECORD_PAYABLE` | `CONSEQUENTIAL_EFFECT` | READBACK_VERIFIABLE | CK = `(…, RECORD_PAYABLE, load:<id>, …)`; MF = {carrier, remittance_party, amount, ratecon, authorized accessorials} | HUMAN_APPROVAL_REQUIRED (money-out); CD-4/CD-5 |
| A4-6 | `record_payment` | `RECORD_PAYMENT` | `CONSEQUENTIAL_EFFECT` | READBACK_VERIFIABLE | CK occ = remittance ref (ADR-009); MF = {invoice, amount} | — |
| A4-7 | `attach_document` | `FILE_DOCUMENT` | `CONSEQUENTIAL_EFFECT` | READBACK_VERIFIABLE | CK occ = **content digest**; MF = {load, doc type, digest} | ### **the document fence: the runtime supplies the file (a model path can never become an upload)** |
| A4-8 | `update_status` / `assign_carrier` | `UPDATE_LOAD`/`BOOK_CARRIER` | `CONSEQUENTIAL_EFFECT` | READBACK_VERIFIABLE | CK by target+operation | BOOK_CARRIER gated by Qualification (CD-2) |

## READBACK_VERIFIABLE specifics *(every A4 effect)*
- ### **exact target addressing:** the specific load/invoice record by its stable id (not a search); ### **verification keys on the approved Material Facts (amount+party), not on a guessed record number (the TMS may renumber — H5: a readback finding a DIFFERENT recently-created invoice ⇒ `OBSERVATION_CONFLICTING`, never a false success).**
- ### **fresh-read required; stale-page detection = the positive health control (a known-present sentinel; "the page loaded" is NOT health — a logged-out page also loads); cache-defeating (a fresh navigation/query).**
- **mismatch ⇒ `OBSERVATION_CONFLICTING` ⇒ `UNKNOWN_OUTCOME`; blind ⇒ `OBSERVATION_UNAVAILABLE` ⇒ `UNKNOWN_OUTCOME`; healthy-and-absent ⇒ `VERIFIED_FAILURE`.**

## Unknown outcomes *(H3, H4, H7)*
### **API timeout after creating an invoice (H4) / browser crash after submit (H3) / session expiry after grant claim (H7) ⇒ the adapter returns STRUCTURED EXECUTION EVIDENCE (what it submitted, the last observed page/response) and NEVER decides — the Pipeline/Effect machine goes `UNKNOWN_OUTCOME` (never `FAILED`); entity frozen, commit_key held, human asked.**

## Cross-entry-point mutual exclusion *(H8, R-02)*
### **All write-capable paths (this adapter + the direct-terminal scripts) share the ONE Effect Grant Ledger + Commit-Key namespace: `UNIQUE(tenant, commit_key) WHERE state='CLAIMED'` ⇒ two entry points attempting the same logical effect ⇒ exactly one claims (H8). Until the cutover, the runbook one-writer-at-a-time discipline holds; the ledger is the real fix.**

## Migration Safety Task #1 *(preserved, NOT implemented)*
> ### **The canonical Commit Key above (amount NOT in it, mandatory for every effect incl. non-money) is the target. The current `commit_identity` includes `approved_amount` and is absent for non-money effects — a live double-billing hole. This contract SPECIFIES the fix; the code change is the first migration task, not this phase.**

**Acceptance.** `test_a4_amount_read_is_consequential_freshness_no_cache`; `test_a4_readback_verifies_approved_facts_not_record_number` (H5); `test_a4_timeout_after_create_is_unknown_not_failed` (H4); `test_a4_two_entry_points_one_claims` (H8); `test_a4_commit_key_excludes_amount`; `test_a4_document_fence_runtime_supplies_file`. **Adversarial.** H3, H4, H5, H6, H7, H8, H19. **Open.** flow-aware write model per TMS; API vs browser per vendor — NEEDS VALIDATION.
