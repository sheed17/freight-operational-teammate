# P9-CP-1 — the freight-domain spine, driven by twenty hostile load histories

**Implementer record. Not a review, not an acceptance.** This is the on-disk evidence that
`meta.status_model.execution_state` requires before a phase may be recorded `IN_PROGRESS`. The status
authority is [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) unit `P9` and
[`CURRENT.md`](CURRENT.md); this file establishes none.

> **The corpus is synthetic development input.** Nothing here is a design-partner observation, no
> freight rule is validated by it, and V-21 and V-14 remain **OPEN**.
> **No independent review has been performed.** Tier-1 surfaces were touched (§5); one focused
> independent review is owed before merge ([`CLAUDE.md`](../../CLAUDE.md) §7).

## 1. What a broker can now do that they could not before

Nothing in production — it ships dark. What now *exists* is the thing P10 needs: **a load can be
followed end to end as one canonical record.** Hand Neyma the TMS snapshots, tracking pings, emails,
texts, documents and staff actions for a load, in whatever order and however duplicated or
contradictory they arrived, and it produces:

- one canonical **Brokerage Load** with its order, movements, stops, appointments, parties, documents,
  messages, tracking events, accessorials and payables — every field carrying where it came from;
- an ordered **operational timeline** of what happened, when, in the timezone it happened in;
- what is **in dispute** (a Conflict with every party's statement), what is **owed and late** (an
  Expectation, OVERDUE only where the channel was provably up), and what a **human must decide** (an
  Exception with one named owner);
- whether the carrier's invoice **reconciles** against the rate confirmation, line by line;
- whether the load is **eligible to invoice**, and exactly why not.

Run it: `.venv/bin/python scripts/run_freight_corpus.py` (timelines + metrics, ~2 s) or `--json`.

## 2. What was built

| Piece | Where | What it is |
|---|---|---|
| External Entity Mapping | `migrations/phase9_external_entity_mappings.py`, `freight_domain/entity_mapping.py` | The one new durable table. Tenant-first, composite FKs, exact lookup on `(tenant, system, kind, id)`, four statuses (`EXACT` / `AMBIGUOUS` / `RETIRED_ONLY` / `UNMAPPED`), corrections retire and never edit or delete (triggers), no model provenance storable. |
| Composition module | `freight_domain/foundation.py` | The **only** module that imports the P6–P8 machines (M1, M5, M6, M7, M8, M9, Evidence, provenance, linker). |
| Canonical model | `freight_domain/model.py` | Entities with **field-level** provenance; a `Field` is the append-only history of what each source said and reports `absent` / `unknown` / `consistent` / `conflicting`; `DirectedMoney` (integer minor units + currency + direction + kind). |
| Input contract | `freight_domain/history.py` | What one inbound record looks like. The record names its channel and kind; the runtime derives provenance. Content declaring its own provenance is refused at any depth. |
| Intake | `freight_domain/intake.py` | observe → parse → resolve references (intersected) → bind → project → detect → materialize. Only a TMS row creates a load. |
| Projection | `freight_domain/projection.py` | Canonical entities as a **pure-read fold** over Observations, Identity Binding Claims and mappings. |
| Detectors | `freight_domain/detectors.py` | Pure functions returning intents — Conflicts, Expectations, Exceptions — handed to M7/M8/M9. |
| Reconciliation | `freight_domain/financial.py` | Financial Reconciliation Result per movement: rate confirmation vs carrier invoice. Zero tolerance; never adjusts. |
| Timeline | `freight_domain/timeline.py` | Operational Timeline Entry, derived from canonical records by template. |
| Runner + report | `freight_domain/corpus_run.py`, `scripts/run_freight_corpus.py` | One command; machine-readable report; labeled outcomes asserted one by one. |
| Corpus | `eval/freight_corpus/` | Twenty hostile histories, three brokerages, one database. |

**Canonical entities exercised** (of the registry's 40): Organization / Brokerage Tenant, Customer,
Customer Contact, Carrier, Carrier Contact, Driver, Customer Order, Brokerage Load, Carrier Movement,
Leg, Stop, Appointment, Rate Confirmation, Document, Document Requirement, Communication Thread,
Communication Message, Tracking Event, Accessorial Charge, Accessorial Authorization, Customer
Invoice (eligibility guard only), Carrier Payable, External Entity Mapping, Operational Timeline
Entry, Financial Reconciliation Result — **25**. **Not built:** Customer Location, Equipment, Facility
(carried as Stop fields), Quote, Quote Version, Carrier Offer, Tender, Carrier Assignment, Document
Packet, Customer Invoice Line, Carrier Payable Line (lines are values), Payment Application, Claim /
OS&D Case, Compliance Record, Carrier Qualification Decision — **15**.

## 3. How the open validation items were handled

Neither is answered. Each item's recorded **safe interim behaviour** is applied.

- **V-21 (cardinality).** Order, Load, Movement, Leg, Stop are distinct entities, FK on the child.
  The corpus exercises one load moved by two carriers (N15) and one order covering two loads (N08).
  With no order id from the TMS the order is *provisionally* one per load, recorded as such.
- **V-14 (pre-rate-con buy rate).** The rate confirmation is the only authoritative buy rate. A TMS
  carrier-pay field and a number agreed in a message are retained as `MODEL_INFERRED` and are
  invisible to every consequential read. With no rate confirmation the expected side is `absent` and
  a human is asked (C02). An **unsigned** rate confirmation never yields `RECONCILED` (H01) — whether
  an unsigned one governs is itself unvalidated.
- **V-15 / V-17.** An accessorial not on the rate confirmation is `UNRESOLVED` unless a recorded human
  authorized it. Never auto-approved, never auto-disputed. Zero tolerance on every line.
- **Customer configuration.** Which documents a load needs, by when, on which channel, is tenant
  setup. One brokerage configures a deadline (Northline), one configures the requirement with no
  deadline (Cedar Ridge — outstanding, no invented clock), one configures nothing (Harbor Point —
  `unknown`, not eligible).

## 4. What broke in the P0–P8 machinery when freight hit it

| # | Finding | Disposition |
|---|---|---|
| F-1 | **Three ships-dark guards could not fail.** M8's matched the substring `from .expectation`; the Evidence store's matched `node.module in (".evidence", …)`; the provenance module's matched `.endswith(".provenance")`. None sees a relative import from a subpackage, and the last two never saw even a sibling import (`lineage.py`, `linker.py`). All three stayed green with a new production importer on disk. | **Fixed.** One AST matcher (`eval/tests/dark_surface_kit.py`), proved on twelve spellings. |
| F-2 | **Every ships-dark guard asserted zero importers**, which P9 makes false by design. | **Replaced** (rule 20), not relaxed: eleven guards now assert an exact set naming one P9 module by path; the module is proved dark; each guard has a mutant. |
| F-3 | **M5 overwrites an Observation's source provenance at bind.** OB-3/OB-4 write the *binding's* provenance onto the row: a driver's text bound by exact id reads `LINKER_INFERRED`, and bound by a human reads `OWNER_ASSERTED`. Anything reading that column for what the content can bear would launder it (R-P2). | **Worked around, not fixed.** P9 records the acquisition at parse and derives every fact's provenance from that. Debt `P9-D1`. |
| F-4 | **M5 has no re-bind transition.** After a human corrects a binding (M6 IB-7), `observations.bound_entity_ref` still names the old load — and M8's discharge reads that column, so a corrected POD cannot discharge the right load's Expectation and would still discharge the wrong one's. | **Worked around.** The binding is read from M6's CONFIRMED claim; the right load's Expectation is discharged by the human's correcting act; the wrong load's requirement is re-raised. Debt `P9-D2`. |
| F-5 | **M8 called a blind window healthy when coverage records overlap.** `_coverage_verdict` took the first row spanning the window, so a `DOWN` outage recorded inside a `HEALTHY` month returned `OVERDUE` — blindness converted into counterparty fault (I8, M-32). | **Fixed in M8** (§5). Strictly fail-closed: it can only turn an `OVERDUE` into `INDETERMINATE`. |
| F-6 | **An Exception raised for a missed deadline stays open after the thing arrives.** Only a human or a registered rule closes an Exception, and the rule set is empty. | **Recorded.** P9 lists these as housekeeping, not attention. Debt `P9-D3`. |
| F-7 | **M6's propagation obligation is recorded and nothing consumes it.** | **Recorded** with F-4. Debt `P9-D2`. |
| F-8 | **One live Expectation per `(subject, type)`.** A second promise made while the first is live coalesces rather than being raised. | **Recorded.** Debt `P9-D6`. |

## 5. Safety surfaces touched — tier 1, independent review owed before merge

- **A migration**: `external_entity_mappings` joined the canonical schema (fresh == migrated proved by
  the existing walk; partition and baseline manifest updated).
- **Tenant isolation**: the mapping store, and a whole-database cross-tenant audit shown to fire.
- **Eleven ships-dark guards replaced**: M1, M5, M6, M7, M8, M9, Evidence, provenance, linker/lineage,
  the consolidated P7 guard, the U8.4 consumer guard.
- **M8 (`expectation.py`) changed**: the coverage verdict (F-5) — an accepted P8 machine, edited
  after acceptance.
- **Four machine byte-freeze guards edited**: `expectation.py` was removed from the frozen tuples in
  `test_phase6_brake.py`, `test_phase6_compensation.py`, `test_phase6_policy.py` and
  `test_phase6_rule.py`, by the same precedent U8.1/U8.2/U8.4 used and with the reason written into
  each. Those guards compare against `HEAD`, so they fired on this change exactly as designed.

**Mutation proof.** `scripts/mutate_p9_freight_domain.py` — 42 mutants, 42 caught. Each reintroduces
one real defect; the named guard is green before, RED under it, and green after an in-memory
byte-for-byte restore. The first run caught 39 of 41 and the two misses were real: the "a mapping
cannot be deleted" assertion was being satisfied by a foreign key rather than by the trigger it
claimed to prove, and the "stale news" test checked ordering without checking what a stale TMS
snapshot is narrated as. Both tests were strengthened and both mutants are now caught. M8's own
pre-existing battery (`scripts/mutate_phase6_expectation.py`) was re-run against the changed machine:
21 of 21 caught.

**Rollback / disablement.** Nothing reaches the spine from a live path, so there is nothing to
disable. To remove it: delete `src/freight_recon/freight_domain/`, the corpus and the harness script,
and revert the eleven guards. The table is additive and empty in every existing database; leaving it
is harmless. The M8 change is independent and should stay; reverting it means restoring
`expectation.py` to the four frozen tuples as well.

## 6. Knowingly incomplete

| ID | Debt | Why it does not block this checkpoint |
|---|---|---|
| `P9-D1` | M5's `provenance_class` column means "binding provenance" after bind (F-3). | P9 never reads it for content. A later consumer that does would launder — fix M5 before any does. |
| `P9-D2` | No M5 re-bind; M6's propagation obligation has no consumer (F-4, F-7). | Worked around in the projection and proved by N16. |
| `P9-D3` | No Exception closure path is wired; an authorization does not close the Exception it answers. | Open Exceptions are truthful and owned; nothing is hidden. |
| `P9-D4` | Fifteen of the forty entities are not built; no per-entity domain tables. | Not exercised by the first operating loop; the registry's `migration_requirements` is still owed. |
| `P9-D5` | Legacy `reconciliation.py` still exists beside the canonical result. | Its deletion condition (LEGACY-DISPOSITION S7) is unmet; neither gates anything. |
| `P9-D6` | One `counterparty_update` Expectation per load at a time (F-8). | Coalescing loses no obligation; a second promise is raised once the first discharges. |
| `P9-D7` | No concurrency tests; the new table is not exercised on PostgreSQL. | Single-writer harness; ships dark. Both are required before P9 acceptance. |
| `P9-D8` | Deadlines are evaluated by calling M8 at each arrival; the P5 timer relay is not run. | M8 arms the durable timers; the verdict path is the same. |
| `P9-D9` | No pending-reference TTL; an unresolved record waits indefinitely, owned. | The threshold is an unsupplied per-brokerage constant. |
| `P9-D10` | Accessorial Authorization: only the undocumented human path; contractual pre-authorization not built. | NEEDS VALIDATION; fail-closed to a human. |
| `P9-D11` | No P9 `acceptance_criteria` block. | Instantiating it is not the builder's to score (CLAUDE.md §10). |
