# W2 Procurement Acceptance *(AC-WF2-*)*
*Source: `workflows/W2-procurement.md`, Operating Model L2.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF2-001** | ### **candidates remain CANDIDATES until identity + qualification pass** | a search result/offer never becomes an Assignment; ### **assert no Assignment row exists** |
| **AC-WF2-002** | ### **MC/DOT deterministic confirmation enforced** | confirmation only on an exact MC/DOT; ### **at confidence 1.0 an alias ⇒ `AMBIGUOUS`** |
| **AC-WF2-003** | ### **aliases cannot independently confirm identity** | board name / email signature / factoring alias ⇒ candidate signals only |
| **AC-WF2-004** | prohibited-carrier rule **blocks** selection | a compiled `do_not_use` rule ⇒ checkpoint step-6 deny |
| **AC-WF2-005** | ### **qualification freshness checked at the CORRECT consequential point** | ### **qualified at selection, SUSPENDED before acceptance ⇒ the booking-time read blocks (CD-2)** |
| **AC-WF2-006** | Carrier Offer and Assignment remain **distinct** | 2 tables, 2 lifecycles |
| **AC-WF2-007** | duplicate outreach controlled | dedup on the source-natural key |
| **AC-WF2-008** | ### **carrier falloff reopens/creates the proper obligation** | `FELL_OFF` ⇒ a NEW Movement (Load→Movement 1:N); the `COVER_LOAD` reopens a phase |
| **AC-WF2-009** | ### **closure requires a valid Assignment or explicit disposition** | signed Rate Con + verified remittance, else unserviceable/escalated with a `decision_ref` |
| **AC-WF2-010** | verbal-vs-written rate con ⇒ **version + Conflict** | ### **no silent overwrite (CD-16)** |
