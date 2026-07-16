# W3 Compliance Acceptance *(AC-WF3-*)*
*Source: `workflows/W3-compliance.md`, Operating Model L3.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF3-001** | ### **onboarding does NOT imply permanent qualification** | an onboarded carrier + expired insurance ⇒ later booking **blocked** |
| **AC-WF3-002** | ### **qualification is time- AND movement-specific** | the decision carries `evaluated_at`+`scope`; a different movement re-evaluates |
| **AC-WF3-003** | ### **stale/unavailable authoritative data FAILS CLOSED** | FMCSA unavailable at qualification ⇒ **block the tender**; ### **assert NEVER "assume qualified"** |
| **AC-WF3-004** | ### **model fraud signals remain CLAIMS** | `MODEL_INFERRED` ⇒ `FraudSignalRaised` + narrow autonomy; ### **the model never makes the final trust decision** |
| **AC-WF3-005** | owner decisions recorded with evidence | `OWNER_ASSERTED` + `decision_ref` + the input compliance-record versions pinned |
| **AC-WF3-006** | expiration creates Expectations + blocking | a durable timer on `expires_at` ⇒ Expectation ⇒ block |
| **AC-WF3-007** | qualification change **invalidates dependent work** | an authority change post-decision ⇒ the next tender re-evaluates and blocks |
