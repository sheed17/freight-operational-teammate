# W10 Customer Comms Acceptance *(AC-WF10-*)*
*Source: `workflows/W10-customer-comms.md`, Operating Model L10.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF10-001** | comms obligations are **explicit Expectations** | a reply owed / a commitment made ⇒ a tracked Expectation |
| **AC-WF10-002** | ### **sent ≠ delivered** | RECEIPT proves transmission; ### **assert no "delivered" field written** |
| **AC-WF10-003** | ### **delivered ≠ acknowledged** | delivery ≠ compliance; the Expectation stays until acknowledged where required |
| **AC-WF10-004** | ### **quoted/forwarded content is NOT a new commitment** | a forwarded promise ⇒ no Expectation without corroborating evidence |
| **AC-WF10-005** | customer-specific comms rules apply **deterministically** | a compiled rule; ### **an uncompilable instruction ⇒ honest memory + the owner TOLD** |
| **AC-WF10-006** | ### **stale operational info cannot be represented as current** | a `DECISION_SUPPORT_READ` renders `as_of`+`stale`; ### **assert no undisclosed stale value in an outbound message** |
| **AC-WF10-007** | missed communications remain **owned work** | an `EXPIRED` Expectation ⇒ an Exception, owned |
| **AC-WF10-008** | ### **evidence links correctly WITHOUT assuming one thread = one load** | a thread spanning 2 loads ⇒ per-message bindings |
