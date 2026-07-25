# W5 Tracking Acceptance *(AC-WF5-*)*
*Source: `workflows/W5-tracking.md`, Operating Model L5.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF5-001** | ### **provider position / provider status / carrier assertion / driver assertion / TMS status / derived ETA remain DISTINCT** | six distinct provenance classes on six rows; ### **assert no collapse into one "status"** |
| **AC-WF5-002** | stale tracking is **visible** | the position's `observed_at` is surfaced, never "now" |
| **AC-WF5-003** | ### **observability gaps ⇒ `INDETERMINATE`, NOT false lateness** | 6h provider outage across a deadline ⇒ ### **`INDETERMINATE`; assert NEVER `OVERDUE`/late/on-time** |
| **AC-WF5-004** | milestones create/discharge Expectations correctly | arrival/departure/delivery; a late arrival still discharges |
| **AC-WF5-005** | conflicting sources raise **Conflict** | provider vs TMS vs driver disagree ⇒ `ConflictRaised` |
| **AC-WF5-006** | ### **a delivery assertion does NOT close Documentation** | W6 `COMPLETE_DOCS` open (AC-FC-005) |
| **AC-WF5-007** | ### **detention timing uses correct LOCAL timezone semantics** | ### **an appointment window across a DST boundary evaluated in FACILITY-local time** |
| **AC-WF5-008** | ### **a derived ETA never gates** | `MODEL_INFERRED` ⇒ the checkpoint raises on read |
