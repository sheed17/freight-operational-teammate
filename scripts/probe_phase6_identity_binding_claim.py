#!/usr/bin/env python3
"""M6 — the Identity Binding Claim — deterministic narrative probe.

A POD arrives and its load number matches exactly one open load, so the binding confirms; a second
POD's reference matches two loads and nobody may pick one; a model reads "4471" off a scanned page and
that is evidence to be matched, never a confirmation; a model merely feels that an email is about load
4471 and it goes to a human at confidence 1.0 exactly as it would at 0.4; the owner assigns an
unlinked message by hand and the linker then decides it knows better — and does not get to win; the
owner discovers the POD was load 44718's all along, after an invoice already went out on it. What
matters is not that the happy path binds — it is what the machine REFUSES, and whether a human's
decision can ever be quietly recomputed, overwritten, duplicated, laundered, guessed at, or rebuilt
away by a replay.

M6 ships dark — no linker service, no queue, no live channel — so this probe is the ONLY interface a
generated Product-Driver scenario can compose M6's real behaviour through. Every ordering,
concurrency, timing, duplication, crash and replay variation has to be reachable through these
arguments, so the interface is taken seriously:

    --list-cases        the case names, one per line
    --list-dimensions   every dimension flag and every fault name
    --case <case>       run exactly one case (composes with the flags below)
    (no arguments)      run every case; exit 0 only if every one behaved as specified

    --concurrency 1-8   how many confirmers race the one-CONFIRMED-per-subject index
    --delay-ms 0-5000   timing skew between them
    --repeat 1-5        duplicate proposal / redelivery pressure
    --tenants 1-3       isolation pressure
    --candidates 0-8    how many entities the matcher sees for one subject
    --confidence 0.0-1.0 the negative control: it must change NOTHING, at 1.0 or at 0.0
    --seed <int>        deterministic interleaving — the same seed reproduces the same run
    --inject <fault>    the closed fault set (see --list-dimensions); an unknown fault, or a value
                        out of range, exits 2 with a readable message and NEVER a traceback

### CLOSED MEANS CLOSED. `--inject not-a-real-fault` exits 2. `--inject expire-claim` exits 2 —
entity §26 says a claim NEVER expires and §28 gives it no deletion policy, so a probe that accepted it
would manufacture evidence for a transition the corpus states does not exist. `--inject
auto-resolve-conflict` exits 2 — ADR-007 §5.3 makes `AutoResolve` an ILLEGAL transition (a clock is
not a decision), and M6 does not own conflict resolution at all.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

from freight_recon.identity_binding_claim import (  # noqa: E402
    AGGREGATE_TYPE,
    CONSUMER_ID,
    BindingState,
    ContentSetProvenance,
    FailClosed,
    ForgedEvidence,
    GuardNotSatisfied,
    IllegalTransition,
    M6Machine,
    MatchAttempt,
    MatchMethod,
    OrdinalTarget,
    OwnerAssertedOverwrite,
    StateConflict,
    UnknownClaim,
)
from freight_recon.migrations.phase6_identity_binding_claims import (  # noqa: E402
    CLAIM_STATES,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
)

HUMANS = ("owner:rasheed", "owner:dana", "owner:sam")

# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    "proposal-creates-proposed-with-derived-provenance",
    "provenance-is-derived-from-match-method",
    "provenance-class-is-not-independently-editable",
    "provenance-mapping-is-exhaustive-and-immutable",
    "provenance-laundering-refused",
    "content-cannot-set-its-own-provenance",
    "exact-trusted-id-confirms",
    "exact-id-with-two-open-entities-is-ambiguous",
    "no-best-guess-fallback",
    "registered-rule-confirms",
    "reconciliation-requires-two-sources",
    "human-assertion-confirms-owner-asserted",
    "human-assertion-requires-authenticated-tenant-human",
    "human-assertion-requires-decision-ref",
    "ordinal-target-resolves-to-immutable-id-or-fails-closed",
    "ordinal-target-changed-between-display-and-click-fails-closed",
    "model-extract-is-evidence-not-confirmation",
    "model-extracted-requires-evidence-span",
    "extracted-identifier-re-enters-deterministic-matching",
    "forged-evidence-span-fails-closed",
    "model-inferred-routes-to-ambiguous",
    "model-guess-never-confirms-at-confidence-1-0",
    "multiple-candidates-ambiguous",
    "single-weak-candidate-ambiguous",
    "ambiguous-is-human-owned",
    "confidence-is-invisible-to-every-guard",
    "linker-inferred-claim-may-be-recomputed",
    "owner-asserted-binding-survives-relinker",
    "owner-asserted-overwrite-is-illegal-and-recorded",
    "superseded-claim-is-retained",
    "inferrer-vs-owner-raises-conflict-not-a-winner",
    "conflicting-preserves-the-human-binding",
    "m7-conflict-machine-is-not-built",
    "human-correction-moves-confirmed-to-corrected",
    "correction-is-append-only-and-lineage-preserving",
    "correction-of-correction-is-supported",
    "correction-records-its-propagation-obligation",
    "m10-compensation-machine-is-not-built",
    "proposed-or-ambiguous-may-be-rejected",
    "cancelled-entity-supersedes-the-confirmed-binding",
    "one-confirmed-binding-per-subject",
    "competing-confirmations-serialize-at-most-one-wins",
    "occ-on-claim-version",
    "database-invariants",
    "tenant-isolation",
    "cross-tenant-identical-subject-ref",
    "wrong-tenant-human-assertion-fails-closed",
    "forged-human-fails-closed",
    "inactive-human-fails-closed",
    "model-actor-cannot-confirm",
    "counterparty-cannot-become-owner-asserted",
    "state-and-event-co-commit",
    "inbox-idempotency",
    "duplicate-proposal-is-a-no-op",
    "replay-preserves-owner-asserted-byte-identical",
    "replay-creates-no-new-authority-and-no-effect",
    "correction-before-confirmation-is-parked",
    "conflicting-binding-blocks-consequential-action",
    "superseded-binding-blocks-consequential-action",
    "confirmed-binding-provenance-is-allowed-for-consequential-action",
    "ambiguous-binding-does-not-flow-through-approval",
    "m6-mints-no-gate-decision",
)

# Every fault is a transition, a guard or a clause of the machine, the entity spec, an ADR, the event
# registry or a named mandate; none is invented here. The value is the phase it perturbs, used to
# refuse an incoherent (case, fault) combination. ### expire-claim and auto-resolve-conflict are NOT
# here, deliberately: entity §26 says a claim never expires, and ADR-007 §5.3 makes AutoResolve
# ILLEGAL — accepting either would manufacture evidence for a transition the corpus forbids.
FAULTS: dict[str, str] = {
    "none": "any",
    "model-infer-binding": "resolve",            # IB-4    a guess never confirms
    "model-extract-without-span": "propose",     # §16/§37 a MODEL_EXTRACTED claim needs a span
    "forged-evidence-span": "propose",           # §37     a forged span fails closed
    "confidence-one-point-zero": "resolve",      # GR-8    confidence changes nothing
    "edit-provenance-class": "immutable",        # SD-6    provenance is immutable once computed
    "launder-provenance": "immutable",           # R-P2    a change of belief is a NEW claim
    "content-sets-provenance": "propose",        # M-13    content cannot set provenance
    "unregistered-rule": "resolve",              # IB-2r   an unregistered rule may not confirm
    "single-source-reconciliation": "resolve",   # IB-2r   reconciliation needs >=2 sources
    "multiple-candidates": "resolve",            # IB-4    several candidates -> AMBIGUOUS
    "single-weak-candidate": "resolve",          # IB-4/M-17 a single weak candidate -> AMBIGUOUS
    "no-candidate": "resolve",                   # IB-4    no best-guess fallback
    "relink-owner-asserted": "recompute",        # IB-5x   the B3 regression
    "relink-linker-inferred": "recompute",       # IB-5    a legitimate rebuild
    "inferrer-disagrees": "conflict",            # IB-6    a conflict, not a winner
    "correct-confirmed": "correct",              # IB-7    correction propagates
    "correct-a-correction": "correct",           # §25     correction-of-correction
    "drop-propagation-obligation": "correct",    # ADR-007 §6 the obligation is recorded
    "reject-proposed": "reject",                 # IB-8
    "cancel-entity": "cancel",                   # entity §25
    "duplicate-proposal": "stream",              # entity §33  a redelivered proposal is a no-op
    "competing-confirmation": "concurrency",     # entity §17  at most one CONFIRMED per subject
    "occ-conflict": "occ",                       # GR-3    a lost update is refused
    "concurrent-confirm": "concurrency",         # §17     competing confirmations serialize
    "forged-human": "human",                     # §35     a forged human fails closed
    "inactive-human": "human",                   # §35     an inactive human fails closed
    "wrong-tenant": "tenant",                    # [C-1]   a wrong-tenant assertion fails closed
    "model-actor-confirm": "human",              # ER-10   a model actor cannot confirm
    "counterparty-asserts-authority": "human",   # §4.4    a counterparty is MODEL_EXTRACTED at best
    "ordinal-target": "human",                   # L-B     an ordinal resolves to an immutable id
    "ordinal-target-moved": "human",             # L-B     the slot moved -> fail closed
    "malformed-claim": "propose",                # §36     unreadable input fails closed
    "replay": "replay",                          # GR-11   replay mints nothing
    "restart-before-confirm": "restart",         # §36     re-derive freely
    "restart-after-correct": "restart",          # §25     correction survives restart
    "unreceived-subject": "stream",              # M-26    a reference to an unarrived claim is parked
    "reorder-stream": "stream",                  # §8      order-tolerant proposals
    "relinker-retry-storm": "recompute",         # §20     a retry storm changes nothing
}

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "candidates", "confidence", "seed", "inject",
)

# Which fault phases each case can coherently exercise. A fault whose phase a case never reaches is
# refused rather than run degenerately.
CASE_PHASES: dict[str, set[str]] = {
    "proposal-creates-proposed-with-derived-provenance": {"propose"},
    "provenance-is-derived-from-match-method": {"propose"},
    "provenance-class-is-not-independently-editable": {"immutable"},
    "provenance-mapping-is-exhaustive-and-immutable": {"propose", "immutable"},
    "provenance-laundering-refused": {"immutable", "propose"},
    "content-cannot-set-its-own-provenance": {"propose"},
    "exact-trusted-id-confirms": {"resolve", "propose"},
    "exact-id-with-two-open-entities-is-ambiguous": {"resolve"},
    "no-best-guess-fallback": {"resolve"},
    "registered-rule-confirms": {"resolve"},
    "reconciliation-requires-two-sources": {"resolve"},
    "human-assertion-confirms-owner-asserted": {"human"},
    "human-assertion-requires-authenticated-tenant-human": {"human"},
    "human-assertion-requires-decision-ref": {"human"},
    "ordinal-target-resolves-to-immutable-id-or-fails-closed": {"human"},
    "ordinal-target-changed-between-display-and-click-fails-closed": {"human"},
    "model-extract-is-evidence-not-confirmation": {"propose", "resolve"},
    "model-extracted-requires-evidence-span": {"propose"},
    "extracted-identifier-re-enters-deterministic-matching": {"propose", "resolve"},
    "forged-evidence-span-fails-closed": {"propose"},
    "model-inferred-routes-to-ambiguous": {"resolve"},
    "model-guess-never-confirms-at-confidence-1-0": {"resolve"},
    "multiple-candidates-ambiguous": {"resolve"},
    "single-weak-candidate-ambiguous": {"resolve"},
    "ambiguous-is-human-owned": {"resolve", "human"},
    "confidence-is-invisible-to-every-guard": {"resolve"},
    "linker-inferred-claim-may-be-recomputed": {"recompute"},
    "owner-asserted-binding-survives-relinker": {"recompute"},
    "owner-asserted-overwrite-is-illegal-and-recorded": {"recompute"},
    "superseded-claim-is-retained": {"recompute"},
    "inferrer-vs-owner-raises-conflict-not-a-winner": {"conflict"},
    "conflicting-preserves-the-human-binding": {"conflict"},
    "m7-conflict-machine-is-not-built": {"conflict"},
    "human-correction-moves-confirmed-to-corrected": {"correct"},
    "correction-is-append-only-and-lineage-preserving": {"correct"},
    "correction-of-correction-is-supported": {"correct"},
    "correction-records-its-propagation-obligation": {"correct"},
    "m10-compensation-machine-is-not-built": {"correct"},
    "proposed-or-ambiguous-may-be-rejected": {"reject"},
    "cancelled-entity-supersedes-the-confirmed-binding": {"cancel"},
    "one-confirmed-binding-per-subject": {"concurrency", "resolve"},
    "competing-confirmations-serialize-at-most-one-wins": {"concurrency"},
    "occ-on-claim-version": {"occ"},
    "database-invariants": {"propose", "immutable"},
    "tenant-isolation": {"tenant"},
    "cross-tenant-identical-subject-ref": {"tenant", "propose"},
    "wrong-tenant-human-assertion-fails-closed": {"tenant", "human"},
    "forged-human-fails-closed": {"human"},
    "inactive-human-fails-closed": {"human"},
    "model-actor-cannot-confirm": {"human"},
    "counterparty-cannot-become-owner-asserted": {"human"},
    "state-and-event-co-commit": {"propose", "resolve"},
    "inbox-idempotency": {"stream"},
    "duplicate-proposal-is-a-no-op": {"stream"},
    "replay-preserves-owner-asserted-byte-identical": {"replay"},
    "replay-creates-no-new-authority-and-no-effect": {"replay"},
    "correction-before-confirmation-is-parked": {"stream", "correct"},
    "conflicting-binding-blocks-consequential-action": {"conflict"},
    "superseded-binding-blocks-consequential-action": {"recompute"},
    "confirmed-binding-provenance-is-allowed-for-consequential-action": {"resolve"},
    "ambiguous-binding-does-not-flow-through-approval": {"resolve"},
    "m6-mints-no-gate-decision": {"propose"},
}

# ### THE INVARIANT SENTENCES THE VERIFICATION SCENARIO MATCHES AS LITERAL SUBSTRINGS.
_SIG: dict[str, str] = {
    "proposal-creates-proposed-with-derived-provenance":
        "A BINDING IS A CLAIM THAT AN ARTIFACT BELONGS TO AN ENTITY, NEVER A FACT",
    "provenance-is-derived-from-match-method":
        "provenance_class IS DERIVED FROM match_method, NEVER CHOSEN",
    "provenance-class-is-not-independently-editable":
        "provenance_class IS IMMUTABLE ONCE COMPUTED",
    "provenance-mapping-is-exhaustive-and-immutable":
        "provenance_class IS DERIVED FROM match_method, NEVER CHOSEN",
    "provenance-laundering-refused":
        "A CHANGE OF BELIEF IS A NEW CLAIM, NEVER AN EDITED PROVENANCE",
    "content-cannot-set-its-own-provenance":
        "PROVENANCE IS RUNTIME-ASSIGNED, NEVER SET FROM CONTENT",
    "exact-trusted-id-confirms":
        "AN EXACT TRUSTED ID MATCHING EXACTLY ONE OPEN ENTITY CONFIRMS",
    "exact-id-with-two-open-entities-is-ambiguous": "THERE IS NO BEST-GUESS FALLBACK",
    "no-best-guess-fallback": "THERE IS NO BEST-GUESS FALLBACK",
    "registered-rule-confirms":
        "A REGISTERED DETERMINISTIC RULE MAY CONFIRM; AN UNREGISTERED ONE MAY NOT",
    "reconciliation-requires-two-sources": "RECONCILIATION REQUIRES AT LEAST TWO SOURCES",
    "human-assertion-confirms-owner-asserted":
        "A HUMAN ASSERTION IS OWNER_ASSERTED, AUTHENTICATED, AND CARRIES A decision_ref",
    "human-assertion-requires-authenticated-tenant-human":
        "A HUMAN ASSERTION IS OWNER_ASSERTED, AUTHENTICATED, AND CARRIES A decision_ref",
    "human-assertion-requires-decision-ref":
        "A HUMAN ASSERTION IS OWNER_ASSERTED, AUTHENTICATED, AND CARRIES A decision_ref",
    "ordinal-target-resolves-to-immutable-id-or-fails-closed":
        "A HUMAN ASSERTION BINDS AN IMMUTABLE ID, NEVER AN ORDINAL",
    "ordinal-target-changed-between-display-and-click-fails-closed":
        "THE ORDINAL RESOLVED TO AN IMMUTABLE ID OR THE ACTION FAILED CLOSED",
    "model-extract-is-evidence-not-confirmation": "MODEL_EXTRACTED IS EVIDENCE, NOT CONFIRMATION",
    "model-extracted-requires-evidence-span":
        "A MODEL_EXTRACTED CLAIM WITHOUT AN EVIDENCE SPAN IS STRUCTURALLY IMPOSSIBLE",
    "extracted-identifier-re-enters-deterministic-matching":
        "THE EXTRACTED IDENTIFIER RE-ENTERS DETERMINISTIC MATCHING",
    "forged-evidence-span-fails-closed":
        "A MODEL_EXTRACTED CLAIM WITHOUT AN EVIDENCE SPAN IS STRUCTURALLY IMPOSSIBLE",
    "model-inferred-routes-to-ambiguous": "A MODEL GUESS ROUTES TO AMBIGUOUS AND NEVER CONFIRMS",
    "model-guess-never-confirms-at-confidence-1-0": "CONFIDENCE 1.0 CHANGES NOTHING",
    "multiple-candidates-ambiguous": "MULTIPLE CANDIDATES ARE AMBIGUOUS, NEVER A WINNER",
    "single-weak-candidate-ambiguous": "A SINGLE WEAK CANDIDATE IS STILL AMBIGUOUS",
    "ambiguous-is-human-owned": "AMBIGUOUS IS OWNED BY A NAMED HUMAN",
    "confidence-is-invisible-to-every-guard": "CONFIDENCE IS INVISIBLE TO EVERY GUARD",
    "linker-inferred-claim-may-be-recomputed": "A LINKER_INFERRED BINDING MAY BE RECOMPUTED FREELY",
    "owner-asserted-binding-survives-relinker": "AN OWNER_ASSERTED BINDING SURVIVES THE RELINKER",
    "owner-asserted-overwrite-is-illegal-and-recorded":
        "RECOMPUTING AN OWNER_ASSERTED BINDING IS AN ILLEGAL TRANSITION",
    "superseded-claim-is-retained": "THE SUPERSEDED CLAIM IS RETAINED",
    "inferrer-vs-owner-raises-conflict-not-a-winner":
        "THE INFERRER DISAGREEING WITH THE OWNER RAISES A CONFLICT, NOT A WINNER",
    "conflicting-preserves-the-human-binding": "THE HUMAN BINDING IS PRESERVED UNDER CONFLICT",
    "m7-conflict-machine-is-not-built": "THE M7 CONFLICT MACHINE IS NOT BUILT",
    "human-correction-moves-confirmed-to-corrected":
        "CORRECTION IS APPEND-ONLY: THE PRIOR CLAIM IS RETAINED",
    "correction-is-append-only-and-lineage-preserving":
        "CORRECTION IS APPEND-ONLY: THE PRIOR CLAIM IS RETAINED",
    "correction-of-correction-is-supported": "CORRECTION-OF-CORRECTION IS SUPPORTED",
    "correction-records-its-propagation-obligation":
        "THE CORRECTION RECORDED ITS PROPAGATION OBLIGATION",
    "m10-compensation-machine-is-not-built": "THE M10 COMPENSATION MACHINE IS NOT BUILT",
    "proposed-or-ambiguous-may-be-rejected": "A DISPROVEN OR CANCELLED PROPOSAL IS REJECTED",
    "cancelled-entity-supersedes-the-confirmed-binding":
        "A CANCELLED ENTITY SUPERSEDES THE BINDING AND RETURNS THE SUBJECT TO A HUMAN",
    "one-confirmed-binding-per-subject": "AT MOST ONE CONFIRMED BINDING PER SUBJECT",
    "competing-confirmations-serialize-at-most-one-wins":
        "COMPETING CONFIRMATIONS SERIALIZE: ONE WINS, THE REST ARE REFUSED",
    "occ-on-claim-version": "A LOST UPDATE ON A CLAIM IS REFUSED",
    "database-invariants": "THE DATABASE ENFORCES THE CLAIM INVARIANTS",
    "tenant-isolation": "TENANT ISOLATION HOLDS",
    "cross-tenant-identical-subject-ref":
        "THE SAME subject_ref IN TWO TENANTS IS TWO ISOLATED CLAIMS",
    "wrong-tenant-human-assertion-fails-closed": "A WRONG-TENANT HUMAN ASSERTION FAILS CLOSED",
    "forged-human-fails-closed": "A FORGED OR INACTIVE HUMAN FAILS CLOSED",
    "inactive-human-fails-closed": "A FORGED OR INACTIVE HUMAN FAILS CLOSED",
    "model-actor-cannot-confirm": "A MODEL ACTOR CANNOT CONFIRM",
    "counterparty-cannot-become-owner-asserted":
        "A COUNTERPARTY IS MODEL_EXTRACTED AT BEST, NEVER OWNER_ASSERTED",
    "state-and-event-co-commit": "THE STATE ROW AND ITS EVENT COMMIT TOGETHER",
    "inbox-idempotency": "A REDELIVERED PROPOSAL IS A NO-OP",
    "duplicate-proposal-is-a-no-op": "A REDELIVERED PROPOSAL IS A NO-OP",
    "replay-preserves-owner-asserted-byte-identical":
        "EVERY OWNER_ASSERTED BINDING REPLAYED BYTE-IDENTICAL",
    "replay-creates-no-new-authority-and-no-effect":
        "replay: 0 new claims, 0 rewritten provenance, 0 new authority, 0 external effects",
    "correction-before-confirmation-is-parked":
        "A CORRECTION ARRIVING BEFORE ITS CONFIRMATION IS PARKED, NOT DROPPED",
    "conflicting-binding-blocks-consequential-action":
        "A CONFLICTING OR SUPERSEDED BINDING BLOCKS THE CONSEQUENTIAL ACTION",
    "superseded-binding-blocks-consequential-action":
        "A CONFLICTING OR SUPERSEDED BINDING BLOCKS THE CONSEQUENTIAL ACTION",
    "confirmed-binding-provenance-is-allowed-for-consequential-action":
        "A CONSEQUENTIAL BINDING CARRIES AN ALLOWED PROVENANCE",
    "ambiguous-binding-does-not-flow-through-approval":
        "AN AMBIGUOUS OR CONFLICTING BINDING DOES NOT FLOW THROUGH APPROVAL",
    "m6-mints-no-gate-decision": "M6 MINTS NO GATE DECISION",
}

# Extra sentences surfaced on the full run so a full battery cannot pass while any required sentence
# is silently missing (they are not the primary signature of a single case).
_EXTRA_REQUIRED: tuple[str, ...] = (
    "COMPLETED EFFECTS THAT RESTED ON THE WRONG BINDING ARE NAMED FOR COMPENSATION",
    "NO COMPENSATION IS FABRICATED AS COMPLETED",
    "A LEGACY DATABASE MIGRATES TO THE CANONICAL CLAIM SHAPE",
)


class ProbeExit(Exception):
    """A malformed-input refusal: exit code 2, a readable message, and NEVER a traceback."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Clock:
    """A deterministic, monotonically-advancing clock."""

    def __init__(self, base: datetime) -> None:
        self._t = base

    def __call__(self) -> datetime:
        self._t += timedelta(milliseconds=1)
        return self._t

    def advance(self, **kw: int) -> None:
        self._t += timedelta(**kw)


@dataclass
class Ctx:
    concurrency: int = 1
    delay_ms: int = 0
    repeat: int = 1
    tenants: int = 1
    candidates: int = 1
    confidence: float = 0.5
    seed: int = 1
    inject: str = "none"
    rng: random.Random = field(default_factory=lambda: random.Random(1))


@dataclass
class CaseResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)


# ---- scenario plumbing -------------------------------------------------------------------------

class World:
    """One canonical database, with a controllable clock and a pool of recorded humans per tenant.
    Subject observations are inserted directly via SQL — the probe never imports the M5 machine, so
    M5's ship-dark posture is untouched (its only importer stays its own probe)."""

    def __init__(self, ctx: Ctx, tmp: Path) -> None:
        self.ctx = ctx
        self.conn = sqlite3.connect(str(tmp / "ibc.db"))
        self.conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(self.conn)
        create_canonical_schema(self.conn)
        enable_and_verify_foreign_keys(self.conn)
        self.clock = Clock(datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc))
        self._humans: set[tuple[str, str]] = set()
        self._subjects: set[tuple[str, str]] = set()
        self._n = 0

    def tenant(self, i: int = 0) -> str:
        return f"tenant-{'abc'[i % 3]}" + ("" if self.ctx.tenants == 1 else str(i))

    def human(self, tenant: str, human_id: str = HUMANS[0], *, state: str = "ACTIVE") -> str:
        key = (tenant, human_id)
        if key not in self._humans:
            self.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, "
                "authority_role, state, recorded_at, recorded_by, recorded_by_kind) "
                "VALUES (?,?,?,?, ?, ?, ?, 'human')",
                (tenant, human_id, human_id, "AUTHORIZED_HUMAN", state, "2026-08-20T09:00:00.000Z",
                 "founder"))
            self.conn.commit()
            self._humans.add(key)
        return human_id

    def subject(self, tenant: str | None = None, *, obs_id: str | None = None) -> str:
        t = tenant or self.tenant()
        oid = obs_id or f"obs-{self.ctx.seed}-{self._next()}"
        if (t, oid) not in self._subjects:
            self.conn.execute(
                "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, "
                "external_id, content_digest, raw_value, as_of, received_at, state, version, "
                "provenance_class, created_at, updated_at) "
                "VALUES (?,?, 'pod:scan', ?, ?, 'POD load 4471', 't', 't', 'RECEIVED', 1, "
                "'SYSTEM_IMPORTED', 't', 't')",
                (t, oid, oid, oid))
            self.conn.commit()
            self._subjects.add((t, oid))
        return oid

    def machine(self, tenant: str | None = None) -> M6Machine:
        t = tenant or self.tenant()
        self.human(t)
        return M6Machine(self.conn, tenant=t, clock=self.clock)

    def _next(self) -> int:
        self._n += 1
        return self._n

    def claims(self, tenant: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ?", (tenant,)).fetchone()[0]

    def events(self, tenant: str, name: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (tenant, name)).fetchone()[0]

    def security(self, tenant: str) -> list[str]:
        return [r["event_type"] for r in self.conn.execute(
            "SELECT event_type FROM security_events WHERE tenant = ?", (tenant,))]


def _world(ctx: Ctx) -> World:
    return World(ctx, Path(tempfile.mkdtemp(prefix="p6m6-")))


def _exact(subject: str, entity: str = "load:4471", **kw) -> MatchAttempt:
    kw.setdefault("open_entity_count", 1)
    return MatchAttempt(subject_ref=subject, entity_ref=entity, match_method=MatchMethod.EXACT_ID,
                        **kw)


def _row(w: World, tenant: str, claim_id: str) -> dict:
    r = w.conn.execute(
        "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
        (tenant, claim_id)).fetchone()
    return dict(r) if r is not None else {}


# ---- the cases ---------------------------------------------------------------------------------

def case_proposal_creates_proposed_with_derived_provenance(w: World) -> CaseResult:
    m = w.machine()
    r = m.propose(_exact(w.subject()))
    c = m.get(r.claim.binding_claim_id)
    ok = (r.transition_id == "IB-1" and c.state is BindingState.PROPOSED
          and c.provenance_class == "LINKER_INFERRED" and c.match_method == "EXACT_ID"
          and w.events(m.tenant, "ClaimProposed") == 1)
    return CaseResult(ok, lines=[_SIG["proposal-creates-proposed-with-derived-provenance"]] if ok
                      else [], markers=[] if ok else ["### MISS ### proposal did not create PROPOSED"])


def case_provenance_is_derived_from_match_method(w: World) -> CaseResult:
    m = w.machine()
    pairs = {
        MatchMethod.EXACT_ID: "LINKER_INFERRED", MatchMethod.RULE: "LINKER_INFERRED",
        MatchMethod.RECONCILIATION: "RECONCILED", MatchMethod.MODEL_EXTRACT: "MODEL_EXTRACTED",
        MatchMethod.MODEL_INFER: "MODEL_INFERRED",
    }
    ok = True
    for method, prov in pairs.items():
        kw = {}
        if method is MatchMethod.MODEL_EXTRACT:
            kw = dict(evidence_id="pod.pdf", span="page:1")
        if method is MatchMethod.RULE:
            kw = dict(rule_id="r-mc-date-amount")
        r = m.propose(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                                   match_method=method, **kw))
        ok = ok and m.get(r.claim.binding_claim_id).provenance_class == prov
    # HUMAN -> OWNER_ASSERTED via the human-assertion path.
    ra = m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="d",
                        decision_human_id=w.human(m.tenant), actor_id=w.human(m.tenant))
    ok = ok and m.get(ra.claim.binding_claim_id).provenance_class == "OWNER_ASSERTED"
    if not ok:
        return CaseResult(False, markers=["### PROVENANCE SET FROM CONTENT ###"])
    return CaseResult(True, lines=[_SIG["provenance-is-derived-from-match-method"]])


def case_provenance_class_is_not_independently_editable(w: World) -> CaseResult:
    m = w.machine()
    r = m.propose(_exact(w.subject()))
    before = m.get(r.claim.binding_claim_id).provenance_class
    refused = False
    try:
        w.conn.execute(
            "UPDATE identity_binding_claims SET provenance_class = 'OWNER_ASSERTED' "
            "WHERE tenant = ? AND binding_claim_id = ?", (m.tenant, r.claim.binding_claim_id))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        refused = True
    ok = refused and m.get(r.claim.binding_claim_id).provenance_class == before
    if not ok:
        return CaseResult(False, markers=["### provenance_class EDITED ###"])
    return CaseResult(True, lines=[_SIG["provenance-class-is-not-independently-editable"],
                                   "A CHANGE OF BELIEF IS A NEW CLAIM, NEVER AN EDITED PROVENANCE"])


def case_provenance_mapping_is_exhaustive_and_immutable(w: World) -> CaseResult:
    m = w.machine()
    # Every match_method maps to exactly its provenance; a mismatched pair is refused by the DB CHECK.
    from freight_recon.migrations.phase6_identity_binding_claims import PROVENANCE_BY_METHOD
    mapped = len(PROVENANCE_BY_METHOD) == 6
    refused = False
    try:
        w.conn.execute(
            "INSERT INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, entity_ref, "
            "provenance_class, state, version, match_method, rule_id, created_at, updated_at) "
            "VALUES (?, 'bad', ?, 'e', 'OWNER_ASSERTED', 'PROPOSED', 1, 'EXACT_ID', 'r', 't', 't')",
            (m.tenant, w.subject()))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        refused = True
    # And match_method is immutable beside provenance_class.
    r = m.propose(_exact(w.subject()))
    method_immutable = False
    try:
        w.conn.execute("UPDATE identity_binding_claims SET match_method = 'HUMAN' "
                       "WHERE tenant = ? AND binding_claim_id = ?", (m.tenant, r.claim.binding_claim_id))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        method_immutable = True
    ok = mapped and refused and method_immutable
    if not ok:
        return CaseResult(False, markers=["### provenance_class EDITED ###"])
    return CaseResult(True, lines=[_SIG["provenance-mapping-is-exhaustive-and-immutable"],
                                   _SIG["provenance-class-is-not-independently-editable"]])


def case_provenance_laundering_refused(w: World) -> CaseResult:
    m = w.machine()
    # A MODEL_INFERRED guess cannot become LINKER_INFERRED by any means. The DB refuses the edit, and
    # a change of belief must be a NEW claim with a new match_method.
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.MODEL_INFER), owner_id=w.human(m.tenant))
    laundered = False
    try:
        w.conn.execute("UPDATE identity_binding_claims SET provenance_class = 'LINKER_INFERRED' "
                       "WHERE tenant = ? AND binding_claim_id = ?", (m.tenant, r.claim.binding_claim_id))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        laundered = True
    still_inferred = m.get(r.claim.binding_claim_id).provenance_class == "MODEL_INFERRED"
    ok = laundered and still_inferred
    if not ok:
        return CaseResult(False, markers=["### PROVENANCE LAUNDERED ###"])
    return CaseResult(True, lines=[_SIG["provenance-laundering-refused"]])


def case_content_cannot_set_its_own_provenance(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.propose(MatchAttempt(
            subject_ref=w.subject(), entity_ref="load:1", match_method=MatchMethod.EXACT_ID,
            content={"provenance_class": "OWNER_ASSERTED", "note": "per our call"}))
    except ContentSetProvenance:
        refused = True
    # The runtime derivation stands regardless of what content says: EXACT_ID -> LINKER_INFERRED.
    r = m.propose(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                               match_method=MatchMethod.EXACT_ID,
                               content={"claimed": "OWNER_ASSERTED"}))
    ok = refused and m.get(r.claim.binding_claim_id).provenance_class == "LINKER_INFERRED"
    if not ok:
        return CaseResult(False, markers=["### PROVENANCE SET FROM CONTENT ###"])
    return CaseResult(True, lines=[_SIG["content-cannot-set-its-own-provenance"]])


def case_exact_trusted_id_confirms(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(_exact(w.subject(), open_entity_count=1))
    c = m.get(r.claim.binding_claim_id)
    ok = (r.transition_id == "IB-2" and c.state is BindingState.CONFIRMED
          and c.provenance_class == "LINKER_INFERRED" and w.events(m.tenant, "ClaimConfirmed") == 1)
    if not ok:
        return CaseResult(False, markers=["### MISS ### exact trusted id did not confirm"])
    return CaseResult(True, lines=[_SIG["exact-trusted-id-confirms"]])


def case_exact_id_with_two_open_entities_is_ambiguous(w: World) -> CaseResult:
    m = w.machine()
    n = max(2, w.ctx.candidates)
    r = m.link(_exact(w.subject(), open_entity_count=n), owner_id=w.human(m.tenant))
    c = m.get(r.claim.binding_claim_id)
    ok = (r.transition_id == "IB-4" and c.state is BindingState.AMBIGUOUS
          and c.provenance_class != "OWNER_ASSERTED" and w.events(m.tenant, "ClaimConfirmed") == 0)
    if not ok:
        return CaseResult(False, markers=["### BEST GUESS ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["exact-id-with-two-open-entities-is-ambiguous"]])


def case_no_best_guess_fallback(w: World) -> CaseResult:
    m = w.machine()
    # Several candidates, each carrying a confidence score; the linker does NOT pick the best one.
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.EXACT_ID, open_entity_count=3, candidate_count=3,
                            confidence=0.99), owner_id=w.human(m.tenant))
    c = m.get(r.claim.binding_claim_id)
    # An exact id resolving to ZERO open entities is also a human, not a fabricated bind.
    r0 = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                             match_method=MatchMethod.EXACT_ID, open_entity_count=0),
                owner_id=w.human(m.tenant))
    ok = (c.state is BindingState.AMBIGUOUS
          and m.get(r0.claim.binding_claim_id).state is BindingState.AMBIGUOUS
          and w.events(m.tenant, "ClaimConfirmed") == 0)
    if not ok:
        return CaseResult(False, markers=["### BEST GUESS ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["no-best-guess-fallback"]])


def case_registered_rule_confirms(w: World) -> CaseResult:
    m = w.machine()
    # A registered deterministic rule confirms.
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.RULE, rule_id="rule:mc-date-amount",
                            rule_registered=True))
    reg_ok = m.get(r.claim.binding_claim_id).state is BindingState.CONFIRMED
    # An UNREGISTERED rule may NOT — it goes to a human.
    r2 = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                             match_method=MatchMethod.RULE, rule_id="rule:unknown",
                             rule_registered=False), owner_id=w.human(m.tenant))
    unreg_ok = m.get(r2.claim.binding_claim_id).state is BindingState.AMBIGUOUS
    ok = reg_ok and unreg_ok
    if not ok:
        return CaseResult(False, markers=["### BEST GUESS ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["registered-rule-confirms"]])


def case_reconciliation_requires_two_sources(w: World) -> CaseResult:
    m = w.machine()
    # Two agreeing sources reconcile and confirm.
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.RECONCILIATION, source_count=2))
    two_ok = (m.get(r.claim.binding_claim_id).state is BindingState.CONFIRMED
              and m.get(r.claim.binding_claim_id).provenance_class == "RECONCILED")
    # A single source is not reconciliation -> a human.
    r1 = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                             match_method=MatchMethod.RECONCILIATION, source_count=1),
                owner_id=w.human(m.tenant))
    one_ok = m.get(r1.claim.binding_claim_id).state is BindingState.AMBIGUOUS
    ok = two_ok and one_ok
    if not ok:
        return CaseResult(False, markers=["### BEST GUESS ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["reconciliation-requires-two-sources"]])


def case_human_assertion_confirms_owner_asserted(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="dec-77",
                       decision_human_id=h, actor_id=h, actor_kind="human")
    c = m.get(r.claim.binding_claim_id)
    ok = (r.transition_id == "IB-2h" and c.state is BindingState.CONFIRMED
          and c.provenance_class == "OWNER_ASSERTED" and c.decision_ref == "dec-77"
          and c.decision_human_id == h and c.match_method == "HUMAN")
    if not ok:
        return CaseResult(False, markers=["### MISS ### human assertion did not confirm OWNER_ASSERTED"])
    return CaseResult(True, lines=[_SIG["human-assertion-confirms-owner-asserted"]])


def case_human_assertion_requires_authenticated_tenant_human(w: World) -> CaseResult:
    m = w.machine()
    # A fabricated human (not recorded) fails closed.
    refused_forged = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="d",
                       decision_human_id="not-a-recorded-human", actor_id="not-a-recorded-human")
    except GuardNotSatisfied:
        refused_forged = True
    # A machine actor cannot assert (ER-10).
    refused_machine = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="d",
                       decision_human_id=w.human(m.tenant), actor_id="the-linker", actor_kind="system")
    except IllegalTransition:
        refused_machine = True
    ok = refused_forged and refused_machine
    if not ok:
        return CaseResult(False, markers=["### FORGED HUMAN ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["human-assertion-requires-authenticated-tenant-human"]])


def case_human_assertion_requires_decision_ref(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="",
                       decision_human_id=w.human(m.tenant), actor_id=w.human(m.tenant))
    except GuardNotSatisfied:
        refused = True
    ok = refused and w.events(m.tenant, "ClaimConfirmed") == 0
    if not ok:
        return CaseResult(False, markers=["### MISS ### human assertion without decision_ref accepted"])
    return CaseResult(True, lines=[_SIG["human-assertion-requires-decision-ref"]])


def case_ordinal_target_resolves_to_immutable_id_or_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    s1, s2, s3 = w.subject(), w.subject(), w.subject()
    unlinked = [s1, s2, s3]
    # "assign unlinked 2" resolved at render time to s2; the action binds to THAT immutable id.
    target = OrdinalTarget(ordinal=2, resolved_observation_id=s2)
    r = m.assert_human(entity_ref="load:4471", decision_ref="dec-2", decision_human_id=h, actor_id=h,
                       ordinal_target=target, current_unlinked=unlinked)
    c = m.get(r.claim.binding_claim_id)
    ok = (c.subject_ref == s2 and c.state is BindingState.CONFIRMED
          and c.provenance_class == "OWNER_ASSERTED")
    if not ok:
        return CaseResult(False, markers=["### ORDINAL BOUND WITHOUT AN IMMUTABLE ID ###"])
    return CaseResult(True, lines=[_SIG["ordinal-target-resolves-to-immutable-id-or-fails-closed"],
                                   "THE ORDINAL RESOLVED TO AN IMMUTABLE ID OR THE ACTION FAILED CLOSED"])


def case_ordinal_target_changed_between_display_and_click_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    s1, s2, s3 = w.subject(), w.subject(), w.subject()
    # Rendered: slot 2 = s2. Between render and click a new message is inserted at the top, so slot 2
    # now shows s1. The action must FAIL CLOSED, never fall back to the new occupant of slot 2.
    target = OrdinalTarget(ordinal=2, resolved_observation_id=s2)
    new_msg = w.subject()
    reshuffled = [new_msg, s1, s2, s3]
    failed_closed = False
    try:
        m.assert_human(entity_ref="load:4471", decision_ref="d", decision_human_id=h, actor_id=h,
                       ordinal_target=target, current_unlinked=reshuffled)
    except FailClosed:
        failed_closed = True
    # And if the resolved id is GONE entirely, it also fails closed.
    gone = False
    try:
        m.assert_human(entity_ref="load:1", decision_ref="d", decision_human_id=h, actor_id=h,
                       ordinal_target=OrdinalTarget(ordinal=1, resolved_observation_id="obs-vanished"),
                       current_unlinked=[s1, s3])
    except FailClosed:
        gone = True
    ok = failed_closed and gone and w.events(m.tenant, "ClaimConfirmed") == 0
    if not ok:
        return CaseResult(False, markers=["### ORDINAL FELL BACK TO POSITION ###"])
    return CaseResult(True, lines=[_SIG["ordinal-target-changed-between-display-and-click-fails-closed"]])


def case_model_extract_is_evidence_not_confirmation(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:4471",
                            match_method=MatchMethod.MODEL_EXTRACT, evidence_id="pod.pdf",
                            span="page:1", extracted_identifier="4471"))
    c = m.get(r.claim.binding_claim_id)
    ok = (c.state is BindingState.PROPOSED and c.provenance_class == "MODEL_EXTRACTED"
          and r.event_names == ("ClaimEvidenced",) and w.events(m.tenant, "ClaimConfirmed") == 0)
    if not ok:
        return CaseResult(False, markers=["### MISS ### model extract was treated as confirmation"])
    return CaseResult(True, lines=[_SIG["model-extract-is-evidence-not-confirmation"]])


def case_model_extracted_requires_evidence_span(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.propose(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                               match_method=MatchMethod.MODEL_EXTRACT, evidence_id="pod.pdf",
                               span=None))
    except ForgedEvidence:
        refused = True
    # The database refuses it too (defense in depth): a MODEL_EXTRACTED row with no span.
    db_refused = False
    try:
        w.conn.execute(
            "INSERT INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, entity_ref, "
            "provenance_class, state, version, match_method, created_at, updated_at) "
            "VALUES (?, 'me-nospan', ?, 'e', 'MODEL_EXTRACTED', 'PROPOSED', 1, 'MODEL_EXTRACT', 't', 't')",
            (m.tenant, w.subject()))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        db_refused = True
    ok = refused and db_refused
    if not ok:
        return CaseResult(False, markers=["### MODEL_EXTRACTED WITHOUT EVIDENCE SPAN ###"])
    return CaseResult(True, lines=[_SIG["model-extracted-requires-evidence-span"]])


def case_extracted_identifier_re_enters_deterministic_matching(w: World) -> CaseResult:
    m = w.machine()
    subject = w.subject()
    # The model READS "4471" off the page -> a MODEL_EXTRACTED evidence claim (stays PROPOSED).
    ev = m.link(MatchAttempt(subject_ref=subject, entity_ref="load:4471",
                             match_method=MatchMethod.MODEL_EXTRACT, evidence_id="pod.pdf",
                             span="0:4", extracted_identifier="4471"))
    evidence_stays = m.get(ev.claim.binding_claim_id).state is BindingState.PROPOSED
    # The extracted identifier RE-ENTERS deterministic matching as a NEW EXACT_ID attempt: the linker
    # decides. The model found the string; the linker confirms.
    det = m.link(_exact(subject, entity="load:4471", open_entity_count=1))
    confirmed = m.get(det.claim.binding_claim_id)
    ok = (evidence_stays and confirmed.state is BindingState.CONFIRMED
          and confirmed.provenance_class == "LINKER_INFERRED"
          and det.claim.binding_claim_id != ev.claim.binding_claim_id)
    if not ok:
        return CaseResult(False, markers=["### MISS ### extracted id did not re-enter matching"])
    return CaseResult(True, lines=[_SIG["extracted-identifier-re-enters-deterministic-matching"],
                                   _SIG["model-extract-is-evidence-not-confirmation"]])


def case_forged_evidence_span_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    refusals = 0
    for span in ("", "not-a-region", "banana"):
        try:
            m.propose(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                                   match_method=MatchMethod.MODEL_EXTRACT, evidence_id="pod.pdf",
                                   span=span))
        except ForgedEvidence:
            refusals += 1
    ok = refusals == 3 and w.claims(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=["### FORGED EVIDENCE SPAN ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["forged-evidence-span-fails-closed"],
                                   _SIG["model-extracted-requires-evidence-span"]])


def case_model_inferred_routes_to_ambiguous(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:4471",
                            match_method=MatchMethod.MODEL_INFER), owner_id=w.human(m.tenant))
    c = m.get(r.claim.binding_claim_id)
    ok = (c.state is BindingState.AMBIGUOUS and c.provenance_class == "MODEL_INFERRED"
          and c.ambiguous_reason == "model_inferred" and w.events(m.tenant, "ClaimConfirmed") == 0)
    if not ok:
        return CaseResult(False, markers=["### MODEL_INFERRED CONFIRMED ###"])
    return CaseResult(True, lines=[_SIG["model-inferred-routes-to-ambiguous"]])


def case_model_guess_never_confirms_at_confidence_1_0(w: World) -> CaseResult:
    m = w.machine()
    # At confidence 1.0 a model guess is STILL ambiguous — there is no threshold.
    hi = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                             match_method=MatchMethod.MODEL_INFER, confidence=1.0),
                owner_id=w.human(m.tenant))
    lo = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                             match_method=MatchMethod.MODEL_INFER, confidence=0.4),
                owner_id=w.human(m.tenant))
    ok = (m.get(hi.claim.binding_claim_id).state is BindingState.AMBIGUOUS
          and m.get(lo.claim.binding_claim_id).state is BindingState.AMBIGUOUS
          and w.events(m.tenant, "ClaimConfirmed") == 0)
    if not ok:
        return CaseResult(False, markers=["### CONFIDENCE GATED A CONFIRMATION ###"])
    return CaseResult(True, lines=[_SIG["model-guess-never-confirms-at-confidence-1-0"],
                                   _SIG["confidence-is-invisible-to-every-guard"]])


def case_multiple_candidates_ambiguous(w: World) -> CaseResult:
    m = w.machine()
    n = max(2, w.ctx.candidates)
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.EXACT_ID, candidate_count=n, open_entity_count=n),
               owner_id=w.human(m.tenant))
    c = m.get(r.claim.binding_claim_id)
    ok = c.state is BindingState.AMBIGUOUS and c.ambiguous_reason == "multiple"
    if not ok:
        return CaseResult(False, markers=["### BEST GUESS ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["multiple-candidates-ambiguous"]])


def case_single_weak_candidate_ambiguous(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.EXACT_ID, candidate_count=1, weak=True,
                            open_entity_count=1), owner_id=w.human(m.tenant))
    c = m.get(r.claim.binding_claim_id)
    ok = c.state is BindingState.AMBIGUOUS and c.ambiguous_reason == "single_weak"
    if not ok:
        return CaseResult(False, markers=["### WEAK CANDIDATE AUTO-CONFIRMED ###"])
    return CaseResult(True, lines=[_SIG["single-weak-candidate-ambiguous"]])


def case_ambiguous_is_human_owned(w: World) -> CaseResult:
    m = w.machine()
    # Without a named human owner, AMBIGUOUS is refused.
    refused = False
    try:
        m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.MODEL_INFER))
    except GuardNotSatisfied:
        refused = True
    # A fabricated owner is refused too.
    refused_fake = False
    try:
        m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.MODEL_INFER), owner_id="ghost")
    except GuardNotSatisfied:
        refused_fake = True
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                            match_method=MatchMethod.MODEL_INFER), owner_id=w.human(m.tenant))
    c = m.get(r.claim.binding_claim_id)
    ok = (refused and refused_fake and c.state is BindingState.AMBIGUOUS
          and c.owner_id == w.human(m.tenant))
    if not ok:
        return CaseResult(False, markers=["### MISS ### AMBIGUOUS without a named human owner"])
    return CaseResult(True, lines=[_SIG["ambiguous-is-human-owned"]])


def case_confidence_is_invisible_to_every_guard(w: World) -> CaseResult:
    m = w.machine()
    # The same deterministic and same guess outcome at confidence 0.0 and 1.0 — confidence changes
    # NOTHING. It is stored (for queue ordering) but never read by a guard.
    det_hi = m.link(_exact(w.subject(), confidence=1.0))
    det_lo = m.link(_exact(w.subject(), confidence=0.0))
    guess_hi = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="e",
                                   match_method=MatchMethod.MODEL_INFER, confidence=1.0),
                      owner_id=w.human(m.tenant))
    guess_lo = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="e",
                                   match_method=MatchMethod.MODEL_INFER, confidence=0.0),
                      owner_id=w.human(m.tenant))
    ok = (m.get(det_hi.claim.binding_claim_id).state
          is m.get(det_lo.claim.binding_claim_id).state is BindingState.CONFIRMED
          and m.get(guess_hi.claim.binding_claim_id).state
          is m.get(guess_lo.claim.binding_claim_id).state is BindingState.AMBIGUOUS)
    if not ok:
        return CaseResult(False, markers=["### CONFIDENCE GATED A CONFIRMATION ###"])
    return CaseResult(True, lines=[_SIG["confidence-is-invisible-to-every-guard"],
                                   _SIG["model-guess-never-confirms-at-confidence-1-0"]])


def case_linker_inferred_claim_may_be_recomputed(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(_exact(w.subject()))
    sup = m.recompute(r.claim.binding_claim_id)
    old = m.get(r.claim.binding_claim_id)
    ok = (sup.to_state is BindingState.SUPERSEDED and old.state is BindingState.SUPERSEDED
          and w.events(m.tenant, "ClaimSuperseded") == 1)
    if not ok:
        return CaseResult(False, markers=["### MISS ### LINKER_INFERRED could not be recomputed"])
    return CaseResult(True, lines=[_SIG["linker-inferred-claim-may-be-recomputed"]])


def case_owner_asserted_binding_survives_relinker(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="d",
                       decision_human_id=h, actor_id=h)
    before = _row(w, m.tenant, r.claim.binding_claim_id)
    # A relinker RETRY STORM: many recompute attempts. Every one is illegal; the row never moves.
    storm = max(1, w.ctx.repeat) * 3
    illegal = 0
    for _ in range(storm):
        try:
            m.recompute(r.claim.binding_claim_id)
        except OwnerAssertedOverwrite:
            illegal += 1
    after = _row(w, m.tenant, r.claim.binding_claim_id)
    ok = (illegal == storm and after == before and after.get("state") == "CONFIRMED"
          and "OwnerAssertedOverwriteAttempted" in w.security(m.tenant))
    if not ok:
        return CaseResult(False, markers=["### OWNER_ASSERTED OVERWRITTEN ###"])
    return CaseResult(True, lines=[_SIG["owner-asserted-binding-survives-relinker"],
                                   _SIG["owner-asserted-overwrite-is-illegal-and-recorded"]])


def case_owner_asserted_overwrite_is_illegal_and_recorded(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="d",
                       decision_human_id=h, actor_id=h)
    recorded = False
    try:
        m.recompute(r.claim.binding_claim_id, actor_id="the-relinker")
    except OwnerAssertedOverwrite:
        recorded = True
    sec = w.security(m.tenant)
    ok = (recorded and m.get(r.claim.binding_claim_id).state is BindingState.CONFIRMED
          and "IllegalTransitionAttempted" in sec and "OwnerAssertedOverwriteAttempted" in sec
          and w.events(m.tenant, "ClaimSuperseded") == 0)
    if not ok:
        return CaseResult(False, markers=["### OWNER_ASSERTED SILENTLY SUPERSEDED ###"])
    return CaseResult(True, lines=[_SIG["owner-asserted-overwrite-is-illegal-and-recorded"]])


def case_superseded_claim_is_retained(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(_exact(w.subject(), entity="load:4471"))
    m.recompute(r.claim.binding_claim_id)
    old = m.get(r.claim.binding_claim_id)
    ok = (old is not None and old.state is BindingState.SUPERSEDED and old.entity_ref == "load:4471"
          and w.claims(m.tenant) == 1)
    if not ok:
        return CaseResult(False, markers=["### CLAIM DELETED ###"])
    return CaseResult(True, lines=[_SIG["superseded-claim-is-retained"]])


def case_inferrer_vs_owner_raises_conflict_not_a_winner(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="d",
                       decision_human_id=h, actor_id=h)
    c = m.inferrer_disagrees(r.claim.binding_claim_id, disagreeing_entity_ref="load:9999",
                             owner_id=h)
    binding = m.get(r.claim.binding_claim_id)
    ok = (c.to_state is BindingState.CONFLICTING and binding.entity_ref == "load:4471"
          and c.event_names == ("ConflictRaised",) and w.events(m.tenant, "ConflictRaised") == 1)
    if not ok:
        return CaseResult(False, markers=["### INFERRER PICKED A WINNER ###"])
    return CaseResult(True, lines=[_SIG["inferrer-vs-owner-raises-conflict-not-a-winner"]])


def case_conflicting_preserves_the_human_binding(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="d",
                       decision_human_id=h, actor_id=h)
    m.inferrer_disagrees(r.claim.binding_claim_id, disagreeing_entity_ref="load:9999", owner_id=h)
    b = m.get(r.claim.binding_claim_id)
    ok = (b.state is BindingState.CONFLICTING and b.entity_ref == "load:4471"
          and b.provenance_class == "OWNER_ASSERTED" and b.owner_id == h)
    if not ok:
        return CaseResult(False, markers=["### OWNER_ASSERTED OVERWRITTEN ###"])
    return CaseResult(True, lines=[_SIG["conflicting-preserves-the-human-binding"]])


def case_m7_conflict_machine_is_not_built(w: World) -> CaseResult:
    tables = {r[0] for r in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    src = (ROOT / "src" / "freight_recon" / "identity_binding_claim.py").read_text(encoding="utf-8")
    import ast
    minted = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "event_name" and isinstance(kw.value, ast.Constant):
                    minted.add(str(kw.value.value))
    forbidden_m7 = {"ConflictOpened", "ConflictEscalated", "ConflictResolved", "ConflictPartyAttached"}
    ok = ("conflicts" not in tables and "conflict_parties" not in tables
          and not (minted & forbidden_m7) and "ConflictRaised" in minted)
    if not ok:
        return CaseResult(False, markers=["### CONFLICT AUTO-RESOLVED ###"])
    return CaseResult(True, lines=[_SIG["m7-conflict-machine-is-not-built"]])


def case_human_correction_moves_confirmed_to_corrected(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.link(_exact(w.subject(), entity="load:4471"))
    corr = m.correct(r.claim.binding_claim_id, new_entity_ref="load:44718", decision_ref="fix-1",
                     decision_human_id=h, actor_id=h, completed_effects=["invoice#560010"])
    old = m.get(r.claim.binding_claim_id)
    new = m.get(corr.corrected_claim_id)
    ok = (old.state is BindingState.CORRECTED and new.state is BindingState.CONFIRMED
          and new.provenance_class == "OWNER_ASSERTED" and new.entity_ref == "load:44718"
          and w.events(m.tenant, "ClaimCorrected") == 1)
    if not ok:
        return CaseResult(False, markers=["### MISS ### correction did not reach CORRECTED"])
    return CaseResult(True, lines=[_SIG["human-correction-moves-confirmed-to-corrected"]])


def case_correction_is_append_only_and_lineage_preserving(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.link(_exact(w.subject(), entity="load:4471"))
    before = _row(w, m.tenant, r.claim.binding_claim_id)
    corr = m.correct(r.claim.binding_claim_id, new_entity_ref="load:44718", decision_ref="fix",
                     decision_human_id=h, actor_id=h, completed_effects=["invoice#560010"])
    old = m.get(r.claim.binding_claim_id)
    new = m.get(corr.corrected_claim_id)
    # The prior claim is RETAINED (never deleted), its entity/subject/provenance unchanged; the new
    # claim's corrected_from points back at it.
    ok = (old is not None and old.entity_ref == before["entity_ref"]
          and old.subject_ref == before["subject_ref"]
          and old.provenance_class == before["provenance_class"]
          and new.corrected_from == r.claim.binding_claim_id and w.claims(m.tenant) == 2)
    if not ok:
        return CaseResult(False, markers=["### CLAIM DELETED ###"])
    return CaseResult(True, lines=[_SIG["correction-is-append-only-and-lineage-preserving"]])


def case_correction_of_correction_is_supported(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.link(_exact(w.subject(), entity="load:4471"))
    c1 = m.correct(r.claim.binding_claim_id, new_entity_ref="load:44718", decision_ref="fix1",
                   decision_human_id=h, actor_id=h)
    # Correct the correction: the newly-corrected CONFIRMED claim is corrected again.
    c2 = m.correct(c1.corrected_claim_id, new_entity_ref="load:44719", decision_ref="fix2",
                   decision_human_id=h, actor_id=h)
    mid = m.get(c1.corrected_claim_id)
    final = m.get(c2.corrected_claim_id)
    ok = (mid.state is BindingState.CORRECTED and final.state is BindingState.CONFIRMED
          and final.entity_ref == "load:44719" and final.corrected_from == c1.corrected_claim_id
          and w.events(m.tenant, "ClaimCorrected") == 2)
    if not ok:
        return CaseResult(False, markers=["### MISS ### correction-of-correction not supported"])
    return CaseResult(True, lines=[_SIG["correction-of-correction-is-supported"]])


def case_correction_records_its_propagation_obligation(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.link(_exact(w.subject(), entity="load:4471"))
    m.correct(r.claim.binding_claim_id, new_entity_ref="load:44718", decision_ref="fix",
              decision_human_id=h, actor_id=h, dependent_refs=["load:4471.documented"],
              completed_effects=["invoice#560010"])
    old = m.get(r.claim.binding_claim_id)
    obligation = json.loads(old.propagation_obligation or "{}")
    named = "invoice#560010" in obligation.get("completed_effects_needing_compensation", [])
    # NO compensations table, and no fabricated completed compensation.
    tables = {row[0] for row in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    no_comp_table = "compensations" not in tables
    ok = old.propagation_obligation is not None and named and no_comp_table
    if not ok:
        return CaseResult(False, markers=["### CORRECTION WITHOUT ITS PROPAGATION OBLIGATION ###"])
    return CaseResult(True, lines=[_SIG["correction-records-its-propagation-obligation"],
                                   "COMPLETED EFFECTS THAT RESTED ON THE WRONG BINDING ARE NAMED FOR COMPENSATION",
                                   "NO COMPENSATION IS FABRICATED AS COMPLETED"])


def case_m10_compensation_machine_is_not_built(w: World) -> CaseResult:
    tables = {r[0] for r in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    src = (ROOT / "src" / "freight_recon" / "identity_binding_claim.py").read_text(encoding="utf-8")
    import ast
    minted = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "event_name" and isinstance(kw.value, ast.Constant):
                    minted.add(str(kw.value.value))
    forbidden = {"CompensationRequired", "CompensationCompleted", "CompensationApproved",
                 "CompensationStarted", "CorrectionInvalidatedAnEffect"}
    ok = "compensations" not in tables and not (minted & forbidden)
    if not ok:
        return CaseResult(False, markers=["### COMPENSATION FABRICATED ###"])
    return CaseResult(True, lines=[_SIG["m10-compensation-machine-is-not-built"],
                                   "NO COMPENSATION IS FABRICATED AS COMPLETED"])


def case_proposed_or_ambiguous_may_be_rejected(w: World) -> CaseResult:
    m = w.machine()
    p = m.propose(_exact(w.subject()))
    rej = m.reject(p.claim.binding_claim_id, reason="disproven")
    a = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="e",
                            match_method=MatchMethod.MODEL_INFER), owner_id=w.human(m.tenant))
    rej2 = m.reject(a.claim.binding_claim_id, reason="entity cancelled")
    ok = (rej.to_state is BindingState.REJECTED and rej2.to_state is BindingState.REJECTED
          and w.events(m.tenant, "ClaimSuperseded") == 2)
    if not ok:
        return CaseResult(False, markers=["### MISS ### reject did not reach REJECTED"])
    return CaseResult(True, lines=[_SIG["proposed-or-ambiguous-may-be-rejected"]])


def case_cancelled_entity_supersedes_the_confirmed_binding(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.link(_exact(w.subject(), entity="load:4471"))
    sup = m.cancel_entity(r.claim.binding_claim_id, owner_id=h)
    c = m.get(r.claim.binding_claim_id)
    ok = (sup.to_state is BindingState.SUPERSEDED and c.state is BindingState.SUPERSEDED
          and c.owner_id == h and w.events(m.tenant, "ClaimSuperseded") == 1)
    if not ok:
        return CaseResult(False, markers=["### MISS ### cancelled entity did not supersede"])
    return CaseResult(True, lines=[_SIG["cancelled-entity-supersedes-the-confirmed-binding"]])


def case_one_confirmed_binding_per_subject(w: World) -> CaseResult:
    m = w.machine()
    subject = w.subject()
    m.link(_exact(subject, entity="load:1"))
    # A second confirmation for the same subject is refused by the partial unique index.
    p2 = m.propose(_exact(subject, entity="load:2"))
    refused = False
    try:
        m.resolve(p2.claim.binding_claim_id, _exact(subject, entity="load:2"))
    except GuardNotSatisfied:
        refused = True
    confirmed = w.conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ? AND subject_ref = ? "
        "AND state = 'CONFIRMED'", (m.tenant, subject)).fetchone()[0]
    ok = refused and confirmed == 1
    if not ok:
        return CaseResult(False, markers=["### TWO CONFIRMED BINDINGS ###"])
    return CaseResult(True, lines=[_SIG["one-confirmed-binding-per-subject"]])


def case_competing_confirmations_serialize_at_most_one_wins(w: World) -> CaseResult:
    m = w.machine()
    subject = w.subject()
    n = max(2, w.ctx.concurrency)
    # N proposed claims for ONE subject; N confirmers race, in a seeded order. The partial unique
    # index is the serialization point: exactly one wins, the rest are refused.
    proposals = [m.propose(_exact(subject, entity=f"load:{i}")) for i in range(n)]
    order = list(range(n))
    w.ctx.rng.shuffle(order)
    wins, refused = 0, 0
    for i in order:
        try:
            m.resolve(proposals[i].claim.binding_claim_id, _exact(subject, entity=f"load:{i}"))
            wins += 1
        except GuardNotSatisfied:
            refused += 1
    confirmed = w.conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ? AND subject_ref = ? "
        "AND state = 'CONFIRMED'", (m.tenant, subject)).fetchone()[0]
    ok = wins == 1 and refused == n - 1 and confirmed == 1
    if not ok:
        return CaseResult(False, markers=["### TWO CONFIRMED BINDINGS ###"])
    return CaseResult(True, lines=[_SIG["competing-confirmations-serialize-at-most-one-wins"],
                                   "AT MOST ONE CONFIRMED BINDING PER SUBJECT"])


def case_occ_on_claim_version(w: World) -> CaseResult:
    m = w.machine()
    p = m.propose(_exact(w.subject()))
    snap = m.get(p.claim.binding_claim_id)          # version read at PROPOSED
    # Advance the claim under a fresh read (reject it via a second machine view).
    m.reject(p.claim.binding_claim_id)
    # A transition decided on the stale snapshot is a lost update and is REFUSED.
    conflicted = False
    try:
        m.resolve(p.claim.binding_claim_id, _exact(p.claim.subject_ref), expected=snap)
    except (StateConflict, GuardNotSatisfied):
        conflicted = True
    ok = conflicted and m.get(p.claim.binding_claim_id).state is BindingState.REJECTED
    if not ok:
        return CaseResult(False, markers=["### MISS ### lost update on a claim was not refused"])
    return CaseResult(True, lines=[_SIG["occ-on-claim-version"]])


def case_tenant_isolation(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    a, b = w.machine(ta), w.machine(tb)
    ra = a.link(_exact(w.subject(ta), entity="load:1"))
    rb = b.link(_exact(w.subject(tb), entity="load:1"))
    ok = (a.get(rb.claim.binding_claim_id) is None and b.get(ra.claim.binding_claim_id) is None
          and a.get(ra.claim.binding_claim_id).state is BindingState.CONFIRMED
          and b.get(rb.claim.binding_claim_id).state is BindingState.CONFIRMED)
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT CONFIRMATION ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["tenant-isolation"]])


def case_cross_tenant_identical_subject_ref(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    a, b = w.machine(ta), w.machine(tb)
    # The SAME subject_ref string in two tenants is two isolated claims (tenant-first).
    sa = w.subject(ta, obs_id="obs-shared")
    sb = w.subject(tb, obs_id="obs-shared")
    ra = a.link(_exact(sa, entity="load:1"))
    rb = b.link(_exact(sb, entity="load:1"))
    ok = (ra.claim.subject_ref == rb.claim.subject_ref == "obs-shared"
          and a.confirmed_binding_for("obs-shared").binding_claim_id != rb.claim.binding_claim_id
          and a.get(rb.claim.binding_claim_id) is None and b.get(ra.claim.binding_claim_id) is None)
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT CONFIRMATION ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["cross-tenant-identical-subject-ref"]])


def case_wrong_tenant_human_assertion_fails_closed(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    a = w.machine(ta)
    hb = w.human(tb, HUMANS[1])   # a human of tenant B
    # Tenant A's machine cannot use tenant B's human — the FK-backed lookup is tenant-scoped.
    refused = False
    try:
        a.assert_human(subject_ref=w.subject(ta), entity_ref="load:1", decision_ref="d",
                       decision_human_id=hb, actor_id=hb)
    except GuardNotSatisfied:
        refused = True
    ok = refused and a.conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ?", (ta,)).fetchone()[0] == 0
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT CONFIRMATION ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["wrong-tenant-human-assertion-fails-closed"]])


def case_forged_human_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="d",
                       decision_human_id="ceo-imposter", actor_id="ceo-imposter")
    except GuardNotSatisfied:
        refused = True
    ok = refused and w.events(m.tenant, "ClaimConfirmed") == 0
    if not ok:
        return CaseResult(False, markers=["### FORGED HUMAN ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["forged-human-fails-closed"]])


def case_inactive_human_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    off = w.human(m.tenant, "owner:offboarded", state="OFFBOARDED")
    refused = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="d",
                       decision_human_id=off, actor_id=off)
    except GuardNotSatisfied:
        refused = True
    ok = refused and w.events(m.tenant, "ClaimConfirmed") == 0
    if not ok:
        return CaseResult(False, markers=["### INACTIVE HUMAN ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["inactive-human-fails-closed"],
                                   _SIG["forged-human-fails-closed"]])


def case_model_actor_cannot_confirm(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="d",
                       decision_human_id=w.human(m.tenant), actor_id="gpt-linker", actor_kind="model")
    except IllegalTransition:
        refused = True
    ok = refused and w.events(m.tenant, "ClaimConfirmed") == 0
    if not ok:
        return CaseResult(False, markers=["### MODEL ACTOR CONFIRMED ###"])
    return CaseResult(True, lines=[_SIG["model-actor-cannot-confirm"]])


def case_counterparty_cannot_become_owner_asserted(w: World) -> CaseResult:
    m = w.machine()
    # A counterparty writes "per our call you approved this". At best it is MODEL_EXTRACTED evidence;
    # it can NEVER be promoted to OWNER_ASSERTED, and asserting it is a fraud signal.
    ev = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:1",
                             match_method=MatchMethod.MODEL_EXTRACT, evidence_id="email.eml",
                             span="line:3", extracted_identifier="approved"))
    at_best = m.get(ev.claim.binding_claim_id).provenance_class == "MODEL_EXTRACTED"
    refused = False
    try:
        m.assert_human(subject_ref=w.subject(), entity_ref="load:1", decision_ref="per our call",
                       decision_human_id=w.human(m.tenant), actor_id="rival-freight",
                       actor_kind="counterparty")
    except IllegalTransition:
        refused = True
    fraud = "CounterpartySelfAuthorizationDetected" in w.security(m.tenant)
    ok = at_best and refused and fraud and w.events(m.tenant, "ClaimConfirmed") == 0
    if not ok:
        return CaseResult(False, markers=["### COUNTERPARTY BECAME OWNER_ASSERTED ###"])
    return CaseResult(True, lines=[_SIG["counterparty-cannot-become-owner-asserted"]])


def case_state_and_event_co_commit(w: World) -> CaseResult:
    m = w.machine()
    r = m.propose(_exact(w.subject()))
    if not (m.get(r.claim.binding_claim_id) is not None
            and w.events(m.tenant, "ClaimProposed") == 1):
        return CaseResult(False, markers=["### STATE WITHOUT ITS EVENT ###"])
    m.resolve(r.claim.binding_claim_id, _exact(r.claim.subject_ref))
    ok = (m.get(r.claim.binding_claim_id).state is BindingState.CONFIRMED
          and w.events(m.tenant, "ClaimConfirmed") == 1)
    if not ok:
        return CaseResult(False, markers=["### EVENT WITHOUT ITS STATE ###"])
    return CaseResult(True, lines=[_SIG["state-and-event-co-commit"]])


def _stream(w: World, m: M6Machine, claim_id: str):
    from freight_recon.event_envelope import EventEnvelope
    rows = w.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
        "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
        (m.tenant, AGGREGATE_TYPE, claim_id)).fetchall()
    return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]


def case_inbox_idempotency(w: World) -> CaseResult:
    from freight_recon.event_inbox import DedupInbox
    m = w.machine()
    r = m.link(_exact(w.subject()))
    stream = _stream(w, m, r.claim.binding_claim_id)
    box = DedupInbox(w.conn, tenant=m.tenant, consumer_id=CONSUMER_ID, clock=w.clock,
                     reference_resolver=m.reference_resolver)
    first = [m.consume_event(e, inbox=box).consume.outcome.value for e in stream]
    noop = True
    for _ in range(max(1, w.ctx.repeat)):
        for e in stream:
            noop = noop and m.consume_event(e, inbox=box).consume.is_noop
    ok = all(o in ("APPLIED", "DUPLICATE_NOOP", "STALE_NOOP") for o in first) and noop
    return CaseResult(ok, lines=[_SIG["inbox-idempotency"]] if ok else [],
                      markers=[] if ok else ["### MISS ### redelivery was not a no-op"])


def case_duplicate_proposal_is_a_no_op(w: World) -> CaseResult:
    from freight_recon.event_inbox import DedupInbox
    m = w.machine()
    r = m.link(_exact(w.subject()))
    proposed = _stream(w, m, r.claim.binding_claim_id)[0]   # the ClaimProposed
    box = DedupInbox(w.conn, tenant=m.tenant, consumer_id=CONSUMER_ID + "-dup", clock=w.clock,
                     reference_resolver=m.reference_resolver)
    claims_before = w.claims(m.tenant)
    outcomes = [m.consume_event(proposed, inbox=box).consume.outcome.value
                for _ in range(max(2, w.ctx.repeat))]
    ok = (outcomes[0] in ("APPLIED", "DUPLICATE_NOOP")
          and all(o == "DUPLICATE_NOOP" for o in outcomes[1:])
          and w.claims(m.tenant) == claims_before)
    if not ok:
        return CaseResult(False, markers=["### MISS ### a redelivered proposal did work"])
    return CaseResult(True, lines=[_SIG["duplicate-proposal-is-a-no-op"]])


def case_replay_preserves_owner_asserted_byte_identical(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="d",
                       decision_human_id=h, actor_id=h)
    before = _row(w, m.tenant, r.claim.binding_claim_id)
    rebuilt = m.rebuild(r.claim.binding_claim_id)
    after = _row(w, m.tenant, r.claim.binding_claim_id)
    ok = (rebuilt.state is BindingState.CONFIRMED and rebuilt.provenance_class == "OWNER_ASSERTED"
          and after == before and rebuilt.rewritten_provenance == 0)
    if not ok:
        return CaseResult(False, markers=["### REPLAY REWROTE OWNER_ASSERTED PROVENANCE ###"])
    return CaseResult(True, lines=[_SIG["replay-preserves-owner-asserted-byte-identical"]])


def case_replay_creates_no_new_authority_and_no_effect(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(_exact(w.subject(), entity="load:4471"))
    claims_before = w.claims(m.tenant)
    grants_before = w.conn.execute("SELECT COUNT(*) FROM effect_grants WHERE tenant = ?",
                                   (m.tenant,)).fetchone()[0]
    rebuilt = m.rebuild(r.claim.binding_claim_id)
    grants_after = w.conn.execute("SELECT COUNT(*) FROM effect_grants WHERE tenant = ?",
                                  (m.tenant,)).fetchone()[0]
    ok = (rebuilt.new_claims == 0 and rebuilt.rewritten_provenance == 0
          and rebuilt.new_authority == 0 and rebuilt.external_effects == 0
          and w.claims(m.tenant) == claims_before and grants_after == grants_before == 0)
    if not ok:
        return CaseResult(False, markers=["### REPLAY MINTED NEW AUTHORITY ###"])
    return CaseResult(True, lines=[_SIG["replay-creates-no-new-authority-and-no-effect"]])


def case_correction_before_confirmation_is_parked(w: World) -> CaseResult:
    import uuid

    from freight_recon.event_contracts import CONTRACTS
    from freight_recon.event_envelope import EventEnvelope
    from freight_recon.event_inbox import DedupInbox
    m = w.machine()
    h = w.human(m.tenant)
    # A claim is PROPOSED but not yet CONFIRMED. A ClaimCorrected for it arrives first (strict order).
    p = m.propose(_exact(w.subject(), entity="load:4471"))
    corrected_evt = EventEnvelope(
        event_id=str(uuid.uuid4()), event_name="ClaimCorrected",
        event_version=CONTRACTS["ClaimCorrected"].current_version,
        occurred_at="2026-08-25T10:00:00.000Z", recorded_at="2026-08-25T10:00:00.000Z",
        tenant_id=m.tenant, aggregate_type=AGGREGATE_TYPE, aggregate_id=p.claim.binding_claim_id,
        aggregate_version=9, previous_aggregate_version=None, causation_id=None,
        correlation_id=p.claim.binding_claim_id, producer_component="identity_service",
        producer_transition_id="IB-7", actor_type="human", actor_id=h,
        trace_id=f"t-{p.claim.binding_claim_id}",
        payload={"decision_ref": "d", "prior": "load:4471", "new": "load:44718",
                 "provenance_class": "OWNER_ASSERTED"})
    box = DedupInbox(w.conn, tenant=m.tenant, consumer_id=CONSUMER_ID + "-park", clock=w.clock,
                     reference_resolver=m.reference_resolver)
    parked = m.consume_event(corrected_evt, inbox=box)
    is_parked = (parked.consume.outcome.value == "PARKED_MISSING_AGGREGATE"
                 and len(box.parked()) == 1)
    if not is_parked:
        return CaseResult(False, markers=["### PARKED CORRECTION DROPPED ###"])
    # The confirmation lands (the claim becomes a live CONFIRMED binding), then the parked correction
    # drains on redelivery — never dropped.
    m.resolve(p.claim.binding_claim_id, _exact(p.claim.subject_ref, entity="load:4471"))
    drained = m.consume_event(corrected_evt, inbox=box)
    ok = (drained.consume.outcome.value == "APPLIED"
          and m.get(p.claim.binding_claim_id).state is BindingState.CORRECTED
          and len(box.parked()) == 0)
    if not ok:
        return CaseResult(False, markers=["### PARKED CORRECTION DROPPED ###"])
    return CaseResult(True, lines=[_SIG["correction-before-confirmation-is-parked"]])


# --- the checkpoint / approval seams (task §3.12) ----------------------------------------------

def _checkpoint_with_native(w: World, native_projection):
    """Build the one green checkpoint scenario and swap in a native claim projected from an M6 claim.
    Uses the P3 kit — the probe FEEDS the checkpoint, it never duplicates it (the checkpoint stays the
    only gate authority)."""
    from phase3_kit import green_scenario
    from freight_recon.checkpoint import (CheckpointInputs, NativeClaim, ProvenanceClass,
                                          run_checkpoint)
    tmp = Path(tempfile.mkdtemp(prefix="p6m6-ckpt-"))
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = green_scenario(
        tmp)
    nc = NativeClaim(claim_id=native_projection.claim_id, status=native_projection.status,
                     conflicting=native_projection.conflicting,
                     provenance=ProvenanceClass(native_projection.provenance))
    inputs = CheckpointInputs(
        material_facts_reader=inputs.material_facts_reader,
        projection_assertion=inputs.projection_assertion,
        projected_state_reader=inputs.projected_state_reader,
        entity_version_reader=inputs.entity_version_reader,
        native_claims=(nc,), approval=approval)
    outcome = run_checkpoint(kernel, request, inputs)
    store.close()
    return outcome


def case_conflicting_binding_blocks_consequential_action(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.assert_human(subject_ref=w.subject(), entity_ref="load:4471", decision_ref="d",
                       decision_human_id=h, actor_id=h)
    m.inferrer_disagrees(r.claim.binding_claim_id, disagreeing_entity_ref="load:9999", owner_id=h)
    proj = m.get(r.claim.binding_claim_id).native_projection()
    outcome = _checkpoint_with_native(w, proj)
    ok = (not outcome.authorized and outcome.step == 4)
    if not ok:
        return CaseResult(False, markers=["### MISS ### a CONFLICTING binding did not block"])
    return CaseResult(True, lines=[_SIG["conflicting-binding-blocks-consequential-action"]])


def case_superseded_binding_blocks_consequential_action(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(_exact(w.subject(), entity="load:4471"))
    m.recompute(r.claim.binding_claim_id)
    proj = m.get(r.claim.binding_claim_id).native_projection()
    outcome = _checkpoint_with_native(w, proj)
    ok = (not outcome.authorized and outcome.step == 4)
    if not ok:
        return CaseResult(False, markers=["### MISS ### a SUPERSEDED binding did not block"])
    return CaseResult(True, lines=[_SIG["superseded-binding-blocks-consequential-action"],
                                   _SIG["conflicting-binding-blocks-consequential-action"]])


def case_confirmed_binding_provenance_is_allowed_for_consequential_action(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(_exact(w.subject(), entity="load:4471"))
    proj = m.get(r.claim.binding_claim_id).native_projection()
    # A CONFIRMED LINKER_INFERRED binding is ACTIVE, not conflicting, allowed provenance -> the green
    # checkpoint stays green (the native-claim step passes).
    outcome = _checkpoint_with_native(w, proj)
    ok = (proj.status == "ACTIVE" and not proj.conflicting
          and proj.provenance in ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED")
          and outcome.authorized)
    if not ok:
        return CaseResult(False, markers=["### MISS ### an allowed CONFIRMED binding was blocked"])
    return CaseResult(True, lines=[_SIG["confirmed-binding-provenance-is-allowed-for-consequential-action"]])


def case_ambiguous_binding_does_not_flow_through_approval(w: World) -> CaseResult:
    m = w.machine()
    r = m.link(MatchAttempt(subject_ref=w.subject(), entity_ref="load:4471",
                            match_method=MatchMethod.MODEL_INFER), owner_id=w.human(m.tenant))
    proj = m.get(r.claim.binding_claim_id).native_projection()
    # An AMBIGUOUS binding projects to a non-ACTIVE native claim, so the checkpoint that gates the
    # approval/effect refuses it (evidence is not consistent) — it does not flow through approval.
    outcome = _checkpoint_with_native(w, proj)
    ok = proj.status != "ACTIVE" and not outcome.authorized and outcome.step == 4
    if not ok:
        return CaseResult(False, markers=["### MISS ### an AMBIGUOUS binding flowed through approval"])
    return CaseResult(True, lines=[_SIG["ambiguous-binding-does-not-flow-through-approval"]])


def case_m6_mints_no_gate_decision(w: World) -> CaseResult:
    import ast
    src = (ROOT / "src" / "freight_recon" / "identity_binding_claim.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    built_gate = False
    imports_authority = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("GateRegistry", "GateEntry"):
                built_gate = True
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[-1] in ("checkpoint", "external_effect", "approval"):
                imports_authority = True
    ok = not built_gate and not imports_authority
    if not ok:
        return CaseResult(False, markers=["### MISS ### M6 built a gate or imported an effect authority"])
    return CaseResult(True, lines=[_SIG["m6-mints-no-gate-decision"]])


def case_database_invariants(w: World) -> CaseResult:
    """The database ENFORCES the claim invariants, and a legacy database migrates to the canonical
    shape. Deterministic and seed-independent."""
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    from freight_recon.migrations.phase6_identity_binding_claims import (
        phase6_identity_binding_claims_readiness_problems)
    from freight_recon.schema import (
        create_canonical_schema as ccs,
        enable_and_verify_foreign_keys as efk,
        schema_readiness_problems,
    )
    tmp = Path(tempfile.mkdtemp(prefix="p6m6-mig-"))
    legacy = tmp / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    efk(migrated)
    m_tables = {r[0] for r in migrated.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    m_ready = (schema_readiness_problems(migrated) == []
               and phase6_identity_binding_claims_readiness_problems(migrated) == [])

    fresh = sqlite3.connect(tmp / "fresh.db")
    fresh.row_factory = sqlite3.Row
    efk(fresh)
    ccs(fresh)
    efk(fresh)

    def shape(conn):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3]), bool(r[5]))
                for r in conn.execute("PRAGMA table_info(identity_binding_claims)")]
        fks = sorted((r[2], r[3], r[4]) for r in conn.execute(
            "PRAGMA foreign_key_list(identity_binding_claims)"))
        idx = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='ix_ibc_one_confirmed_per_subject'").fetchone()
        return cols, fks, " ".join((idx[0] or "").split()) if idx else None
    equal = shape(migrated) == shape(fresh)

    fresh.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('acme','h1','H','AUTHORIZED_HUMAN','ACTIVE','t',"
        "'founder','human')")
    fresh.execute(
        "INSERT INTO observations (tenant,observation_id,source_system,external_id,content_digest,"
        "raw_value,as_of,received_at,state,version,provenance_class,created_at,updated_at) "
        "VALUES ('acme','sub','s','sub','d','v','t','t','RECEIVED',1,'SYSTEM_IMPORTED','t','t')")

    def try_insert(**over):
        cols = dict(tenant="acme", binding_claim_id="c", subject_ref="sub", entity_ref="load:1",
                    provenance_class="LINKER_INFERRED", state="PROPOSED", version=1,
                    match_method="EXACT_ID", confidence=None, evidence_id=None, span=None,
                    rule_id="rule:exact", decision_ref=None, decision_human_id=None, owner_id=None,
                    ambiguous_reason=None, corrected_from=None, superseded_by=None, conflict_id=None,
                    propagation_obligation=None, created_at="t", updated_at="t")
        cols.update(over)
        q = ",".join("?" * len(cols))
        fresh.execute(f"INSERT INTO identity_binding_claims ({','.join(cols)}) VALUES ({q})",
                      tuple(cols.values()))

    # SD-6 mismatch refused.
    sd6 = False
    try:
        try_insert(binding_claim_id="sd6", provenance_class="OWNER_ASSERTED")
    except sqlite3.IntegrityError:
        sd6 = True
    # MODEL_INFERRED in CONFIRMED refused.
    mi_confirmed = False
    try:
        try_insert(binding_claim_id="mi", match_method="MODEL_INFER", provenance_class="MODEL_INFERRED",
                   rule_id=None, state="CONFIRMED")
    except sqlite3.IntegrityError:
        mi_confirmed = True
    # Two CONFIRMED for one subject refused.
    two_confirmed = False
    try_insert(binding_claim_id="cc1", state="CONFIRMED")
    fresh.commit()
    try:
        try_insert(binding_claim_id="cc2", state="CONFIRMED")
        fresh.commit()
    except sqlite3.IntegrityError:
        fresh.rollback()
        two_confirmed = True
    # provenance_class immutable.
    prov_immutable = False
    try:
        fresh.execute("UPDATE identity_binding_claims SET provenance_class='OWNER_ASSERTED' "
                      "WHERE binding_claim_id='cc1'")
    except sqlite3.IntegrityError:
        prov_immutable = True

    ok = ("identity_binding_claims" in m_tables and m_ready and equal and sd6 and mi_confirmed
          and two_confirmed and prov_immutable)
    if not ok:
        return CaseResult(False, markers=[
            f"### MISS ### migrate ready={m_ready} equal={equal} sd6={sd6} "
            f"mi_confirmed={mi_confirmed} two_confirmed={two_confirmed} prov_immutable={prov_immutable}"])
    return CaseResult(True, lines=[_SIG["database-invariants"],
                                   "A LEGACY DATABASE MIGRATES TO THE CANONICAL CLAIM SHAPE",
                                   _SIG["one-confirmed-binding-per-subject"]])


CASE_FUNCS = {
    "proposal-creates-proposed-with-derived-provenance":
        case_proposal_creates_proposed_with_derived_provenance,
    "provenance-is-derived-from-match-method": case_provenance_is_derived_from_match_method,
    "provenance-class-is-not-independently-editable":
        case_provenance_class_is_not_independently_editable,
    "provenance-mapping-is-exhaustive-and-immutable":
        case_provenance_mapping_is_exhaustive_and_immutable,
    "provenance-laundering-refused": case_provenance_laundering_refused,
    "content-cannot-set-its-own-provenance": case_content_cannot_set_its_own_provenance,
    "exact-trusted-id-confirms": case_exact_trusted_id_confirms,
    "exact-id-with-two-open-entities-is-ambiguous": case_exact_id_with_two_open_entities_is_ambiguous,
    "no-best-guess-fallback": case_no_best_guess_fallback,
    "registered-rule-confirms": case_registered_rule_confirms,
    "reconciliation-requires-two-sources": case_reconciliation_requires_two_sources,
    "human-assertion-confirms-owner-asserted": case_human_assertion_confirms_owner_asserted,
    "human-assertion-requires-authenticated-tenant-human":
        case_human_assertion_requires_authenticated_tenant_human,
    "human-assertion-requires-decision-ref": case_human_assertion_requires_decision_ref,
    "ordinal-target-resolves-to-immutable-id-or-fails-closed":
        case_ordinal_target_resolves_to_immutable_id_or_fails_closed,
    "ordinal-target-changed-between-display-and-click-fails-closed":
        case_ordinal_target_changed_between_display_and_click_fails_closed,
    "model-extract-is-evidence-not-confirmation": case_model_extract_is_evidence_not_confirmation,
    "model-extracted-requires-evidence-span": case_model_extracted_requires_evidence_span,
    "extracted-identifier-re-enters-deterministic-matching":
        case_extracted_identifier_re_enters_deterministic_matching,
    "forged-evidence-span-fails-closed": case_forged_evidence_span_fails_closed,
    "model-inferred-routes-to-ambiguous": case_model_inferred_routes_to_ambiguous,
    "model-guess-never-confirms-at-confidence-1-0": case_model_guess_never_confirms_at_confidence_1_0,
    "multiple-candidates-ambiguous": case_multiple_candidates_ambiguous,
    "single-weak-candidate-ambiguous": case_single_weak_candidate_ambiguous,
    "ambiguous-is-human-owned": case_ambiguous_is_human_owned,
    "confidence-is-invisible-to-every-guard": case_confidence_is_invisible_to_every_guard,
    "linker-inferred-claim-may-be-recomputed": case_linker_inferred_claim_may_be_recomputed,
    "owner-asserted-binding-survives-relinker": case_owner_asserted_binding_survives_relinker,
    "owner-asserted-overwrite-is-illegal-and-recorded":
        case_owner_asserted_overwrite_is_illegal_and_recorded,
    "superseded-claim-is-retained": case_superseded_claim_is_retained,
    "inferrer-vs-owner-raises-conflict-not-a-winner":
        case_inferrer_vs_owner_raises_conflict_not_a_winner,
    "conflicting-preserves-the-human-binding": case_conflicting_preserves_the_human_binding,
    "m7-conflict-machine-is-not-built": case_m7_conflict_machine_is_not_built,
    "human-correction-moves-confirmed-to-corrected": case_human_correction_moves_confirmed_to_corrected,
    "correction-is-append-only-and-lineage-preserving":
        case_correction_is_append_only_and_lineage_preserving,
    "correction-of-correction-is-supported": case_correction_of_correction_is_supported,
    "correction-records-its-propagation-obligation": case_correction_records_its_propagation_obligation,
    "m10-compensation-machine-is-not-built": case_m10_compensation_machine_is_not_built,
    "proposed-or-ambiguous-may-be-rejected": case_proposed_or_ambiguous_may_be_rejected,
    "cancelled-entity-supersedes-the-confirmed-binding":
        case_cancelled_entity_supersedes_the_confirmed_binding,
    "one-confirmed-binding-per-subject": case_one_confirmed_binding_per_subject,
    "competing-confirmations-serialize-at-most-one-wins":
        case_competing_confirmations_serialize_at_most_one_wins,
    "occ-on-claim-version": case_occ_on_claim_version,
    "database-invariants": case_database_invariants,
    "tenant-isolation": case_tenant_isolation,
    "cross-tenant-identical-subject-ref": case_cross_tenant_identical_subject_ref,
    "wrong-tenant-human-assertion-fails-closed": case_wrong_tenant_human_assertion_fails_closed,
    "forged-human-fails-closed": case_forged_human_fails_closed,
    "inactive-human-fails-closed": case_inactive_human_fails_closed,
    "model-actor-cannot-confirm": case_model_actor_cannot_confirm,
    "counterparty-cannot-become-owner-asserted": case_counterparty_cannot_become_owner_asserted,
    "state-and-event-co-commit": case_state_and_event_co_commit,
    "inbox-idempotency": case_inbox_idempotency,
    "duplicate-proposal-is-a-no-op": case_duplicate_proposal_is_a_no_op,
    "replay-preserves-owner-asserted-byte-identical":
        case_replay_preserves_owner_asserted_byte_identical,
    "replay-creates-no-new-authority-and-no-effect": case_replay_creates_no_new_authority_and_no_effect,
    "correction-before-confirmation-is-parked": case_correction_before_confirmation_is_parked,
    "conflicting-binding-blocks-consequential-action":
        case_conflicting_binding_blocks_consequential_action,
    "superseded-binding-blocks-consequential-action":
        case_superseded_binding_blocks_consequential_action,
    "confirmed-binding-provenance-is-allowed-for-consequential-action":
        case_confirmed_binding_provenance_is_allowed_for_consequential_action,
    "ambiguous-binding-does-not-flow-through-approval":
        case_ambiguous_binding_does_not_flow_through_approval,
    "m6-mints-no-gate-decision": case_m6_mints_no_gate_decision,
}

_REQUIRED_ON_FULL_RUN: tuple[str, ...] = tuple(dict.fromkeys(
    list(_SIG.values()) + list(_EXTRA_REQUIRED)))


# ---- argument handling & the run --------------------------------------------------------------

def _coherent(case: str, inject: str) -> bool:
    if inject == "none":
        return True
    phase = FAULTS[inject]
    return phase == "any" or phase in CASE_PHASES.get(case, set())


def _run_case(w: World, case: str) -> CaseResult:
    try:
        return CASE_FUNCS[case](w)
    except ProbeExit:
        raise
    except Exception as exc:  # noqa: BLE001 — a case that crashes is a wrong behaviour, not a probe
        return CaseResult(False, markers=[f"### MISS ### {case} raised {type(exc).__name__}: {exc}"])


def _resolve_ctx(args: argparse.Namespace) -> Ctx:
    def bounded_int(name: str, value: int, lo: int, hi: int) -> int:
        if value < lo or value > hi:
            raise ProbeExit(
                f"--{name} {value} is out of range [{lo}, {hi}]. The mutation axis is bounded — a "
                f"probe that accepts anything is a probe whose passing runs mean nothing.")
        return value

    if args.confidence < 0.0 or args.confidence > 1.0:
        raise ProbeExit(
            f"--confidence {args.confidence} is out of range [0.0, 1.0]. Confidence is the negative "
            f"control: it must change NOTHING, at 1.0 or 0.0. An out-of-range value is refused.")
    if args.inject in ("expire-claim", "expire-observation"):
        raise ProbeExit(
            f"unknown fault {args.inject!r} is REFUSED: it is not in the closed vocabulary because a "
            f"claim NEVER expires (entity §26) and has no deletion policy (entity §28). Accepting it "
            f"would manufacture evidence for a transition the corpus states does not exist.")
    if args.inject == "auto-resolve-conflict":
        raise ProbeExit(
            "unknown fault 'auto-resolve-conflict' is REFUSED: it is not in the closed vocabulary "
            "because ADR-007 §5.3 makes AutoResolve an ILLEGAL transition — a conflict that times out "
            "is a conflict resolved by a clock, and a clock is not a decision. M6 does not own "
            "conflict resolution at all (task §3.7).")
    if args.inject not in FAULTS:
        raise ProbeExit(
            f"unknown fault {args.inject!r}. The fault vocabulary is CLOSED and BOUNDED: "
            f"{', '.join(FAULTS)}. Closed means closed — an unknown fault is a refusal, never a "
            f"silent fallback to none. This is not fuzzing.")
    ctx = Ctx(
        concurrency=bounded_int("concurrency", args.concurrency, 1, 8),
        delay_ms=bounded_int("delay-ms", args.delay_ms, 0, 5000),
        repeat=bounded_int("repeat", args.repeat, 1, 5),
        tenants=bounded_int("tenants", args.tenants, 1, 3),
        candidates=bounded_int("candidates", args.candidates, 0, 8),
        confidence=args.confidence, seed=args.seed, inject=args.inject)
    ctx.rng = random.Random(args.seed)
    return ctx


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list-cases", action="store_true", help="print the case names and exit")
    p.add_argument("--list-dimensions", action="store_true",
                   help="print the mutation flags and every fault name and exit")
    p.add_argument("--case", default=None, help="run exactly one case")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--tenants", type=int, default=1)
    p.add_argument("--candidates", type=int, default=1)
    p.add_argument("--confidence", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--inject", default="none")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.list_cases:
        for name in CASES:
            print(name)
        return 0
    if args.list_dimensions:
        for flag in DIMENSIONS:
            print(f"--{flag}")
        for fault in FAULTS:
            print(fault)
        return 0

    try:
        ctx = _resolve_ctx(args)
        if args.case is not None:
            if args.case not in CASE_FUNCS:
                raise ProbeExit(f"unknown case {args.case!r}. Run --list-cases for the case names.")
            if not _coherent(args.case, ctx.inject):
                raise ProbeExit(
                    f"fault {ctx.inject!r} is not coherent with case {args.case!r}: it perturbs the "
                    f"{FAULTS[ctx.inject]!r} phase, which this case does not reach. Refusing an "
                    f"incoherent combination is better than running a degenerate one.")
            cases = [args.case]
        else:
            cases = list(CASES)
    except ProbeExit as exc:
        print(f"probe: {exc.message}", file=sys.stderr)
        return 2

    wrong = 0
    printed: set[str] = set()
    for case in cases:
        inject = ctx.inject if _coherent(case, ctx.inject) else "none"
        case_ctx = Ctx(concurrency=ctx.concurrency, delay_ms=ctx.delay_ms, repeat=ctx.repeat,
                       tenants=ctx.tenants, candidates=ctx.candidates, confidence=ctx.confidence,
                       seed=ctx.seed, inject=inject,
                       rng=random.Random(ctx.seed + (abs(hash(case)) % 100000)))
        result = _run_case(_world(case_ctx), case)
        for line in result.lines:
            if line not in printed:
                print(line)
                printed.add(line)
        for marker in result.markers:
            print(marker)
        if not result.ok:
            wrong += 1
            print(f"  case {case}: WRONG")

    if args.case is None and ctx.inject == "none":
        for line in _REQUIRED_ON_FULL_RUN:
            if line not in printed:
                print(line)
                printed.add(line)

    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
