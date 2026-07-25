# Adapter Boundary Acceptance *(AC-ADPT-*)*

*Registry defaults apply. Level: `ADAPTER_CONTRACT`. Gate: **G3**.*

## Coverage: **every canonical adapter operation** (A1–A18, ~40 ops). `AC-ADPT-000` (`STRUCTURAL`) asserts a bijection between the implementation's operation registry and the frozen contracts — every op declares its **class** (1 of 4) and its **verification mode** (1 of 3), or the build fails.

## The contract simulator *(where no vendor sandbox exists)*
> ### **A DETERMINISTIC contract simulator per adapter, driven by the frozen contract — NOT by the implementation.** It records **every** call (the call log is the negative oracle), can inject each failure in the taxonomy, and can be scripted for stale pages, timeouts, partial renders, MFA interrupts, and cross-tenant leakage. ### **A simulator written from the implementation instead of the contract is a false-pass loophole (L-9) — the simulator lives with the spec.**

## Mandatory assertions
| ID | Assertion | Oracle |
|---|---|---|
| **AC-ADPT-001** | inbound adapters produce **only** permitted outputs | Observations/Evidence/Claims/mappings/security signals — ### **assert NO `OWNER_ASSERTED`, no policy/brake/approval/grant/witness produced** |
| **AC-ADPT-002** | ### **outbound adapters unreachable without capability** | call without grant/witness ⇒ refuse; ### **CI import-graph: no module outside `pipeline/` imports `adapters/`** |
| **AC-ADPT-003** | ### **informational cache CANNOT satisfy consequential freshness** | ### **the `CONSEQUENTIAL_FRESHNESS_READ` constructor REJECTS a cache path — a construction/compile failure, proven by NEGATIVE CONTROL (inject a cache_path ⇒ the guard fires)** |
| **AC-ADPT-004** | each op uses its **declared** verification mode | mode registry vs runtime behavior |
| **AC-ADPT-005** | `READBACK_VERIFIABLE` reads the **exact target** | ### **a decoy: a different recently-created record exists ⇒ verification matches the APPROVED facts, not the decoy ⇒ `OBSERVATION_CONFLICTING`** |
| **AC-ADPT-006** | `RECEIPT_VERIFIABLE` distinguishes **transmission from business completion** | SMTP 250 ⇒ `ATTEMPTED`+Expectation; ### **assert NO "delivered/received/read" field is ever written** |
| **AC-ADPT-007** | ### **`UNVERIFIABLE` ops remain NON-AUTONOMOUS** | a startup check: such an op with `AUTONOMOUS_WITHIN_CAPS` ⇒ **fails to start** |
| **AC-ADPT-008** | ### **adapter-provided provenance fields are IGNORED** | a response carrying `provenance_class` ⇒ ignored + `ProvenanceStrengtheningAttempted` |
| **AC-ADPT-009** | ### **external schemas cannot mutate the canonical ontology** | a vendor field with no domain concept ⇒ **evidence only**, no new domain column |
| **AC-ADPT-010** | duplicate inbound delivery deduplicated | webhook+poll of one message ⇒ 1 Observation + 1 `ObservationConfirmed` |
| **AC-ADPT-011** | ### **session expiry after claim ⇒ the canonical outcome** | ⇒ `UNKNOWN_OUTCOME` + structured evidence; ### **NEVER `FAILED`** |
| **AC-ADPT-012** | ### **browser stale-page detection is POSITIVE, not page-load-based** | ### **serve a logged-out page that "loads fine" ⇒ `OBSERVATION_UNAVAILABLE`, NEVER `VERIFIED_FAILURE`** |
| **AC-ADPT-013** | tenant browser profiles isolated | `T_A`/`T_B` sessions ⇒ no cookie/profile bleed |
| **AC-ADPT-014** | ### **no adapter performs policy or commercial judgment** | a code/structural probe: no policy evaluation or rate decision inside `adapters/` |
| **AC-ADPT-015** | ### **no adapter converts `UNKNOWN_OUTCOME`→`FAILED`** | the adapter returns **structured evidence only**; the machine decides |
| **AC-ADPT-016** | ### **another tenant's data is contained + escalated** | ⇒ rejected pre-ingestion + `CrossTenantAccessAttempted` + GLOBAL brake |

**Per-adapter anchors:** `AC-ADPT-A4-*` (TMS: the amount read is cache-free; the decoy readback; two-entry-point exclusion; ### **`MIGRATION_GUARD`: the current `commit_identity` includes the amount and is absent for non-money effects — a recorded, failing-by-design guard until the migration fixes it**). `AC-ADPT-A15-*` (browser: positive health, human session, document fence, brake-vs-claim). `AC-ADPT-A14-*` (oversight: transports never invents; ordinal→immutable id or fail closed).
