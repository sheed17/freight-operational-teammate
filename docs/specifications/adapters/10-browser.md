# Adapter Family 10 — Browser Actuation Adapter *(A15)*

*Registry: `adapters/registry.md`. ### **A first-class adapter, NOT a temporary hack** — the actuation substrate under browser-only systems (the live TMS).*

**Purpose.** Drive a real browser (CDP) to read and act on systems that expose no API, translating pages into **Observations + Evidence** and clicks/types/uploads into **`CONSEQUENTIAL_EFFECT`s through the Action Pipeline**. **Not.** ### **NOT a decision-maker; NOT a credential holder; NOT reachable except with a valid grant+witness.** **Direction.** bidirectional.

## Session & isolation
- ### **`human_established_session_only` — a human logs into the external system; Neyma ATTACHES to that session (CDP). Neyma never holds nor types the external credentials.**
- **Credential-vault posture:** ### **none for external systems** (there is no vault of TMS passwords); only Neyma's own service creds live in `.env` (gitignored).
- **Tenant isolation:** ### **one browser profile per tenant session; a profile is never shared across tenants; a page returning another tenant's data ⇒ `CrossTenantAccessAttempted` (H30) ⇒ GLOBAL brake.**
- **Concurrency:** ### **a `browser.busy` lock serializes writes on one session (a write holds it); a read during a write busy-falls-back to the cache ONLY for informational/decision-support reads — never for a `CONSEQUENTIAL_FRESHNESS_READ`.**

## Page identity, staleness, targeting
- **Page identity:** URL + an authenticated-session marker + expected structure. ### **Stale-page detection = a POSITIVE health control (a known-present sentinel element); "the page loaded" is NOT health (a logged-out page also loads).**
- **Navigation verification:** after navigate, confirm the target record is addressed (not a search-result guess).
- **Element targeting:** ### **the runtime validates each proposed step against the allowed operation contract; a model may PROPOSE steps, the runtime executes only contract-allowed ones (page-content prompt injection ⇒ `PromptInjectionSignal`, bounded to a proposal, H11).**
- **Evidence:** ### **DOM snapshot + accessibility tree + a screenshot are captured as content-addressed Evidence per consequential action** (the "why did you click that" record).
- **Partial-render detection:** settle-detection before reading/acting; a partial render ⇒ `OBSERVATION_UNAVAILABLE`, never a false read.
- **Downloads/uploads:** ### **`DOM.setFileInputFiles` — the runtime supplies the file (the document fence); a model path can never become an upload.** **Multi-tab:** each tab is a distinct page identity; actions bind to the intended tab.

## Effect + verification
| Op | class | verification | notes |
|---|---|---|---|
| A15-r | `read_page` | per the caller's read class | n/a | a `CONSEQUENTIAL_FRESHNESS_READ` cannot use the busy-cache |
| A15-w | `actuate` (click/type/upload/submit) | ### **`CONSEQUENTIAL_EFFECT`** | ### **READBACK_VERIFIABLE** | ### **the adapter's sole entry point requires a grant AND a fresh witness (two-key); a stale witness (brake/policy moved) ⇒ refuse (`StaleWitnessUsed`); it navigates/acts ONLY after a valid capability** |

## Unknown outcomes & interruptions
### **A click succeeds but the browser crashes before the response (H3); a session expires after the grant claim (H7); an anti-bot/MFA challenge interrupts mid-effect — in every case the adapter returns STRUCTURED EVIDENCE (the last DOM/screenshot, what was submitted) and NEVER decides. The Effect machine ⇒ `UNKNOWN_OUTCOME` (never `FAILED`); the human is asked with the exposure.** MFA/anti-bot on a READ ⇒ `OBSERVATION_UNAVAILABLE`.

## Brake
### **A brake between checkpoint and claim ⇒ the claim CAS matches zero rows, the browser never actuates (H26). A brake after claim, before the external response (H27) ⇒ the in-flight actuation runs to verification (the brake never kills the worker — GR-16); the NEXT effect is refused.**

**Acceptance.** `test_a15_attaches_human_session_never_holds_creds`; `test_a15_stale_page_needs_positive_health_control`; `test_a15_actuate_requires_grant_and_fresh_witness`; `test_a15_crash_after_submit_is_unknown`; `test_a15_page_injection_bounds_to_proposal`; `test_a15_upload_is_document_fence`; `test_a15_cross_tenant_page_engages_global_brake`. **Adversarial.** H3, H7, H11, H26, H27, H30. **Open.** anti-bot/MFA handling policy; per-vendor DOM stability — NEEDS VALIDATION.
