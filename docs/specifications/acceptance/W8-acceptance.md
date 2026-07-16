# W8 Billing Acceptance *(AC-WF8-*)*
*Source: `workflows/W8-billing.md`, Operating Model L8. ### The first-loop destination. Closes at CASH.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF8-001** | eligibility derives from **authoritative rates + the required packet** | the amount is a live `CONSEQUENTIAL_FRESHNESS_READ`; the packet is `COMPLETE` |
| **AC-WF8-002** | ### **unsupported accessorials BLOCK release** | an accessorial with no Authorization ⇒ not eligible (CD-5) |
| **AC-WF8-003** | preparation ≠ release | `PREPARED` ≠ `ISSUED` (approval + checkpoint required) |
| **AC-WF8-004** | release ≠ delivery | `ISSUED` ≠ `SENT` |
| **AC-WF8-005** | ### **delivery ≠ cash** | ### **`SENT` ≠ `PAID`; only a VERIFIED Payment Application closes AR (AC-FC-009)** |
| **AC-WF8-006** | ### **duplicate billing prevented by the LOGICAL Commit Key** | ### **two proposals at £2,850 and £3,100 ⇒ ONE invoice (AC-SAFE-012)** |
| **AC-WF8-007** | ### **credit and rebill preserve original history** | the credit is a Compensation; the rebill is `REISSUE_INVOICE` (new CK); ### **the original invoice row byte-identical; no double-bill** |
| **AC-WF8-008** | short-pay + dispute **remain open until disposition** | `SHORT_PAID` ⇒ residual AR + a W7 obligation; ### **never silently closed** |
| **AC-WF8-009** | ### **the loop closes ONLY under the frozen AR closure rule** | `PAID` (default, P24) — or an authorized write-off / approved short-pay / credit-rebill settlement; ### **the exact disposition set is NEEDS VALIDATION** |
| **AC-WF8-010** | ### **the Documentation→Billing handoff is ATOMIC and DURABLE** | packet `COMPLETE` ⇒ `BILL_AND_COLLECT` in the same commit; ### **crash between ⇒ neither (AC-FC-016)** |
