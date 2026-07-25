# Event Family F12 — Rule Events

*Registry: `events/registry.md`. Producer: machine M12. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=rule`; ordering = **STRICT per-aggregate** (`rule_version` monotonic); security=`high`; projection = **none**; audit=`high`.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`RuleProposed`** RU-1 | proves a natural-language instruction was submitted as a candidate · ¬proves it is enforceable | `source_instruction`(R), `scope`, `kind` | M12 (compile) | `actor_type∈{human,model-proposal-text}` (ER-9); `test_ev_ruleproposed` |
| **`RuleCompiled`** RU-2 | proves the candidate compiled to a deterministic predicate over modelled, non-inferred fields | `rule_id`(R), `compiled_predicate`(R), `test_vectors[]`(R) | Oversight (shows the owner what it would block) | ### **references only MODELLED, NON-INFERRED fields (GR-8)**; `test_ev_rulecompiled_deterministic` |
| **`RuleNotEnforceable`** RU-2f | ### **proves the instruction CANNOT become a rule — and the owner is told it is NOT enforced** · ¬proves enforcement | `missing`(R, e.g. `commodity`) | Oversight (honest reply) | ### **the L-C resolution: the reply MUST NOT claim "Noted the procedure" (M-64, T16)**; `test_ev_rulenotenforceable_reply_is_honest` |
| **`RuleConfirmed`** RU-4 | proves the owner confirmed the compiled rule (having seen its test vectors) | — | M12 (activate) | `actor_type=human`; `test_ev_ruleconfirmed` |
| **`RuleActivated`** RU-5 | ### **proves an AUTHENTICATED human activated an enforceable rule** | `rule_id`(R), `rule_version`(R), `activated_by`(R) | checkpoint (step 6 GATE_PRECONDITION/CONSTRAINT); M7 (conflict detection) | ### **`actor_type=human` ONLY; a model/automation ⇒ `UnauthorizedPolicyActivationAttempted` (F14)**; `test_ev_ruleactivated_human_only` |
| **`RuleSuperseded`** RU-6 | proves a newer version replaced this one (this one still explains history) | `superseded_by` | Audit | old version retained (ER-7); `test_ev_rulesuperseded_retained` |
| **`RuleRevoked`** RU-7 | proves a rule was revoked | `revoked_reason`, `direction` | checkpoint | narrowing may be automation; broadening the Policy Owner (ER-12); `test_ev_rulerevoked_direction` |

## Cross-cutting
**Dedup:** transition-natural; `rule_version` monotonic. **Ordering:** STRICT. **Replay:** decisions explained under the rule versions at their checkpoint. **Projection:** none. **Security:** ### **a model proposes text; it never compiles/activates/evaluates/resolves — "Noted the procedure" is forbidden unless a `RuleActivated` exists (M-64)**; two conflicting active rules ⇒ `ConflictRaised{RULE_VS_RULE}` (F7), fail closed (GR-15). **Audit:** `high` — `source_instruction` + compiled predicate + test vectors. **Open validation:** V4/V5 (which rules); Q3 (never auto-disable a wrong rule — it asks) — fail-closed.
