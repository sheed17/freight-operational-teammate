# W1 Quote Acceptance *(AC-WF1-*)*
*Registry + `workflow-acceptance.md` master apply. Source: `workflows/W1-quote.md`, Operating Model L1. Gates: G5–G9.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF1-001** | demand produces a **correctly scoped** quote obligation | one `QUOTE_TO_COMMITMENT` Work Item, owned; ### **duplicate demand ⇒ `ObservationConfirmed`, still ONE Work Item** |
| **AC-WF1-002** | pricing evidence has **valid freshness** | market-rate evidence carries `as_of`+`expires_at`; a `DECISION_SUPPORT_READ` discloses `stale` |
| **AC-WF1-003** | ### **stale evidence blocks or requires the specified human handling** | evidence past `expires_at` ⇒ the sell basis is `stale` ⇒ **re-price or human-confirm**; ### **assert NO autonomous send** |
| **AC-WF1-004** | ### **a model-suggested rate cannot silently become a commitment** | the suggestion is `MODEL_INFERRED`; ### **the send is `HUMAN_APPROVAL_REQUIRED`; a model actor attempting `SEND_QUOTE` ⇒ zero external calls + a security event** |
| **AC-WF1-005** | Quote Versions **preserve prior commercial history** | a re-price adds a version; ### **the prior version row is byte-identical after** |
| **AC-WF1-006** | delivery ≠ acceptance | `SENT` ≠ `ACCEPTED`; Work Item open (AC-FC-001) |
| **AC-WF1-007** | expiry enforced | a durable timer (clock-advanced, not slept) ⇒ `EXPIRED` |
| **AC-WF1-008** | counteroffer creates the canonical next phase | a new Quote Version; the prior retained |
| **AC-WF1-009** | ### **accepted quote creates DURABLE downstream obligations** | `CONVERTED` ⇒ Order + Load(s) + a `COVER_LOAD` Work Item **in the same commit**; ### **crash between ⇒ neither (AC-FC-016)** |
| **AC-WF1-010** | ### **quote acceptance does NOT falsely close Procurement** | W2 `COVER_LOAD` is OPEN after acceptance (AC-FC-002) |
| **AC-WF1-011** | one order → two loads | 2 Loads, 2 `COVER_LOAD` Work Items, no identity collapse |
| **AC-WF1-012** | owner loss / policy narrow / brake / degraded / replay | per the master's 18 dimensions |
