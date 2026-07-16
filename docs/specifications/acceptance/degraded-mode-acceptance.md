# Degraded-Mode Acceptance *(AC-DEG-*)*
*Registry defaults apply. Level: `WORKFLOW`/`END_TO_END`. Gate: **G7**. ### Every loop × every degraded mode.*

## The matrix: 11 loops × 11 modes
Modes: `no TMS API` · `read-only TMS` · `browser-only TMS` · `no portal access` · `email-only counterparties` · `spreadsheet operational source` · `missing tracking provider` · `missing accounting integration` · `delayed documents` · `external-system outage` · `human-executed consequential action`.
**ID:** `AC-DEG-<Wn>-<mode>`.

## The seven universal assertions *(every cell)*
| # | Assertion | Oracle |
|---|---|---|
| **1** | ### **observations and preparation remain USEFUL** | the loop still produces the prepared effect + the missing-evidence list; ### **assert a non-empty operator-visible output** |
| **2** | ### **autonomous authority NARROWS** | the gate for the affected action class ⇒ `HUMAN_APPROVAL_REQUIRED` or blocked; ### **assert autonomy NEVER broadened by an outage** |
| **3** | human ownership remains **explicit** | the Work Item keeps a named owner throughout |
| **4** | ### **evidence can be captured AFTER an out-of-band action** | the human acts externally ⇒ Neyma ingests the resulting Observation and reconciles the projection |
| **5** | ### **the system does NOT claim Neyma executed the human action** | ### **the audit records `actor_type=human`, out-of-band; assert NO `EffectAttempted`/grant exists for it** |
| **6** | closure still requires **authoritative evidence** | a human-executed write still needs a verified readback to close |
| **7** | ### **an unavailable integration NEVER causes false success OR false failure** | ### **⇒ `unknown`/`INDETERMINATE`/fail-closed — assert neither `VERIFIED_SUCCESS` nor `FAILED` is produced** |

## Named anchors
`AC-DEG-W6-readonly` — ### **the first-loop degraded proof: read-only TMS ⇒ Neyma classifies, binds, tracks missing docs, prepares the packet; the human files; Neyma verifies the readback and closes with them.**
`AC-DEG-W8-readonly` — Neyma prepares the invoice; the human enters it; Neyma reads it back and tracks collection to cash.
`AC-DEG-W5-notracking` — every milestone Expectation ⇒ `INDETERMINATE`; ### **assert zero false "on-time"/"late".**
`AC-DEG-all-outage` — an external outage at a required freshness checkpoint ⇒ ### **fail-closed, no effect (never "assume").**
