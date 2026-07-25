# Observability & Audit Acceptance *(AC-AUD-*)*
*Registry defaults apply. Level: `END_TO_END`. Gates: **G2, G9**.*

## The explainability fixture `EX-1`
> A completed consequential trace (a POD→invoice→payment chain) **90 days old**, spanning **≥1 policy version change, ≥1 rule supersession, ≥1 model upgrade, ≥1 schema version**.

## The canonical explainability query + expected response semantics
> ### **`explain(effect_id)` MUST reconstruct ALL EIGHTEEN, using the beliefs OF THAT DAY — not current state:**
> what happened · who acted · **the accountable owner** · what was known · ### **what was UNKNOWN** · ### **what CONFLICTED** · what evidence existed · ### **the `provenance_class` of EVERY material fact** · ### **which entity versions were pinned (the SD-3 set)** · what approval existed · which **policy version** applied · which **brake version** applied · ### **WHY the checkpoint passed or failed (which of the seven)** · which **Commit Key** was held · what **adapter operation** ran · ### **what verification PROVED** · why the Work Item closed **or stayed open**.

| ID | Proves | Oracle |
|---|---|---|
| **AC-AUD-001** | all eighteen reconstructible | a field-by-field assertion over `EX-1` |
| **AC-AUD-002** | ### **historical explanation uses HISTORICAL context** | ### **change the policy/rule/model TODAY ⇒ `explain(EX-1)` returns the ORIGINAL versions — byte-identical to the pre-change response** |
| **AC-AUD-003** | ### **audit is append-only** | no UPDATE/DELETE grant on the audit/event tables; ### **a deletion attempt fails at the DB layer** |
| **AC-AUD-004** | evidence traversal from any canonical field | one query ⇒ the complete chain to the retained artifact |
| **AC-AUD-005** | latency | < 2s p95 against a warm full corpus |
| **AC-AUD-006** | ### **an UNKNOWN is explainable as UNKNOWN** | `explain` on an `UNKNOWN_OUTCOME` returns the reason, the exposure, what was tried, and the specific human question |
| **AC-AUD-007** | ### **metrics do NOT exclude unknowns** | ### **the safety-metric oracle asserts `UNKNOWN_OUTCOME` rate is REPORTED, not filtered (loophole L-17)** |
