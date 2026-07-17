# U2.6A — Explicit Tenant Source & WorkflowStore Construction Boundary

> ### **U2.6A binds a tenant. It does NOT make persistence tenant-safe.**
> ### **WorkflowStore is tenant-bound at construction, but its affected persistence methods remain noncanonical until U2.6B.**
> The 22 affected methods still issue their original unscoped SQL and the schema is still pre-migration. ### **A store that knows its tenant and does not use it is exactly that — calling this "tenant isolation" would be the most expensive lie available in this phase.**

**Starting commit:** `52ddff1`

---

## 1–6. The mechanical facts *(recomputed, not inherited)*
| Fact | Value |
|---|---|
| affected `WorkflowStore` methods | ### **22** (13 write · 9 read) — the earlier **44** was a regex over-count, superseded |
| construction sites | ### **146** across 51 files (AST-derived) |
| production | **36** · **test** 109 · **migration tool** 1 |

## 7–8. `CallbackAppConfig` + the canonical tenant source
### **`tenant` is the FIRST field, required, validated in `__post_init__`.** A config without a tenant cannot be spelled, and it fails at configuration time — before a store exists. `run_callback_server` requires it too, so no caller can satisfy the config by already knowing.

**Canonical source: `client_id` from the client configuration** — mechanically confirmed against every condition: it names the Neyma workspace (`rasheed_first_design_partner`, `neyma_test_freight`), it is config-stable, two tenants cannot share it, it is present before persistence, it is **not** a counterparty, **not** a display name (there is no `name:` field), and `design_partner_package.py` already asserts `client_id_present`.

## 9–13. Sites migrated
### **146 / 146. Zero unclassified. Zero remaining without a tenant** — asserted by AST, not by grep.
- **Production (36):** `config.tenant` where the config is in scope; `resolve_cli_tenant(--tenant | --client-config)` at CLI entry points; ### **`tenant_from_client_config(client_config_path)` where a function already receives the config — derived at the point of use rather than threaded through a new parameter.**
- **Tests (109):** explicit `tenant-fixture-a` / `-b`. ### **`require_tenant` refuses `"test"`, so a fixture value cannot pose as production.**
- **Migration tool (1):** ### **`--tenant` is REQUIRED.** It will not pick one.
- **Blocked: 0. Removed: 0.**

`tenant` is **keyword-only** everywhere — there is no positional slot to forget and no ordering to get wrong. Three helpers (`_start_batch/_operation/_resume_background_run`) now take it explicitly: ### **the tenant travels WITH the work, because a background worker that looks up its own tenant is a worker that can look up the wrong one.**

## 14–15. Rejected, structurally
`require_tenant()` refuses `None`, non-strings, empty, blank, and **20 sentinels** (`default`, `global`, `unknown`, `test`, `shared`, `system`, …), **case-insensitively**. Rejected inference paths: hardcoded literal · first-tenant-in-DB · env fallback · document hash · load id · email · a tenant read from an unscoped row · singleton-workspace assumption · ### **ambient / thread-local / process-wide current tenant (guarded: a global with better manners is still a global).**

## 16. Guards added *(17 tests, every one proving a non-zero population)*
constructor requires/validates/immutable · keyword-only, no default · `CallbackAppConfig` required+validated · **every one of 146 sites explicit** · no production fixture tenant · no sentinel · ### **no production tenant LITERAL at all** (a hardcoded tenant is a default spelled once per file) · migration tool asserts · no ambient tenant · the canonical source resolves · **`AC-SEC-001` still red** · ### **a test that asserts U2.6A does NOT claim isolation** — a marker of an intermediate state that *should* fail and be replaced when U2.6B lands.

## 17. Mutation results — ### **15/15 DETECTED**

### ⛔ A THIRD SUBSTRING FALSE POSITIVE — IN MY OWN GUARD
The final run failed on the **null-gate probe**: it scans for the gate decision `FORBIDDEN`, and U2.6A's new `FORBIDDEN_TENANTS` sentinel list contains that word. ### **The probe reported that typed policy had arrived at Phase 2 because a constant was named well.** Fixed with whole-token matching. ### **This is the same class as the report guard that tripped over "DELETED" in a docstring — a scanner that matches fragments will eventually match the wrong thing, and it fails in the direction that looks like news.**
tenant optional · default introduced · `require_tenant` bypassed · sentinels un-refused · a production site omits tenant · a test site omits tenant · `"default"` hardcoded · a fixture tenant in production · **any** literal in production · config tenant optional · tenant made mutable · ambient tenant appears · migration tool loses its assertion · **the parser evaluates zero sites** · AC-SEC-001 falsely greened · a U2.6A test weakened to skip. All restored, bytecode purged, digests verified.

### ⛔ THE SAME HOLE, FOR THE THIRD TIME
The skip-ban globbed `test_phase0_*`; a Phase-1 skip slipped through, so it was widened to `test_phase1_*`; ### **a U2.6A skip then slipped through the widened version.**
> ### **A guard that enumerates the files it knows about will always lag the next file added — and it fails SILENT, which is the only failure mode that matters here.** Fixed properly: guard files are now **discovered**, not listed. I widened a list twice before noticing the list was the bug.

## 18–21. Status
| | |
|---|---|
| **AC-SAFE-012** | ### **GREEN** |
| **AC-SAFE-013** | ### **GREEN** |
| ### **AC-SEC-001** | ### **RED — correctly.** The live schema is untouched; 7 of 8 tables are still not tenant-first. ### **Asserted by a test, so U2.6A cannot drift into claiming it.** |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |

## 22. Hardcoded knowledge-base defaults — ### **recorded, NOT fixed**
`ops_control.py` (5 sites) + `action_callback.py:1639` pass ### **`tenant="default"`** to the **knowledge base** — a different store, outside the seven-table scope, so untouched per the brief. **PRESENT_BUT_UNSAFE** · runtime: Slack ops surface · removal: the phase that makes the KB tenant-safe · condition: a canonical tenant reaches `KnowledgeBase`. ### **It is exactly the pattern this phase forbids, and it is on the record rather than found later.**

## 23. Legacy modules touched
`workflow.py` **ADAPT** (22 methods await U2.6B) · `action_callback.py` **ADAPT** · `mailbox_workflow.py` **ADAPT** · `tenant.py` / `cli_tenant.py` **KEEP** (canonical boundary) · `migrations/` **KEEP** · the 19 CLI scripts **ADAPT** · `ops_control.py` **ADAPT** (KB default).

## 24–25. Final suite + final-tree validation
| | |
|---|---|
| **Final suite** | ### **`879 passed · 1 skipped · 0 failed`** |
| validation start tree | `2901253442f873b1c7d7f3a9cf5007c81ec61b8d` |
| validation end tree | `2901253442f873b1c7d7f3a9cf5007c81ec61b8d` |
| ### **all three match** | ### **`✔ — run LAST, against the exact tree committed`** |

## 26–27. Remaining work
- ### **U2.6B** — scope all **22** methods (13 write, 9 read). ### **All 22 together: a store where some methods are tenant-safe and others are not READS as safe, which is worse than one where none are.**
- **U2.6C** — activate the staged migration (`--assert-tenant` or quarantine) ⇒ then and only then `AC-SEC-001`.

## 28–29. Is U2.6A complete? ### **Yes.** May U2.6B begin? ### **Yes.**

---

# VERDICT

## ### **READY TO BEGIN U2.6B**

**Carried forward:** ### **U2.6A is a construction boundary, not tenant isolation** — 22 methods still unscoped, schema still pre-migration, `AC-SEC-001` still red. ### **R-07 remains OPEN — NOT CONTAINED.** The knowledge-base `"default"` tenants remain unresolved and recorded.
