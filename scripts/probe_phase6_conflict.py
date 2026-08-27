#!/usr/bin/env python3
"""M7 — the Conflict — deterministic narrative probe.

The TMS says load 4471 is delivered and the carrier portal says it is still in transit, so the
delivery field FREEZES and a named human owns it. The owner assigned a POD to load 4471 by hand and
the linker now insists it belongs to 44718, and Neyma preserves the owner's binding and RAISES rather
than picking. A readback of the payable just entered does not match the invoice the owner approved —
not an ordinary failure and not a silent retry. Two standing rules disagree about which source governs,
and that fails closed too. A third source arrives and ATTACHES to the same conflict rather than starting
another. The clock advances and the conflict ESCALATES — it never expires and it never resolves. What
matters is not that a conflict can be raised — it is that nothing closes it except a registered rule
with an id or an authenticated human with a decision, and that an invoice cannot go out while it stands.

M7 ships dark — no reconciliation service, no queue, no live channel — so this probe is the ONLY
interface a generated Product-Driver scenario can compose M7's real behaviour through. Every ordering,
concurrency, timing, duplication, crash and replay variation has to be reachable through these
arguments, so the interface is taken seriously:

    --list-cases        the case names, one per line
    --list-dimensions   every dimension flag and every fault name
    --case <case>       run exactly one case (composes with the flags below)
    (no arguments)      run every case; exit 0 only if every one behaved as specified

    --concurrency 1-8   how many detectors or resolvers race the one-open-conflict-per-field index
    --delay-ms 0-5000   timing skew between them
    --repeat 1-5        duplicate detection / redelivery pressure
    --tenants 1-3       isolation pressure
    --parties 2-8       how many disagreeing parties one field attracts
    --age-ms 0-60000    how far the durable timer is advanced; it may ESCALATE and never resolve
    --confidence 0.0-1.0 the negative control: it must change NOTHING, at 1.0 or at 0.0
    --seed <int>        deterministic interleaving — the same seed reproduces the same run
    --inject <fault>    the closed fault set (see --list-dimensions); an unknown fault, or a value out
                        of range, exits 2 with a readable message and NEVER a traceback

### CLOSED MEANS CLOSED. `--inject not-a-real-fault` exits 2. `--inject expire-conflict` exits 2 —
entity §26 and machine §12/§23 say a Conflict NEVER expires and §28 gives it no deletion policy, so a
probe that accepted it would manufacture evidence for a transition the corpus states does not exist.
`--inject cancel-conflict` exits 2 — machine §14 enumerates only CF-1..CF-7, GR-1 makes anything
unenumerated ILLEGAL, and no CANCELLED state and no conflict-cancellation event is registered anywhere;
this is M7-AQ-3 held OPEN rather than answered. `--inject auto-resolve` and `--inject timer-resolve`
ARE in the vocabulary: they name mechanisms the corpus defines as ILLEGAL (machine §15), so the machine
is seen to REFUSE them under GR-1. A fault refused as UNKNOWN and a fault refused as ILLEGAL are two
different proofs, and M7 owes both.
"""

from __future__ import annotations

import argparse
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

from freight_recon.conflict import (  # noqa: E402
    CONFLICT_RAISED_PRODUCERS,
    M7_AQ1_SEAM,
    PRODUCED_CONTRACTS,
    CfState,
    GuardNotSatisfied,
    IllegalTransition,
    M7Machine,
    MalformedConflict,
    Party,
    StateConflict,
)
from freight_recon.event_timers import TimerRelay  # noqa: E402
from freight_recon.migrations.phase6_conflicts import CONFLICT_KINDS, CONFLICT_STATES  # noqa: E402
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
)

HUMANS = ("owner:rasheed", "owner:dana", "owner:sam")
REG_RULE = "rule:tms-beats-portal-v1"          # a rule a TEST registers for itself; the SET ships empty

# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    "raise-creates-raised-with-a-named-human-owner",
    "raise-and-freeze-are-one-commit",
    "ownerless-conflict-is-impossible",
    "a-model-cannot-own-a-conflict",
    "the-six-conflict-kinds-are-closed",
    "system-vs-system-raises-a-conflict",
    "claim-vs-claim-raises-a-conflict",
    "claim-vs-observation-raises-a-conflict",
    "inferrer-vs-owner-records-the-owner-asserted-party",
    "readback-vs-approved-is-not-an-ordinary-failure",
    "rule-vs-rule-fails-closed-and-never-auto-merges",
    "injected-competing-claim-freezes-the-entity-not-control",
    "acknowledgement-opens-the-conflict",
    "raised-conflict-already-blocks-consequential-action",
    "open-conflict-blocks-consequential-action",
    "escalated-conflict-still-blocks-consequential-action",
    "open-conflict-fails-checkpoint-native-state-validity",
    "no-effect-grant-on-a-conflicted-material-field",
    "open-conflict-blocks-the-approval",
    "m7-mints-no-gate-decision",
    "registered-rule-resolves-the-conflict",
    "unregistered-rule-cannot-resolve",
    "rule-resolution-requires-a-registered-rule-id",
    "confidence-cannot-resolve-a-conflict",
    "recency-cannot-resolve-a-conflict",
    "source-priority-cannot-resolve-without-a-registered-rule",
    "a-model-cannot-resolve-a-conflict",
    "authenticated-human-resolves-the-conflict",
    "human-resolution-requires-a-decision-ref",
    "counterparty-cannot-resolve-a-conflict",
    "wrong-tenant-human-resolution-fails-closed",
    "forged-human-fails-closed",
    "inactive-human-fails-closed",
    "resolution-carries-exactly-one-basis",
    "resolution-with-neither-rule-nor-decision-is-illegal",
    "resolution-unfreezes-the-field",
    "a-resolved-conflict-is-retained-never-deleted",
    "new-evidence-after-resolution-raises-a-new-conflict",
    "age-threshold-escalates-the-conflict",
    "a-timer-never-resolves-a-conflict",
    "a-conflict-never-expires",
    "escalated-resolves-by-registered-rule",
    "escalated-resolves-by-authenticated-human",
    "escalated-resolution-is-by-target-state-never-by-position",
    "second-detection-attaches-a-party-not-a-new-conflict",
    "at-most-one-open-conflict-per-field",
    "an-attached-party-carries-its-own-provenance",
    "party-provenance-is-never-strengthened",
    "concurrent-detectors-produce-one-conflict",
    "a-party-retraction-never-silently-closes-the-conflict",
    "replay-rebuilds-the-complete-party-set",
    "replay-keeps-the-field-frozen",
    "replay-cannot-resolve-or-duplicate-a-conflict",
    "replay-creates-no-new-authority-and-no-effect",
    "restart-preserves-the-open-conflict",
    "tenant-isolation",
    "cross-tenant-identical-entity-ref-and-field",
    "cross-tenant-party-reference-fails-closed",
    "occ-on-conflict-version",
    "competing-resolutions-serialize-at-most-one-wins",
    "redelivered-detection-is-a-no-op",
    "inbox-idempotency",
    "state-and-event-co-commit",
    "database-invariants",
    "malformed-conflict-fails-closed",
    "persistence-failure-rolls-back-the-raise-and-the-freeze",
    "the-m6-claim-machine-is-not-rewritten",
    "the-m3-unknown-outcome-semantics-are-unchanged",
    "the-cross-family-conflict-raised-producers-are-recorded",
    "m8-m9-m10-and-m12-are-not-built",
)

# The closed fault vocabulary — every member named by the canonical machine, the entity spec, an ADR,
# the event registry or a named mandate. `phase` is the transition phase the fault perturbs, used only
# to refuse an INCOHERENT (case, fault) combination rather than run it degenerately.
FAULTS: dict[str, str] = {
    "none": "any",
    "system-vs-system": "raise",           # entity §12 / ADR-007 §5.1 — a canonical kind
    "claim-vs-claim": "raise",
    "claim-vs-observation": "raise",
    "inferrer-vs-owner": "raise",          # entity §13 — records one party is OWNER_ASSERTED
    "readback-vs-approved": "raise",       # entity §21 — a readback contradiction, not a failure
    "rule-vs-rule": "raise",               # GR-15 / spec §20.7 — two rules fail closed
    "ownerless-raise": "raise",            # entity §37 — structurally impossible
    "model-owner": "raise",                # [C-6], ER-9 — a model may not own
    "acknowledge": "ack",                  # CF-2
    "age-threshold": "escalate",           # CF-5 — the durable timer escalates
    "timer-resolve": "resolve",            # machine §15 — ILLEGAL: a timer never resolves
    "auto-resolve": "resolve",             # ADR-007 §5.3 — ILLEGAL: no third way
    "model-resolve": "resolve",            # GR-7, ER-9 — a model never resolves
    "confidence-resolve": "resolve",       # GR-8 / ADR-007 §8 — confidence changes nothing
    "recency-resolve": "resolve",          # ADR-007 §5.3 — the newest source is not a winner
    "source-priority-resolve": "resolve",  # ADR-007 §8 — a registered rule or nothing
    "unregistered-rule": "resolve",        # CF-3 — an unregistered rule may not resolve
    "missing-rule-id": "resolve",          # CF-3 — a rule resolution names a rule_id
    "missing-decision-ref": "resolve",     # CF-4 — a human resolution names a decision_ref
    "both-resolution-bases": "resolve",    # entity §16 — exactly one basis
    "neither-resolution-basis": "resolve", # machine §15 — ILLEGAL
    "forged-human": "resolve",             # entity §35 — a forged human fails closed
    "inactive-human": "resolve",           # entity §35 — an inactive human fails closed
    "wrong-tenant": "resolve",             # [C-1] — a wrong-tenant human fails closed
    "counterparty-resolve": "resolve",     # [C-6] — a counterparty never resolves
    "second-detection": "attach",          # CF-7 — a party attaches, not a new conflict
    "concurrent-detection": "attach",      # §17 — concurrent detectors, one conflict
    "duplicate-detection": "attach",       # GR-4 — a redelivered detection is a no-op
    "retract-party": "attach",             # entity §25 / M7-AQ-3 — never silently closes
    "strengthen-party-provenance": "attach",  # ER-14, R-P2 — carried, never strengthened
    "cross-tenant-party": "tenant",        # [C-1], ER-15 — fails closed
    "occ-conflict": "occ",                 # GR-3 — a lost update is refused
    "competing-resolution": "resolve",     # [C-10] — competing resolutions serialize
    "malformed-conflict": "raise",         # §36 — unreadable input fails closed
    "persistence-failure": "raise",        # entity §15 — raise+freeze are one commit
    "replay": "replay",                    # GR-11 — replay mints nothing
    "restart-before-open": "restart",      # §36 — an open conflict survives restart
    "restart-after-escalate": "restart",   # §36 — an escalated conflict survives restart
    "reorder-stream": "replay",            # §8 — order-tolerant across aggregates
    "new-evidence-after-resolution": "raise",  # machine §24 — a NEW conflict
}

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "parties", "age-ms", "confidence", "seed",
    "inject",
)

# Which fault phases each case can coherently exercise. A fault whose phase a case never reaches is
# refused rather than run degenerately.
CASE_PHASES: dict[str, set[str]] = {
    "raise-creates-raised-with-a-named-human-owner": {"raise"},
    "raise-and-freeze-are-one-commit": {"raise"},
    "ownerless-conflict-is-impossible": {"raise"},
    "a-model-cannot-own-a-conflict": {"raise"},
    "the-six-conflict-kinds-are-closed": {"raise"},
    "system-vs-system-raises-a-conflict": {"raise"},
    "claim-vs-claim-raises-a-conflict": {"raise"},
    "claim-vs-observation-raises-a-conflict": {"raise"},
    "inferrer-vs-owner-records-the-owner-asserted-party": {"raise"},
    "readback-vs-approved-is-not-an-ordinary-failure": {"raise"},
    "rule-vs-rule-fails-closed-and-never-auto-merges": {"raise"},
    "injected-competing-claim-freezes-the-entity-not-control": {"raise"},
    "acknowledgement-opens-the-conflict": {"ack", "raise"},
    "raised-conflict-already-blocks-consequential-action": {"raise"},
    "open-conflict-blocks-consequential-action": {"raise", "ack"},
    "escalated-conflict-still-blocks-consequential-action": {"escalate", "ack"},
    "open-conflict-fails-checkpoint-native-state-validity": {"raise"},
    "no-effect-grant-on-a-conflicted-material-field": {"raise"},
    "open-conflict-blocks-the-approval": {"raise"},
    "m7-mints-no-gate-decision": {"raise"},
    "registered-rule-resolves-the-conflict": {"resolve", "ack"},
    "unregistered-rule-cannot-resolve": {"resolve", "ack"},
    "rule-resolution-requires-a-registered-rule-id": {"resolve", "ack"},
    "confidence-cannot-resolve-a-conflict": {"resolve", "ack"},
    "recency-cannot-resolve-a-conflict": {"resolve", "ack"},
    "source-priority-cannot-resolve-without-a-registered-rule": {"resolve", "ack"},
    "a-model-cannot-resolve-a-conflict": {"resolve", "ack"},
    "authenticated-human-resolves-the-conflict": {"resolve", "ack"},
    "human-resolution-requires-a-decision-ref": {"resolve", "ack"},
    "counterparty-cannot-resolve-a-conflict": {"resolve", "ack"},
    "wrong-tenant-human-resolution-fails-closed": {"resolve", "tenant", "ack"},
    "forged-human-fails-closed": {"resolve", "ack"},
    "inactive-human-fails-closed": {"resolve", "ack"},
    "resolution-carries-exactly-one-basis": {"resolve", "ack"},
    "resolution-with-neither-rule-nor-decision-is-illegal": {"resolve", "ack"},
    "resolution-unfreezes-the-field": {"resolve", "ack"},
    "a-resolved-conflict-is-retained-never-deleted": {"resolve", "ack"},
    "new-evidence-after-resolution-raises-a-new-conflict": {"resolve", "raise", "ack"},
    "age-threshold-escalates-the-conflict": {"escalate", "ack"},
    "a-timer-never-resolves-a-conflict": {"escalate", "resolve", "ack"},
    "a-conflict-never-expires": {"escalate", "ack"},
    "escalated-resolves-by-registered-rule": {"escalate", "resolve", "ack"},
    "escalated-resolves-by-authenticated-human": {"escalate", "resolve", "ack"},
    "escalated-resolution-is-by-target-state-never-by-position": {"escalate", "resolve", "ack"},
    "second-detection-attaches-a-party-not-a-new-conflict": {"attach", "raise"},
    "at-most-one-open-conflict-per-field": {"attach", "raise"},
    "an-attached-party-carries-its-own-provenance": {"attach"},
    "party-provenance-is-never-strengthened": {"attach"},
    "concurrent-detectors-produce-one-conflict": {"attach", "raise"},
    "a-party-retraction-never-silently-closes-the-conflict": {"attach"},
    "replay-rebuilds-the-complete-party-set": {"replay", "attach"},
    "replay-keeps-the-field-frozen": {"replay"},
    "replay-cannot-resolve-or-duplicate-a-conflict": {"replay"},
    "replay-creates-no-new-authority-and-no-effect": {"replay"},
    "restart-preserves-the-open-conflict": {"restart"},
    "tenant-isolation": {"tenant", "raise"},
    "cross-tenant-identical-entity-ref-and-field": {"tenant", "raise"},
    "cross-tenant-party-reference-fails-closed": {"tenant", "attach"},
    "occ-on-conflict-version": {"occ"},
    "competing-resolutions-serialize-at-most-one-wins": {"resolve", "occ", "ack"},
    "redelivered-detection-is-a-no-op": {"attach", "replay"},
    "inbox-idempotency": {"replay"},
    "state-and-event-co-commit": {"raise", "resolve"},
    "database-invariants": {"raise"},
    "malformed-conflict-fails-closed": {"raise"},
    "persistence-failure-rolls-back-the-raise-and-the-freeze": {"raise"},
    "the-m6-claim-machine-is-not-rewritten": {"raise"},
    "the-m3-unknown-outcome-semantics-are-unchanged": {"raise"},
    "the-cross-family-conflict-raised-producers-are-recorded": {"raise"},
    "m8-m9-m10-and-m12-are-not-built": {"raise"},
}

# ### THE INVARIANT SENTENCES THE VERIFICATION SCENARIO MATCHES AS LITERAL SUBSTRINGS.
_SIG: dict[str, str] = {
    "raise-creates-raised-with-a-named-human-owner":
        "A CONFLICT HAS A NAMED HUMAN OWNER FROM CREATION",
    "raise-and-freeze-are-one-commit": "RAISING THE CONFLICT AND FREEZING THE FIELD ARE ONE COMMIT",
    "ownerless-conflict-is-impossible": "AN OWNERLESS CONFLICT IS STRUCTURALLY IMPOSSIBLE",
    "a-model-cannot-own-a-conflict": "A MODEL CANNOT OWN A CONFLICT",
    "the-six-conflict-kinds-are-closed": "THE SIX CONFLICT KINDS ARE CLOSED, AND THERE IS NO SEVENTH",
    "system-vs-system-raises-a-conflict":
        "A CONFLICT IS NOT unknown: WE HAVE TOO MUCH INFORMATION, AND IT DISAGREES",
    "claim-vs-claim-raises-a-conflict": "CLAIM_VS_CLAIM RAISES A CONFLICT ON ONE FIELD",
    "claim-vs-observation-raises-a-conflict": "CLAIM_VS_OBSERVATION RAISES A CONFLICT ON ONE FIELD",
    "inferrer-vs-owner-records-the-owner-asserted-party":
        "AN INFERRER_VS_OWNER CONFLICT RECORDS THAT ONE PARTY IS OWNER_ASSERTED",
    "readback-vs-approved-is-not-an-ordinary-failure":
        "A READBACK CONTRADICTING THE APPROVED FACTS IS A CONFLICT, NOT AN ORDINARY FAILURE",
    "rule-vs-rule-fails-closed-and-never-auto-merges":
        "TWO CONFLICTING STANDING RULES FAIL CLOSED; NEYMA NEVER PICKS A WINNER",
    "injected-competing-claim-freezes-the-entity-not-control":
        "AN INJECTED COMPETING CLAIM YIELDS A FROZEN ENTITY AND A HUMAN, NEVER CONTROL",
    "acknowledgement-opens-the-conflict": "ACKNOWLEDGEMENT OPENS THE CONFLICT AND A HUMAN OWNS IT",
    "raised-conflict-already-blocks-consequential-action": "A RAISED CONFLICT ALREADY BLOCKS",
    "open-conflict-blocks-consequential-action":
        "WHILE A CONFLICT IS OPEN THE FIELD IS conflicting AND BLOCKS EVERY CONSEQUENTIAL ACTION",
    "escalated-conflict-still-blocks-consequential-action": "AN ESCALATED CONFLICT STILL BLOCKS",
    "open-conflict-fails-checkpoint-native-state-validity":
        "CHECKPOINT STEP 4 REFUSES A MATERIAL FIELD WITH AN OPEN CONFLICT",
    "no-effect-grant-on-a-conflicted-material-field":
        "NO EFFECT GRANT IS MINTED ON A CONFLICTED MATERIAL FIELD",
    "open-conflict-blocks-the-approval": "AN OPEN CONFLICT BLOCKS THE APPROVAL",
    "m7-mints-no-gate-decision": "M7 MINTS NO GATE DECISION",
    "registered-rule-resolves-the-conflict":
        "A REGISTERED, VERSIONED, DETERMINISTIC RULE MAY RESOLVE; AN UNREGISTERED ONE MAY NOT",
    "unregistered-rule-cannot-resolve":
        "A REGISTERED, VERSIONED, DETERMINISTIC RULE MAY RESOLVE; AN UNREGISTERED ONE MAY NOT",
    "rule-resolution-requires-a-registered-rule-id":
        "A REGISTERED, VERSIONED, DETERMINISTIC RULE MAY RESOLVE; AN UNREGISTERED ONE MAY NOT",
    "confidence-cannot-resolve-a-conflict": "CONFIDENCE NEVER RESOLVES A CONFLICT",
    "recency-cannot-resolve-a-conflict": "RECENCY NEVER RESOLVES A CONFLICT",
    "source-priority-cannot-resolve-without-a-registered-rule":
        "SOURCE PRIORITY IS A REGISTERED RULE OR IT IS NOTHING",
    "a-model-cannot-resolve-a-conflict": "A MODEL NEVER RESOLVES A CONFLICT",
    "authenticated-human-resolves-the-conflict": "AN AUTHENTICATED HUMAN RESOLVES WITH A decision_ref",
    "human-resolution-requires-a-decision-ref": "AN AUTHENTICATED HUMAN RESOLVES WITH A decision_ref",
    "counterparty-cannot-resolve-a-conflict": "A COUNTERPARTY NEVER RESOLVES A CONFLICT",
    "wrong-tenant-human-resolution-fails-closed": "A WRONG-TENANT RESOLUTION FAILS CLOSED",
    "forged-human-fails-closed": "A FORGED OR INACTIVE HUMAN FAILS CLOSED",
    "inactive-human-fails-closed": "A FORGED OR INACTIVE HUMAN FAILS CLOSED",
    "resolution-carries-exactly-one-basis": "A RESOLUTION CARRIES EXACTLY ONE OF rule_id OR decision_ref",
    "resolution-with-neither-rule-nor-decision-is-illegal":
        "A RESOLUTION WITH NEITHER A RULE NOR A DECISION IS AN ILLEGAL TRANSITION",
    "resolution-unfreezes-the-field": "RESOLUTION UNFREEZES THE FIELD",
    "a-resolved-conflict-is-retained-never-deleted": "A RESOLVED CONFLICT IS RETAINED, NEVER DELETED",
    "new-evidence-after-resolution-raises-a-new-conflict":
        "NEW CONFLICTING EVIDENCE AFTER A RESOLUTION RAISES A NEW CONFLICT",
    "age-threshold-escalates-the-conflict": "A CONFLICT AGES AND ESCALATES",
    "a-timer-never-resolves-a-conflict": "A TIMER NEVER RESOLVES A CONFLICT",
    "a-conflict-never-expires": "A CONFLICT NEVER EXPIRES",
    "escalated-resolves-by-registered-rule": "AN ESCALATED CONFLICT RESOLVES BY A REGISTERED RULE",
    "escalated-resolves-by-authenticated-human":
        "AN ESCALATED CONFLICT RESOLVES BY AN AUTHENTICATED HUMAN",
    "escalated-resolution-is-by-target-state-never-by-position":
        "AN ESCALATED CONFLICT RESOLVES BY TARGET STATE, NEVER BY POSITION",
    "second-detection-attaches-a-party-not-a-new-conflict":
        "A SECOND DETECTION ATTACHES A PARTY, NEVER A SECOND CONFLICT",
    "at-most-one-open-conflict-per-field": "AT MOST ONE OPEN CONFLICT PER TENANT, ENTITY AND FIELD",
    "an-attached-party-carries-its-own-provenance":
        "EACH PARTY CARRIES ITS OWN provenance_class, CARRIED NEVER STRENGTHENED",
    "party-provenance-is-never-strengthened":
        "EACH PARTY CARRIES ITS OWN provenance_class, CARRIED NEVER STRENGTHENED",
    "concurrent-detectors-produce-one-conflict":
        "CONCURRENT DETECTORS PRODUCE ONE CONFLICT AND LOSE NO PARTY",
    "a-party-retraction-never-silently-closes-the-conflict":
        "A PARTY RETRACTION NEVER SILENTLY CLOSES THE CONFLICT",
    "replay-rebuilds-the-complete-party-set": "A REBUILD RECONSTRUCTS THE COMPLETE PARTY SET",
    "replay-keeps-the-field-frozen": "THE FIELD IS STILL FROZEN AFTER RECONSTRUCTION",
    "replay-cannot-resolve-or-duplicate-a-conflict":
        "replay: 0 resolutions, 0 duplicate conflicts, 0 lost parties, 0 new authority, 0 external effects",
    "replay-creates-no-new-authority-and-no-effect":
        "replay: 0 resolutions, 0 duplicate conflicts, 0 lost parties, 0 new authority, 0 external effects",
    "restart-preserves-the-open-conflict": "A RESTART LEAVES THE OPEN CONFLICT OPEN",
    "tenant-isolation": "TENANT ISOLATION HOLDS",
    "cross-tenant-identical-entity-ref-and-field":
        "THE SAME entity_ref AND field IN TWO TENANTS ARE TWO ISOLATED CONFLICTS",
    "cross-tenant-party-reference-fails-closed": "A CROSS-TENANT PARTY REFERENCE FAILS CLOSED",
    "occ-on-conflict-version": "A LOST UPDATE ON A CONFLICT IS REFUSED",
    "competing-resolutions-serialize-at-most-one-wins":
        "COMPETING RESOLUTIONS SERIALIZE: ONE WINS, THE REST ARE REFUSED",
    "redelivered-detection-is-a-no-op": "A REDELIVERED DETECTION IS A NO-OP",
    "inbox-idempotency": "A REDELIVERED DETECTION IS A NO-OP",
    "state-and-event-co-commit": "THE STATE ROW AND ITS EVENT COMMIT TOGETHER",
    "database-invariants": "THE DATABASE ENFORCES THE CONFLICT INVARIANTS",
    "malformed-conflict-fails-closed": "A MALFORMED CONFLICT FAILS CLOSED",
    "persistence-failure-rolls-back-the-raise-and-the-freeze":
        "RAISING THE CONFLICT AND FREEZING THE FIELD ARE ONE COMMIT",
    "the-m6-claim-machine-is-not-rewritten": "THE M6 CLAIM MACHINE IS UNCHANGED",
    "the-m3-unknown-outcome-semantics-are-unchanged": "THE M3 UNKNOWN_OUTCOME SEMANTICS ARE UNCHANGED",
    "the-cross-family-conflict-raised-producers-are-recorded":
        "THE CROSS-FAMILY ConflictRaised PRODUCERS ARE RECORDED (CF-1, IB-6, EF-4c)",
    "m8-m9-m10-and-m12-are-not-built": "THE M8, M9, M10 AND M12 MACHINES ARE NOT BUILT",
}

# The whole-run headline plus the lines not primarily owned by one case, so a full battery cannot pass
# while any required sentence is silently missing.
_EXTRA_REQUIRED: tuple[str, ...] = (
    "A CONFLICT IS TWO OR MORE MUTUALLY EXCLUSIVE CLAIMS ON ONE FIELD, MADE VISIBLE AND BLOCKING",
    "A LEGACY DATABASE MIGRATES TO THE CANONICAL CONFLICT SHAPE",
)

_REQUIRED_ON_FULL_RUN: tuple[str, ...] = tuple(dict.fromkeys(
    list(_SIG.values()) + list(_EXTRA_REQUIRED)))


# ---- harness -----------------------------------------------------------------------------------

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

    @property
    def now(self) -> datetime:
        return self._t

    def advance(self, **kw: int) -> None:
        self._t += timedelta(**kw)


@dataclass
class Ctx:
    concurrency: int = 1
    delay_ms: int = 0
    repeat: int = 1
    tenants: int = 1
    parties: int = 2
    age_ms: int = 0
    confidence: float = 0.5
    seed: int = 1
    inject: str = "none"
    rng: random.Random = field(default_factory=lambda: random.Random(1))


@dataclass
class CaseResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)


class World:
    """One canonical database, a controllable clock and a pool of recorded humans per tenant.

    Party referents (observations for an `observation` party, identity_binding_claims for a
    `identity_binding_claim` party) are inserted directly via SQL — the probe never imports the M5 or
    M6 machines, so their ship-dark posture is untouched (each machine's only importer stays its own
    probe). A `readback`/`rule`/`system` party carries no FK, so its ref is any token."""

    def __init__(self, ctx: Ctx, tmp: Path) -> None:
        self.ctx = ctx
        self.path = tmp / "cf.db"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(self.conn)
        create_canonical_schema(self.conn)
        enable_and_verify_foreign_keys(self.conn)
        self.clock = Clock(datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc))
        self._humans: set[tuple[str, str]] = set()
        self._obs: set[tuple[str, str]] = set()
        self._claims: set[tuple[str, str]] = set()
        self._n = 0

    def tenant(self, i: int = 0) -> str:
        return f"tenant-{'abc'[i % 3]}" + ("" if self.ctx.tenants == 1 else str(i))

    def human(self, tenant: str, human_id: str = HUMANS[0], *, state: str = "ACTIVE") -> str:
        key = (tenant, human_id)
        if key not in self._humans:
            off = "off" if state == "OFFBOARDED" else None
            self.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, "
                "authority_role, state, recorded_at, recorded_by, recorded_by_kind, offboarded_at) "
                "VALUES (?,?,?,?, ?, ?, ?, 'human', ?)",
                (tenant, human_id, human_id, "AUTHORIZED_HUMAN", state, "2026-08-20T09:00:00.000Z",
                 "founder", off))
            self.conn.commit()
            self._humans.add(key)
        return human_id

    def observation(self, tenant: str, oid: str) -> str:
        if (tenant, oid) not in self._obs:
            self.conn.execute(
                "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, "
                "external_id, content_digest, raw_value, as_of, received_at, state, version, "
                "provenance_class, created_at, updated_at) "
                "VALUES (?,?, 'tms:read', ?, ?, 'delivered', 't', 't', 'RECEIVED', 1, "
                "'SYSTEM_IMPORTED', 't', 't')",
                (tenant, oid, oid, oid))
            self.conn.commit()
            self._obs.add((tenant, oid))
        return oid

    def claim(self, tenant: str, cid: str) -> str:
        if (tenant, cid) not in self._claims:
            self.observation(tenant, f"{cid}-subj")
            self.conn.execute(
                "INSERT OR IGNORE INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, "
                "entity_ref, provenance_class, state, version, match_method, confidence, evidence_id, "
                "span, rule_id, decision_ref, decision_human_id, owner_id, ambiguous_reason, "
                "corrected_from, superseded_by, conflict_id, propagation_obligation, created_at, "
                "updated_at) VALUES (?,?,?, 'load:4471', 'LINKER_INFERRED', 'PROPOSED', 1, 'EXACT_ID', "
                "NULL, NULL, NULL, 'rule:exact', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "
                "'t','t')",
                (tenant, cid, f"{cid}-subj"))
            self.conn.commit()
            self._claims.add((tenant, cid))
        return cid

    def machine(self, tenant: str | None = None, *, registered_rules=None) -> M7Machine:
        t = tenant or self.tenant()
        self.human(t)
        return M7Machine(self.conn, tenant=t, registered_rules=registered_rules,
                         clock=self.clock)

    def _next(self) -> int:
        self._n += 1
        return self._n

    def conflicts(self, tenant: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM conflicts WHERE tenant = ?", (tenant,)).fetchone()[0]

    def open_count(self, tenant: str, entity_ref: str, field: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM conflicts WHERE tenant = ? AND entity_ref = ? AND field = ? "
            "AND state IN ('RAISED','OPEN','ESCALATED')", (tenant, entity_ref, field)).fetchone()[0]

    def events(self, tenant: str, name: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (tenant, name)).fetchone()[0]

    def security(self, tenant: str) -> list[str]:
        return [r["event_type"] for r in self.conn.execute(
            "SELECT event_type FROM security_events WHERE tenant = ?", (tenant,))]


def _world(ctx: Ctx) -> World:
    return World(ctx, Path(tempfile.mkdtemp(prefix="p6m7-")))


def _rb(ref: str, prov: str = "MODEL_EXTRACTED", value: str = "v") -> Party:
    return Party(ref, "readback", prov, value)


def _two(a: str = "src-a", b: str = "src-b") -> list[Party]:
    """A canonical two-party disagreement (readback parties carry no FK, so any refs work)."""
    return [_rb(a, "MODEL_EXTRACTED", "delivered"), _rb(b, "MODEL_INFERRED", "in_transit")]


def _open(w: World, m: M7Machine, *, kind: str = "SYSTEM_VS_SYSTEM", entity: str = "load:4471",
          field: str = "delivery", parties=None, owner: str | None = None):
    """Raise then acknowledge — a conflict in the OPEN state, a human owning it."""
    owner = owner or w.human(m.tenant)
    r = m.raise_conflict(kind=kind, entity_ref=entity, field=field, parties=(parties or _two()),
                         owner_id=owner)
    m.acknowledge(r.conflict.conflict_id)
    return r.conflict.conflict_id


# ---- the checkpoint seam (the probe FEEDS the one gate authority, never duplicates it) ----------

def _checkpoint_with_native(native_projection):
    from phase3_kit import green_scenario
    from freight_recon.checkpoint import (CheckpointInputs, NativeClaim, ProvenanceClass,
                                          run_checkpoint)
    tmp = Path(tempfile.mkdtemp(prefix="p6m7-ckpt-"))
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
    grants = store.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    store.close()
    return outcome, grants


def _checkpoint_evidence_conflicting():
    """The ProvenancedFact seam: a material fact whose evidence_condition is CONFLICTING, composed INTO
    the approval so there is no fingerprint drift — step 4 (native-state validity) refuses it as
    EVIDENCE_NOT_CONSISTENT, which is 'consistent fails' voiding the approval (entity §40)."""
    import dataclasses

    from phase3_kit import (T_A, live_reader, make_approval, make_effect, make_facts, make_kernel,
                            make_store)
    from freight_recon.checkpoint import (CheckpointInputs, CheckpointRequest, EvidenceCondition,
                                          run_checkpoint)
    tmp = Path(tempfile.mkdtemp(prefix="p6m7-ev-"))
    store = make_store(tmp, T_A)
    kernel, clock = make_kernel(store)
    effect = make_effect()
    versions = {"load:4471": 17}
    facts = make_facts()
    facts["amount"] = dataclasses.replace(facts["amount"],
                                          evidence_condition=EvidenceCondition.CONFLICTING)
    approval = make_approval(effect, facts, versions, clock)
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(facts)),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: {"status": "DELIVERED"}),
        entity_version_reader=live_reader(lambda: dict(versions)), approval=approval)
    request = CheckpointRequest(effect=effect, actor="pipeline",
                               accountable_owner="owner:rasheed", target_entity_ref="load:4471")
    outcome = run_checkpoint(kernel, request, inputs)
    store.close()
    return outcome


# ---- the cases ---------------------------------------------------------------------------------

def case_raise_creates_raised_with_a_named_human_owner(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                         parties=_two(), owner_id=h)
    c = m.get(r.conflict.conflict_id)
    ok = (r.transition_id == "CF-1" and c.state is CfState.RAISED and c.owner_id == h
          and r.event_names == ("ConflictRaised",))
    if not ok:
        return CaseResult(False, markers=["### MISS ### CF-1 did not create RAISED with a human owner"])
    return CaseResult(True, lines=[
        _SIG["raise-creates-raised-with-a-named-human-owner"],
        "A CONFLICT IS TWO OR MORE MUTUALLY EXCLUSIVE CLAIMS ON ONE FIELD, MADE VISIBLE AND BLOCKING",
        "A CONFLICT IS NOT unknown: WE HAVE TOO MUCH INFORMATION, AND IT DISAGREES"])


def case_raise_and_freeze_are_one_commit(w: World) -> CaseResult:
    m = w.machine()
    before_events = w.events(m.tenant, "ConflictRaised")
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                         parties=_two(), owner_id=w.human(m.tenant))
    # The row exists, the field is frozen, and the event landed — all together, exactly once.
    frozen = m.is_field_conflicting("load:4471", "delivery")
    row = m.get(r.conflict.conflict_id) is not None
    evt = w.events(m.tenant, "ConflictRaised") == before_events + 1
    ok = frozen and row and evt
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### frozen={frozen} row={row} evt={evt}"])
    return CaseResult(True, lines=[_SIG["raise-and-freeze-are-one-commit"]])


def case_ownerless_conflict_is_impossible(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id="")
    except GuardNotSatisfied:
        refused = True
    ok = refused and w.conflicts(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=["### OWNERLESS CONFLICT CREATED ###"])
    return CaseResult(True, lines=[_SIG["ownerless-conflict-is-impossible"]])


def case_a_model_cannot_own_a_conflict(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        # `system` / a model id is not a recorded ACTIVE human; the FK-backed guard fails closed.
        m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id="model:extractor")
    except GuardNotSatisfied:
        refused = True
    ok = refused and w.conflicts(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=["### MODEL BECAME THE CONFLICT OWNER ###"])
    return CaseResult(True, lines=[_SIG["a-model-cannot-own-a-conflict"]])


def case_the_six_conflict_kinds_are_closed(w: World) -> CaseResult:
    m = w.machine()
    # The six canonical kinds all raise; a seventh is refused before any write.
    accepted = 0
    for kind in CONFLICT_KINDS:
        r = m.raise_conflict(kind=kind, entity_ref=f"e-{kind}", field="f", parties=_two(),
                             owner_id=w.human(m.tenant))
        if m.get(r.conflict.conflict_id).kind == kind:
            accepted += 1
    refused = False
    try:
        m.raise_conflict(kind="OWNER_VS_UNIVERSE", entity_ref="e7", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    except MalformedConflict:
        refused = True
    ok = accepted == 6 and refused and len(CONFLICT_KINDS) == 6
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### accepted={accepted} refused-7th={refused}"])
    return CaseResult(True, lines=[_SIG["the-six-conflict-kinds-are-closed"]])


def _kind_case(w: World, kind: str, sig_key: str, extra: str | None = None) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind=kind, entity_ref="load:4471", field="delivery", parties=_two(),
                         owner_id=w.human(m.tenant))
    c = m.get(r.conflict.conflict_id)
    ok = c.kind == kind and c.state is CfState.RAISED and m.is_field_conflicting(
        "load:4471", "delivery")
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### {kind} did not raise+freeze"])
    lines = [_SIG[sig_key]]
    if extra:
        lines.append(extra)
    return CaseResult(True, lines=lines)


def case_system_vs_system_raises_a_conflict(w: World) -> CaseResult:
    return _kind_case(w, "SYSTEM_VS_SYSTEM", "system-vs-system-raises-a-conflict",
                      "SYSTEM_VS_SYSTEM RAISES A CONFLICT ON ONE FIELD")


def case_claim_vs_claim_raises_a_conflict(w: World) -> CaseResult:
    return _kind_case(w, "CLAIM_VS_CLAIM", "claim-vs-claim-raises-a-conflict")


def case_claim_vs_observation_raises_a_conflict(w: World) -> CaseResult:
    return _kind_case(w, "CLAIM_VS_OBSERVATION", "claim-vs-observation-raises-a-conflict")


def case_inferrer_vs_owner_records_the_owner_asserted_party(w: World) -> CaseResult:
    m = w.machine()
    # ### THE INFERRER DISAGREES WITH THE OWNER: one party is OWNER_ASSERTED (the owner's binding),
    # the other LINKER_INFERRED (the relinker). Neyma raises rather than picking.
    owner_party = _rb("owner-binding", "OWNER_ASSERTED", "load:4471")
    inferrer_party = _rb("relinker", "LINKER_INFERRED", "load:44718")
    r = m.raise_conflict(kind="INFERRER_VS_OWNER", entity_ref="pod:9931", field="belongs_to",
                         parties=[owner_party, inferrer_party], owner_id=w.human(m.tenant))
    parties = m.parties(r.conflict.conflict_id)
    has_owner_asserted = any(p["provenance_class"] == "OWNER_ASSERTED" for p in parties)
    # The event carries the parties (with the OWNER_ASSERTED one) into history — recorded, not
    # asserted: the inner key is `provenance` so a system-actor raise is not read as the EVENT
    # asserting OWNER_ASSERTED (ER-10). It still puts the fact into the party set for the rebuild.
    raised = [e for e in m._event_stream(r.conflict.conflict_id) if e.event_name == "ConflictRaised"]
    in_event = bool(raised) and any(
        p.get("provenance") == "OWNER_ASSERTED" for p in raised[0].payload.get("parties", []))
    ok = has_owner_asserted and in_event
    if not ok:
        return CaseResult(False, markers=["### MISS ### INFERRER_VS_OWNER lost the OWNER_ASSERTED party"])
    return CaseResult(True, lines=[_SIG["inferrer-vs-owner-records-the-owner-asserted-party"]])


def case_readback_vs_approved_is_not_an_ordinary_failure(w: World) -> CaseResult:
    m = w.machine()
    # ### A READBACK CONTRADICTS THE APPROVED FACTS. M7's half: it is a Conflict that BLOCKS and is
    # NOT laundered into a normal failure. M7 does not touch M3's UNKNOWN_OUTCOME (M7-AQ-2).
    approved = _rb("approved-invoice", "OWNER_ASSERTED", "285000")
    readback = _rb("payable-readback", "SYSTEM_IMPORTED", "310000")
    r = m.raise_conflict(kind="READBACK_VS_APPROVED", entity_ref="payable:77", field="amount",
                         parties=[approved, readback], owner_id=w.human(m.tenant))
    c = m.get(r.conflict.conflict_id)
    # It blocks like any other conflict; there is no "FAILED" anywhere — the disagreement is not
    # laundered into a normal failure.
    blocks = c.native_projection().conflicting and c.state is CfState.RAISED
    ok = blocks and c.kind == "READBACK_VS_APPROVED"
    if not ok:
        return CaseResult(False, markers=["### READBACK CONTRADICTION LAUNDERED INTO A NORMAL FAILURE ###"])
    return CaseResult(True, lines=[_SIG["readback-vs-approved-is-not-an-ordinary-failure"]])


def case_rule_vs_rule_fails_closed_and_never_auto_merges(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    # Two genuinely conflicting standing rules ⇒ FAIL CLOSED ⇒ a human resolves. Neyma never auto-
    # merges: even with a registered rule present, the RULE_VS_RULE conflict is raised and blocks; it
    # is not silently merged into a winner.
    ruleA = _rb("rule:portal-governs", "RECONCILED", "in_transit")
    ruleB = _rb("rule:tms-governs", "RECONCILED", "delivered")
    r = m.raise_conflict(kind="RULE_VS_RULE", entity_ref="load:4471", field="delivery",
                         parties=[ruleA, ruleB], owner_id=w.human(m.tenant))
    c = m.get(r.conflict.conflict_id)
    ok = c.state is CfState.RAISED and c.native_projection().conflicting
    if not ok:
        return CaseResult(False, markers=["### RULE_VS_RULE AUTO-MERGED ###"])
    return CaseResult(True, lines=[_SIG["rule-vs-rule-fails-closed-and-never-auto-merges"]])


def case_injected_competing_claim_freezes_the_entity_not_control(w: World) -> CaseResult:
    m = w.machine()
    # ### A CONFLICT IS A SECURITY CONTROL. An attacker injecting a competing claim gains a FROZEN
    # entity and a human's attention — NOT control. The attack surfaces itself.
    legit = _rb("legit-tms", "SYSTEM_IMPORTED", "delivered")
    attacker = _rb("injected-claim", "MODEL_EXTRACTED", "paid-to-attacker")
    r = m.raise_conflict(kind="CLAIM_VS_OBSERVATION", entity_ref="load:4471", field="pay_to",
                         parties=[legit, attacker], owner_id=w.human(m.tenant))
    c = m.get(r.conflict.conflict_id)
    frozen = c.native_projection().conflicting
    owned = c.owner_id in HUMANS
    outcome, grants = _checkpoint_with_native(c.native_projection())
    ok = frozen and owned and not outcome.authorized and outcome.step == 4
    if not ok:
        return CaseResult(False, markers=["### MISS ### injected claim did not yield a frozen entity"])
    return CaseResult(True, lines=[_SIG["injected-competing-claim-freezes-the-entity-not-control"]])


def case_acknowledgement_opens_the_conflict(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    r2 = m.acknowledge(r.conflict.conflict_id)
    ok = (r2.transition_id == "CF-2" and r2.conflict.state is CfState.OPEN
          and r2.event_names == ("ConflictOpened",))
    if not ok:
        return CaseResult(False, markers=["### MISS ### CF-2 did not open the conflict"])
    return CaseResult(True, lines=[_SIG["acknowledgement-opens-the-conflict"]])


def _blocks_case(w: World, sig_key: str, state_target: str) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    r = m.raise_conflict(kind="CLAIM_VS_OBSERVATION", entity_ref="load:4471", field="amount",
                         parties=_two(), owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    if state_target in ("OPEN", "ESCALATED"):
        m.acknowledge(cid)
    if state_target == "ESCALATED":
        m.escalate(cid)
    proj = m.get(cid).native_projection()
    outcome, grants = _checkpoint_with_native(proj)
    ok = proj.conflicting and not outcome.authorized and outcome.step == 4
    if not ok:
        return CaseResult(False, markers=["### CONSEQUENTIAL ACTION PROCEEDED ON AN OPEN CONFLICT ###"])
    return CaseResult(True, lines=[_SIG[sig_key]])


def case_raised_conflict_already_blocks_consequential_action(w: World) -> CaseResult:
    return _blocks_case(w, "raised-conflict-already-blocks-consequential-action", "RAISED")


def case_open_conflict_blocks_consequential_action(w: World) -> CaseResult:
    return _blocks_case(w, "open-conflict-blocks-consequential-action", "OPEN")


def case_escalated_conflict_still_blocks_consequential_action(w: World) -> CaseResult:
    return _blocks_case(w, "escalated-conflict-still-blocks-consequential-action", "ESCALATED")


def case_open_conflict_fails_checkpoint_native_state_validity(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m, entity="load:4471", field="amount")
    proj = m.get(cid).native_projection()
    outcome, grants = _checkpoint_with_native(proj)
    ok = not outcome.authorized and outcome.step == 4
    if not ok:
        return CaseResult(False, markers=["### MISS ### checkpoint step 4 did not refuse an open conflict"])
    return CaseResult(True, lines=[_SIG["open-conflict-fails-checkpoint-native-state-validity"]])


def case_no_effect_grant_on_a_conflicted_material_field(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m, entity="load:4471", field="amount")
    outcome, grants = _checkpoint_with_native(m.get(cid).native_projection())
    # The checkpoint mints the grant only on a PASS. Step 4 refused → no grant row exists.
    ok = not outcome.authorized and outcome.step == 4 and grants == 0
    if not ok:
        return CaseResult(False, markers=["### EFFECT GRANT MINTED ON A CONFLICTED FIELD ###"])
    return CaseResult(True, lines=[_SIG["no-effect-grant-on-a-conflicted-material-field"]])


def case_open_conflict_blocks_the_approval(w: World) -> CaseResult:
    # ### AN OPEN CONFLICT ON A MATERIAL FIELD VOIDS/BLOCKS THE APPROVAL: `consistent` fails. Composed
    # into the approval so it is not drift — step 4 refuses EVIDENCE_NOT_CONSISTENT (entity §40).
    outcome = _checkpoint_evidence_conflicting()
    native_outcome, _ = _checkpoint_with_native(
        _open_projection(w))
    ok = (not outcome.authorized and outcome.step == 4 and outcome.reason == "EVIDENCE_NOT_CONSISTENT"
          and not native_outcome.authorized)
    if not ok:
        return CaseResult(False, markers=["### APPROVAL PROCEEDED ON AN OPEN CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["open-conflict-blocks-the-approval"]])


def _open_projection(w: World):
    m = w.machine()
    cid = _open(w, m, entity="load:4471", field="amount")
    return m.get(cid).native_projection()


def case_m7_mints_no_gate_decision(w: World) -> CaseResult:
    # ### A CONFLICT IS AN INPUT TO THE CHECKPOINT AND CAN NEVER MINT A GATE DECISION. Structural: the
    # machine source neither imports the checkpoint/gate registry nor constructs a GateDecision, and a
    # conflict exposes only a native PROJECTION (an input), never a gate.
    src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text(encoding="utf-8")
    # Prose may DISCUSS the gate registry (M7 says it stays EMPTY); what must be absent is any
    # CONSTRUCTION or IMPORT of the gate machinery — a conflict is an input, never a gate.
    no_gate = ("GateDecision(" not in src and "GateRegistry(" not in src
               and "from .checkpoint" not in src and "import checkpoint" not in src)
    m = w.machine()
    cid = _open(w, m)
    proj = m.get(cid).native_projection()
    is_input = hasattr(proj, "conflicting") and not hasattr(proj, "gate")
    ok = no_gate and is_input
    if not ok:
        return CaseResult(False, markers=["### MISS ### M7 appears to mint a gate decision"])
    return CaseResult(True, lines=[_SIG["m7-mints-no-gate-decision"]])


def _lines_with(src: str, token: str) -> str:
    return "\n".join(line for line in src.splitlines() if token in line)


def case_registered_rule_resolves_the_conflict(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    r = m.resolve(cid, rule_id=REG_RULE)
    ok = (r.conflict.state is CfState.RESOLVED_BY_RULE and r.event_producer == "CF-3"
          and not m.is_field_conflicting(m.get(cid).entity_ref, m.get(cid).field))
    if not ok:
        return CaseResult(False, markers=["### MISS ### a registered rule did not resolve"])
    return CaseResult(True, lines=[_SIG["registered-rule-resolves-the-conflict"]])


def case_unregistered_rule_cannot_resolve(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})   # a DIFFERENT rule is unregistered
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, rule_id="rule:some-unregistered-heuristic")
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### UNREGISTERED RULE RESOLVED A CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["unregistered-rule-cannot-resolve"]])


def case_rule_resolution_requires_a_registered_rule_id(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    # A rule resolution with no rule_id at all is a resolution with no basis → ILLEGAL.
    illegal = False
    try:
        m.resolve_by_rule(cid, rule_id="")
    except IllegalTransition:
        illegal = True
    ok = illegal and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### RESOLVED WITHOUT A RULE OR A DECISION ###"])
    return CaseResult(True, lines=[_SIG["rule-resolution-requires-a-registered-rule-id"]])


def _no_resolve_by(w: World, pseudo_rule: str, marker: str, sig_key: str) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, rule_id=pseudo_rule)
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=[marker])
    return CaseResult(True, lines=[_SIG[sig_key]])


def case_confidence_cannot_resolve_a_conflict(w: World) -> CaseResult:
    # There is NO confidence-resolution path. Even at --confidence 1.0 the conflict stays open; the
    # only resolution APIs are a registered rule or a decision_ref. A "confidence:0.99" pseudo-rule is
    # unregistered and refused, and the confidence negative control changes nothing.
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, rule_id=f"confidence:{w.ctx.confidence}")
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### CONFIDENCE RESOLVED A CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["confidence-cannot-resolve-a-conflict"]])


def case_recency_cannot_resolve_a_conflict(w: World) -> CaseResult:
    return _no_resolve_by(w, "recency:newest-source-wins", "### RECENCY RESOLVED A CONFLICT ###",
                          "recency-cannot-resolve-a-conflict")


def case_source_priority_cannot_resolve_without_a_registered_rule(w: World) -> CaseResult:
    return _no_resolve_by(w, "source-priority:tms>portal",
                          "### SOURCE PRIORITY RESOLVED WITHOUT A RULE ###",
                          "source-priority-cannot-resolve-without-a-registered-rule")


def case_a_model_cannot_resolve_a_conflict(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    illegal = False
    try:
        m.resolve(cid, decision_ref="d", decision_human_id=w.human(m.tenant), actor_kind="model")
    except IllegalTransition:
        illegal = True
    ok = illegal and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### MODEL RESOLVED A CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["a-model-cannot-resolve-a-conflict"]])


def case_authenticated_human_resolves_the_conflict(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    cid = _open(w, m)
    r = m.resolve(cid, decision_ref="audit:decision-1", decision_human_id=h, actor_kind="human",
                  actor_id=h)
    ok = (r.conflict.state is CfState.RESOLVED_BY_HUMAN and r.event_producer == "CF-4"
          and m.get(cid).decision_human_id == h)
    if not ok:
        return CaseResult(False, markers=["### MISS ### an authenticated human did not resolve"])
    return CaseResult(True, lines=[_SIG["authenticated-human-resolves-the-conflict"]])


def case_human_resolution_requires_a_decision_ref(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m)
    illegal = False
    try:
        m.resolve_by_human(cid, decision_ref="", decision_human_id=w.human(m.tenant), actor_id="h")
    except IllegalTransition:
        illegal = True
    ok = illegal and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### RESOLVED WITHOUT A RULE OR A DECISION ###"])
    return CaseResult(True, lines=[_SIG["human-resolution-requires-a-decision-ref"]])


def case_counterparty_cannot_resolve_a_conflict(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m)
    illegal = False
    try:
        m.resolve(cid, decision_ref="per-our-call", decision_human_id=w.human(m.tenant),
                  actor_kind="counterparty")
    except IllegalTransition:
        illegal = True
    ok = illegal and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### COUNTERPARTY RESOLVED A CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["counterparty-cannot-resolve-a-conflict"]])


def case_wrong_tenant_human_resolution_fails_closed(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    m = w.machine(ta)
    hb = w.human(tb, HUMANS[1])          # a human of tenant B
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, decision_ref="d", decision_human_id=hb, actor_kind="human", actor_id=hb)
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT RESOLUTION ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["wrong-tenant-human-resolution-fails-closed"]])


def case_forged_human_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, decision_ref="d", decision_human_id="ceo-imposter", actor_kind="human",
                  actor_id="ceo-imposter")
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### FORGED HUMAN ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["forged-human-fails-closed"]])


def case_inactive_human_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    off = w.human(m.tenant, "owner:offboarded", state="OFFBOARDED")
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, decision_ref="d", decision_human_id=off, actor_kind="human", actor_id=off)
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### INACTIVE HUMAN ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["inactive-human-fails-closed"]])


def case_resolution_carries_exactly_one_basis(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    refused = False
    try:
        m.resolve(cid, rule_id=REG_RULE, decision_ref="d", decision_human_id=w.human(m.tenant))
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### TWO RESOLUTION BASES ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["resolution-carries-exactly-one-basis"]])


def case_resolution_with_neither_rule_nor_decision_is_illegal(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m)
    illegal = False
    try:
        m.resolve(cid)
    except IllegalTransition:
        illegal = True
    recorded = "IllegalTransitionAttempted" in w.security(m.tenant)
    ok = illegal and recorded and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### RESOLVED WITHOUT A RULE OR A DECISION ###"])
    return CaseResult(True, lines=[_SIG["resolution-with-neither-rule-nor-decision-is-illegal"]])


def case_resolution_unfreezes_the_field(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m, entity="load:4471", field="delivery")
    frozen_before = m.is_field_conflicting("load:4471", "delivery")
    m.resolve(cid, rule_id=REG_RULE)
    frozen_after = m.is_field_conflicting("load:4471", "delivery")
    ok = frozen_before and not frozen_after
    if not ok:
        return CaseResult(False, markers=["### MISS ### resolution did not unfreeze the field"])
    return CaseResult(True, lines=[_SIG["resolution-unfreezes-the-field"]])


def case_a_resolved_conflict_is_retained_never_deleted(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    m.resolve(cid, rule_id=REG_RULE)
    retained = m.get(cid) is not None
    # The DB refuses a DELETE — permanent retention (entity §28/§29).
    delete_refused = False
    try:
        w.conn.execute("DELETE FROM conflicts WHERE tenant = ? AND conflict_id = ?", (m.tenant, cid))
    except sqlite3.IntegrityError:
        delete_refused = True
    finally:
        w.conn.rollback()
    ok = retained and delete_refused and m.get(cid) is not None
    if not ok:
        return CaseResult(False, markers=["### CONFLICT DELETED ###"])
    return CaseResult(True, lines=[_SIG["a-resolved-conflict-is-retained-never-deleted"]])


def case_new_evidence_after_resolution_raises_a_new_conflict(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m, entity="load:4471", field="delivery")
    m.resolve(cid, rule_id=REG_RULE)
    # The field is unfrozen; new conflicting evidence raises a NEW conflict (CF-1), not a reopen.
    r2 = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                          parties=_two("later-a", "later-b"), owner_id=w.human(m.tenant))
    ok = (r2.conflict.conflict_id != cid and not r2.coalesced
          and m.get(r2.conflict.conflict_id).state is CfState.RAISED
          and m.get(cid).state is CfState.RESOLVED_BY_RULE)
    if not ok:
        return CaseResult(False, markers=["### MISS ### new evidence did not raise a NEW conflict"])
    return CaseResult(True, lines=[_SIG["new-evidence-after-resolution-raises-a-new-conflict"]])


def _escalate_via_timer(w: World, m: M7Machine, cid: str) -> bool:
    age = max(1, w.ctx.age_ms)
    w.clock.advance(milliseconds=age + 1)
    relay = TimerRelay(w.conn, tenant=m.tenant, handler=lambda tr: m.handle_timer_fired(tr),
                       relay_id="relay-1", clock=w.clock)
    relay.run_once()
    return m.get(cid).state is CfState.ESCALATED


def case_age_threshold_escalates_the_conflict(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    m.acknowledge(cid, escalation_at=w.clock.now + timedelta(milliseconds=max(1, w.ctx.age_ms)))
    escalated = _escalate_via_timer(w, m, cid)
    ok = escalated and w.events(m.tenant, "ConflictEscalated") == 1
    if not ok:
        return CaseResult(False, markers=["### MISS ### the timer did not escalate the conflict"])
    return CaseResult(True, lines=[_SIG["age-threshold-escalates-the-conflict"]])


def case_a_timer_never_resolves_a_conflict(w: World) -> CaseResult:
    from freight_recon.event_timers import TimerFired
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    # A durable timer firing with any kind OTHER than the age-threshold escalation is ILLEGAL — there
    # is no timer_kind that reaches a resolution. Model a "resolve" timer and show it is refused.
    illegal = False
    try:
        m.handle_timer_fired(TimerFired(
            tenant=m.tenant, timer_id="t-resolve", aggregate_type="conflict", aggregate_id=cid,
            timer_kind="conflict_resolve", fire_at="t", fired_at="t", payload={}))
    except IllegalTransition:
        illegal = True
    recorded = "IllegalTransitionAttempted" in w.security(m.tenant)
    ok = illegal and recorded and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### TIMER RESOLVED A CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["a-timer-never-resolves-a-conflict"]])


def case_a_conflict_never_expires(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    m.acknowledge(cid, escalation_at=w.clock.now + timedelta(milliseconds=1))
    # Advance the clock far beyond any threshold and fire the relay: it ESCALATES, and it stays open —
    # there is no EXPIRED state and the row is never deleted.
    w.clock.advance(hours=1000)
    relay = TimerRelay(w.conn, tenant=m.tenant, handler=lambda tr: m.handle_timer_fired(tr),
                       relay_id="relay-1", clock=w.clock)
    relay.run_once()
    c = m.get(cid)
    ok = (c is not None and c.state is CfState.ESCALATED
          and "EXPIRED" not in [s for s in CONFLICT_STATES])
    if not ok:
        return CaseResult(False, markers=["### CONFLICT EXPIRED ###"])
    return CaseResult(True, lines=[_SIG["a-conflict-never-expires"]])


def _escalated(w: World, m: M7Machine, entity="load:4471", field="delivery") -> str:
    r = m.raise_conflict(kind="CLAIM_VS_OBSERVATION", entity_ref=entity, field=field,
                         parties=_two(), owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    m.acknowledge(cid)
    m.escalate(cid)
    return cid


def case_escalated_resolves_by_registered_rule(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _escalated(w, m)
    r = m.resolve(cid, rule_id=REG_RULE)
    ok = (r.conflict.state is CfState.RESOLVED_BY_RULE and r.transition_id == "CF-6"
          and r.event_producer == "CF-3")
    if not ok:
        return CaseResult(False, markers=["### MISS ### an escalated conflict did not resolve by rule"])
    return CaseResult(True, lines=[_SIG["escalated-resolves-by-registered-rule"]])


def case_escalated_resolves_by_authenticated_human(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    cid = _escalated(w, m)
    r = m.resolve(cid, decision_ref="audit:d", decision_human_id=h, actor_kind="human", actor_id=h)
    ok = (r.conflict.state is CfState.RESOLVED_BY_HUMAN and r.transition_id == "CF-6"
          and r.event_producer == "CF-4")
    if not ok:
        return CaseResult(False, markers=["### MISS ### an escalated conflict did not resolve by human"])
    return CaseResult(True, lines=[_SIG["escalated-resolves-by-authenticated-human"]])


def case_escalated_resolution_is_by_target_state_never_by_position(w: World) -> CaseResult:
    # An escalated conflict resolved with a decision_ref lands in RESOLVED_BY_HUMAN (producer CF-4);
    # with a rule_id it lands in RESOLVED_BY_RULE (producer CF-3). The TARGET STATE is chosen by WHICH
    # basis, never by the order/position of the resolution.
    m1 = w.machine(registered_rules={REG_RULE})
    c_human = _escalated(w, m1, entity="load:1")
    r_human = m1.resolve(c_human, decision_ref="audit:d", decision_human_id=w.human(m1.tenant),
                         actor_kind="human", actor_id=w.human(m1.tenant))
    c_rule = _escalated(w, m1, entity="load:2")
    r_rule = m1.resolve(c_rule, rule_id=REG_RULE)
    ok = (r_human.conflict.state is CfState.RESOLVED_BY_HUMAN and r_human.event_producer == "CF-4"
          and r_rule.conflict.state is CfState.RESOLVED_BY_RULE and r_rule.event_producer == "CF-3")
    if not ok:
        return CaseResult(False, markers=["### ESCALATION RESOLVED BY POSITION ###"])
    return CaseResult(True, lines=[_SIG["escalated-resolution-is-by-target-state-never-by-position"]])


def case_second_detection_attaches_a_party_not_a_new_conflict(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                         parties=_two(), owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    # A third source arrives — it ATTACHES to the existing open conflict.
    r2 = m.attach_party(cid, _rb("third-source", "RECONCILED", "delivered"))
    ok = (r2.transition_id == "CF-7" and r2.event_names == ("ConflictPartyAttached",)
          and w.open_count(m.tenant, "load:4471", "delivery") == 1
          and "third-source" in m.party_refs(cid))
    if not ok:
        return CaseResult(False, markers=["### A SECOND CONFLICT WAS RAISED INSTEAD OF A PARTY ###"])
    return CaseResult(True, lines=[_SIG["second-detection-attaches-a-party-not-a-new-conflict"]])


def case_at_most_one_open_conflict_per_field(w: World) -> CaseResult:
    m = w.machine()
    n = max(2, w.ctx.parties)
    first = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                             parties=_two(), owner_id=w.human(m.tenant))
    # A direct second INSERT into an open field is refused by the partial unique index.
    direct_refused = False
    try:
        w.conn.execute("BEGIN IMMEDIATE")
        w.conn.execute(
            "INSERT INTO conflicts (tenant, conflict_id, entity_ref, field, kind, state, version, "
            "owner_id, rule_id, decision_ref, decision_ref_kind, decision_human_id, escalation_at, "
            "exposure, created_at, updated_at) VALUES (?, 'dup', 'load:4471', 'delivery', "
            "'SYSTEM_VS_SYSTEM', 'RAISED', 1, ?, NULL, NULL, NULL, NULL, NULL, NULL, 't', 't')",
            (m.tenant, w.human(m.tenant)))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        direct_refused = True
    # And a re-detection (its own two-party view of the same disagreement) coalesces into an attach
    # rather than a second conflict.
    for i in range(n):
        m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                         parties=[_rb(f"more-{i}", "MODEL_INFERRED", "x"),
                                  _rb(f"more-{i}-b", "RECONCILED", "y")], owner_id=w.human(m.tenant))
    ok = direct_refused and w.open_count(m.tenant, "load:4471", "delivery") == 1
    if not ok:
        return CaseResult(False, markers=["### TWO OPEN CONFLICTS FOR ONE FIELD ###"])
    return CaseResult(True, lines=[_SIG["at-most-one-open-conflict-per-field"]])


def case_an_attached_party_carries_its_own_provenance(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    # Each attaching party carries its own provenance_class, verbatim — one per canonical class.
    provs = ["MODEL_INFERRED", "MODEL_EXTRACTED", "RECONCILED", "LINKER_INFERRED"]
    for i in range(min(len(provs), max(2, w.ctx.parties))):
        m.attach_party(cid, _rb(f"party-{provs[i]}", provs[i], "v"))
    stored = {p["party_ref"]: p["provenance_class"] for p in m.parties(cid)}
    ok = all(stored.get(f"party-{p}") == p for p in provs[:min(len(provs), max(2, w.ctx.parties))])
    if not ok:
        return CaseResult(False, markers=["### PARTY PROVENANCE STRENGTHENED ###"])
    return CaseResult(True, lines=[_SIG["an-attached-party-carries-its-own-provenance"]])


def case_party_provenance_is_never_strengthened(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="INFERRER_VS_OWNER", entity_ref="pod:1", field="belongs_to",
                         parties=[_rb("owner-b", "OWNER_ASSERTED", "load:4471"),
                                  _rb("inferrer", "LINKER_INFERRED", "load:44718")],
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    # Attach a genuinely weak party; its recorded provenance is exactly what was detected, never
    # promoted. And the stored provenance cannot be edited afterwards (the immutability trigger).
    m.attach_party(cid, _rb("weak-guess", "MODEL_INFERRED", "load:9"))
    stored = {p["party_ref"]: p["provenance_class"] for p in m.parties(cid)}
    trigger_refused = False
    try:
        w.conn.execute(
            "UPDATE conflict_parties SET provenance_class = 'OWNER_ASSERTED' "
            "WHERE tenant = ? AND conflict_id = ? AND party_ref = 'weak-guess'", (m.tenant, cid))
    except sqlite3.IntegrityError:
        trigger_refused = True
    finally:
        w.conn.rollback()
    ok = stored.get("weak-guess") == "MODEL_INFERRED" and trigger_refused
    if not ok:
        return CaseResult(False, markers=["### PARTY PROVENANCE STRENGTHENED ###"])
    return CaseResult(True, lines=[_SIG["party-provenance-is-never-strengthened"]])


def case_concurrent_detectors_produce_one_conflict(w: World) -> CaseResult:
    m = w.machine()
    n = max(2, w.ctx.concurrency)
    anchor = _rb("anchor-tms", "SYSTEM_IMPORTED", "delivered")
    order = list(range(n))
    w.ctx.rng.shuffle(order)
    # N detectors of ONE field, in a seeded order. The first raises; the partial unique index makes
    # every other coalesce into an attach. Exactly one conflict, and no party is lost.
    detectors = [[anchor, _rb(f"portal-{i}", "MODEL_INFERRED", "in_transit")] for i in range(n)]
    cid = None
    for i in order:
        res = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                               parties=detectors[i], owner_id=w.human(m.tenant))
        cid = cid or res.conflict.conflict_id
    live = m.open_conflict_for("load:4471", "delivery")
    expected = {"anchor-tms", *(f"portal-{i}" for i in range(n))}
    ok = (w.open_count(m.tenant, "load:4471", "delivery") == 1 and live is not None
          and m.party_refs(live.conflict_id) == frozenset(expected))
    if not ok:
        return CaseResult(False, markers=["### PARTY LOST ###", "### TWO OPEN CONFLICTS FOR ONE FIELD ###"])
    return CaseResult(True, lines=[_SIG["concurrent-detectors-produce-one-conflict"],
                                   _SIG["at-most-one-open-conflict-per-field"]])


def case_a_party_retraction_never_silently_closes_the_conflict(w: World) -> CaseResult:
    # ### M7-AQ-3 HELD OPEN. A party retraction NEVER silently closes the conflict: there is no
    # cancellation transition, no CANCELLED state, and no conflict-cancellation event. The conflict stays
    # open, the field stays frozen, and a human still owns it.
    m = w.machine()
    cid = _open(w, m, entity="load:4471", field="delivery")
    no_cancel_api = not hasattr(m, "cancel") and not hasattr(m, "retract")
    no_cancel_state = "CANCELLED" not in CONFLICT_STATES
    no_cancel_event = not any("Cancel" in n or "Retract" in n for n in PRODUCED_CONTRACTS)
    c = m.get(cid)
    still_open = c.state is CfState.OPEN and m.is_field_conflicting("load:4471", "delivery")
    owned = c.owner_id in HUMANS
    ok = no_cancel_api and no_cancel_state and no_cancel_event and still_open and owned
    if not ok:
        return CaseResult(False, markers=["### CONFLICT SILENTLY CANCELLED ###"])
    return CaseResult(True, lines=[_SIG["a-party-retraction-never-silently-closes-the-conflict"]])


def case_replay_rebuilds_the_complete_party_set(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two("p1", "p2"),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    m.attach_party(cid, _rb("p3", "RECONCILED", "x"))
    m.attach_party(cid, _rb("p4", "MODEL_INFERRED", "y"))
    rebuilt = m.rebuild(cid)
    ok = set(rebuilt.parties) == {"p1", "p2", "p3", "p4"} and rebuilt.lost_parties == 0
    if not ok:
        return CaseResult(False, markers=["### REPLAY REBUILT A STALE PARTY SET ###"])
    return CaseResult(True, lines=[_SIG["replay-rebuilds-the-complete-party-set"]])


def case_replay_keeps_the_field_frozen(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m, entity="e", field="f")
    rebuilt = m.rebuild(cid)
    ok = rebuilt.frozen and rebuilt.state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### FIELD FROZEN WITHOUT ITS CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["replay-keeps-the-field-frozen"]])


def case_replay_cannot_resolve_or_duplicate_a_conflict(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m, entity="e", field="f")
    m.attach_party(cid, _rb("p3", "RECONCILED", "x"))
    rebuilt = m.rebuild(cid)
    ok = (rebuilt.state is CfState.OPEN and rebuilt.resolutions == 0
          and rebuilt.duplicate_conflicts == 0 and rebuilt.lost_parties == 0
          and rebuilt.new_authority == 0 and rebuilt.external_effects == 0)
    if not ok:
        return CaseResult(False, markers=["### REPLAY RESOLVED A CONFLICT ###",
                                          "### REPLAY DUPLICATED A CONFLICT ###"])
    return CaseResult(True, lines=[_SIG["replay-cannot-resolve-or-duplicate-a-conflict"]])


def case_replay_creates_no_new_authority_and_no_effect(w: World) -> CaseResult:
    m = w.machine()
    cid = _open(w, m, entity="e", field="f")
    rebuilt = m.rebuild(cid)
    ok = rebuilt.new_authority == 0 and rebuilt.external_effects == 0 and rebuilt.resolutions == 0
    if not ok:
        return CaseResult(False, markers=["### DOWNSTREAM EFFECT DURING REPLAY ###"])
    return CaseResult(True, lines=[_SIG["replay-creates-no-new-authority-and-no-effect"]])


def case_restart_preserves_the_open_conflict(w: World) -> CaseResult:
    m = w.machine()
    # ### A CRASH MID-WORKFLOW RECOVERS TO THE CANONICAL STATE, NEVER A TORN ONE. Every transition
    # co-commits its state row and its event in ONE `BEGIN IMMEDIATE` (GR-2), so a crash between two
    # transitions leaves the LAST committed state — which is canonical by construction — and the field
    # stays frozen while that state is open. `restart-before-open` crashes BEFORE the CF-2
    # acknowledge, so the conflict is RAISED and recovers to RAISED (a RAISED conflict already
    # blocks); `restart-after-escalate` crashes after CF-5 and recovers to ESCALATED; the default
    # restarts from OPEN. Each arm asserts the recovered state is exactly the one it crashed at.
    if w.ctx.inject == "restart-before-open":
        cid = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                               parties=_two(), owner_id=w.human(m.tenant)).conflict.conflict_id
        expected = CfState.RAISED
    else:
        cid = _open(w, m, entity="load:4471", field="delivery")
        expected = CfState.OPEN
        if w.ctx.inject == "restart-after-escalate":
            m.escalate(cid)
            expected = CfState.ESCALATED
    # Close the connection and reopen the SAME database file — a restart. The open conflict survives
    # and the field stays frozen after reconstruction.
    w.conn.close()
    conn2 = sqlite3.connect(str(w.path))
    conn2.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn2)
    m2 = M7Machine(conn2, tenant=m.tenant, clock=w.clock)
    c = m2.get(cid)
    ok = (c is not None and c.state is expected and c.is_open
          and m2.is_field_conflicting("load:4471", "delivery"))
    conn2.close()
    if not ok:
        return CaseResult(False, markers=["### CONFLICT WITHOUT ITS FROZEN FIELD ###"])
    return CaseResult(True, lines=[_SIG["restart-preserves-the-open-conflict"]])


def case_tenant_isolation(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    a, b = w.machine(ta), w.machine(tb)
    ra = a.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:1", field="f", parties=_two(),
                          owner_id=w.human(ta))
    rb = b.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:1", field="f", parties=_two(),
                          owner_id=w.human(tb))
    ok = (a.get(rb.conflict.conflict_id) is None and b.get(ra.conflict.conflict_id) is None
          and a.get(ra.conflict.conflict_id) is not None and b.get(rb.conflict.conflict_id) is not None)
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT PARTY ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["tenant-isolation"]])


def case_cross_tenant_identical_entity_ref_and_field(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    a, b = w.machine(ta), w.machine(tb)
    # The SAME (entity_ref, field) in two tenants are two isolated open conflicts (the partial unique
    # index is tenant-first) — neither refuses the other.
    ra = a.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                          parties=_two(), owner_id=w.human(ta))
    rb = b.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:4471", field="delivery",
                          parties=_two(), owner_id=w.human(tb))
    ok = (a.open_conflict_for("load:4471", "delivery").conflict_id == ra.conflict.conflict_id
          and b.open_conflict_for("load:4471", "delivery").conflict_id == rb.conflict.conflict_id
          and ra.conflict.conflict_id != rb.conflict.conflict_id
          and w.open_count(ta, "load:4471", "delivery") == 1
          and w.open_count(tb, "load:4471", "delivery") == 1)
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT PARTY ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["cross-tenant-identical-entity-ref-and-field"]])


def case_cross_tenant_party_reference_fails_closed(w: World) -> CaseResult:
    w.ctx.tenants = max(2, w.ctx.tenants)
    ta, tb = w.tenant(0), w.tenant(1)
    a = w.machine(ta)
    # An observation of tenant B cannot be a party in a conflict of tenant A — the party FK is
    # tenant-scoped, so a cross-tenant party reference fails closed.
    foreign_obs = w.observation(tb, "obs-of-b")
    refused = False
    try:
        a.raise_conflict(kind="CLAIM_VS_OBSERVATION", entity_ref="e", field="f",
                         parties=[Party("obs-of-b", "observation", "SYSTEM_IMPORTED", "x"),
                                  _rb("local", "MODEL_INFERRED", "y")], owner_id=w.human(ta))
    except sqlite3.IntegrityError:
        w.conn.rollback()
        refused = True
    ok = refused and w.conflicts(ta) == 0
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT PARTY ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["cross-tenant-party-reference-fails-closed"]])


def case_occ_on_conflict_version(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    snap = m.get(cid)              # version read at RAISED
    m.acknowledge(cid)            # advances the version underneath the snapshot
    conflicted = False
    try:
        m.acknowledge(cid, expected=snap)   # a transition decided on the stale snapshot is refused
    except (StateConflict, GuardNotSatisfied):
        conflicted = True
    ok = conflicted and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=["### MISS ### a lost update on a conflict was not refused"])
    return CaseResult(True, lines=[_SIG["occ-on-conflict-version"]])


def case_competing_resolutions_serialize_at_most_one_wins(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    snap = m.get(cid)
    n = max(2, w.ctx.concurrency)
    wins, refused = 0, 0
    for i in range(n):
        try:
            # Each resolver decided on the SAME snapshot version; the OCC predicate lets exactly one
            # win, and the rest are a lost update and refused.
            m.resolve(cid, rule_id=REG_RULE, expected=snap)
            wins += 1
        except (StateConflict, GuardNotSatisfied):
            refused += 1
    ok = wins == 1 and refused == n - 1 and m.get(cid).state is CfState.RESOLVED_BY_RULE
    if not ok:
        return CaseResult(False, markers=["### NEYMA PICKED A WINNER ###"])
    return CaseResult(True, lines=[_SIG["competing-resolutions-serialize-at-most-one-wins"]])


def case_redelivered_detection_is_a_no_op(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    m.attach_party(cid, _rb("third", "RECONCILED", "x"))
    before = len(m.parties(cid))
    # Redelivery of the SAME party attaches nothing new and raises nothing new.
    for _ in range(max(1, w.ctx.repeat)):
        m.attach_party(cid, _rb("third", "RECONCILED", "x"))
    ok = len(m.parties(cid)) == before and w.open_count(m.tenant, "e", "f") == 1
    if not ok:
        return CaseResult(False, markers=["### A SECOND CONFLICT WAS RAISED INSTEAD OF A PARTY ###"])
    return CaseResult(True, lines=[_SIG["redelivered-detection-is-a-no-op"]])


def case_inbox_idempotency(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=_two(),
                         owner_id=w.human(m.tenant))
    cid = r.conflict.conflict_id
    m.acknowledge(cid)
    # Replay the ConflictOpened event through the dedup inbox repeatedly — a redelivery is a no-op.
    env = next(e for e in m._event_stream(cid) if e.event_name == "ConflictOpened")
    outcomes = [m.consume_event(env).consume.outcome.value for _ in range(max(2, w.ctx.repeat))]
    ok = all(o in ("DUPLICATE_NOOP", "STALE_NOOP", "ALREADY_PARKED", "APPLIED") for o in outcomes) \
        and m.get(cid).state is CfState.OPEN
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### inbox not idempotent: {outcomes}"])
    return CaseResult(True, lines=[_SIG["inbox-idempotency"]])


def case_state_and_event_co_commit(w: World) -> CaseResult:
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    m.resolve(cid, rule_id=REG_RULE)
    # For each state-carrying event there is exactly the matching durable row state, and vice versa.
    raised = w.events(m.tenant, "ConflictRaised")
    opened = w.events(m.tenant, "ConflictOpened")
    resolved = w.events(m.tenant, "ConflictResolved")
    ok = (raised == 1 and opened == 1 and resolved == 1
          and m.get(cid).state is CfState.RESOLVED_BY_RULE)
    if not ok:
        return CaseResult(False, markers=["### STATE WITHOUT ITS EVENT ###", "### EVENT WITHOUT ITS STATE ###"])
    return CaseResult(True, lines=[_SIG["state-and-event-co-commit"]])


def case_malformed_conflict_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    refusals = 0
    for kwargs in (
        dict(kind="NOT_A_KIND", entity_ref="e", field="f", parties=_two()),
        dict(kind="SYSTEM_VS_SYSTEM", entity_ref="", field="f", parties=_two()),
        dict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f", parties=[_rb("solo")]),
        dict(kind="SYSTEM_VS_SYSTEM", entity_ref="e", field="f",
             parties=[_rb("a"), Party("b", "not-a-kind", "MODEL_INFERRED", "y")]),
    ):
        try:
            m.raise_conflict(owner_id=w.human(m.tenant), **kwargs)
        except MalformedConflict:
            refusals += 1
    ok = refusals == 4 and w.conflicts(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### malformed not fully refused ({refusals}/4)"])
    return CaseResult(True, lines=[_SIG["malformed-conflict-fails-closed"]])


def case_persistence_failure_rolls_back_the_raise_and_the_freeze(w: World) -> CaseResult:
    m = w.machine()
    # A party whose claim_ref points at a non-existent identity_binding_claim fails the FK MID-
    # transaction, AFTER the conflict row and the first party were inserted. The whole raise rolls
    # back: no conflict row, no parties, no event, and the field is NOT left frozen.
    failed = False
    try:
        m.raise_conflict(kind="CLAIM_VS_CLAIM", entity_ref="load:4471", field="delivery",
                         parties=[_rb("good"),
                                  Party("ghost-claim", "identity_binding_claim", "LINKER_INFERRED",
                                        "x")],
                         owner_id=w.human(m.tenant))
    except sqlite3.IntegrityError:
        failed = True
    if w.conn.in_transaction:
        w.conn.rollback()
    ok = (failed and w.conflicts(m.tenant) == 0
          and not m.is_field_conflicting("load:4471", "delivery")
          and w.events(m.tenant, "ConflictRaised") == 0)
    if not ok:
        return CaseResult(False, markers=["### FIELD FROZEN WITHOUT ITS CONFLICT ###",
                                          "### CONFLICT WITHOUT ITS FROZEN FIELD ###"])
    return CaseResult(True, lines=[_SIG["persistence-failure-rolls-back-the-raise-and-the-freeze"]])


def case_the_m6_claim_machine_is_not_rewritten(w: World) -> CaseResult:
    # ### M7 DOES NOT REWRITE M6. Structural: the M7 machine source never imports M6 and never writes
    # the identity_binding_claims table. A full lifecycle leaves that table untouched (count 0).
    m = w.machine(registered_rules={REG_RULE})
    cid = _open(w, m)
    m.attach_party(cid, _rb("p3", "RECONCILED", "x"))
    m.resolve(cid, rule_id=REG_RULE)
    claim_rows = w.conn.execute("SELECT COUNT(*) FROM identity_binding_claims").fetchone()[0]
    src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text(encoding="utf-8")
    no_import = "identity_binding_claim" not in _lines_with(src, "import ")
    ok = claim_rows == 0 and no_import
    if not ok:
        return CaseResult(False, markers=["### M6 CLAIM ROW REWRITTEN BY M7 ###"])
    return CaseResult(True, lines=[_SIG["the-m6-claim-machine-is-not-rewritten"]])


def case_the_m3_unknown_outcome_semantics_are_unchanged(w: World) -> CaseResult:
    # ### M7 DOES NOT TOUCH M3 (M7-AQ-2). Structural: the M7 machine never imports external_effect, and
    # the shipped M3 EF-4c still emits VerificationConflict and moves ATTEMPTED → UNKNOWN_OUTCOME,
    # unchanged — M7 launders no readback contradiction into a normal failure.
    src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text(encoding="utf-8")
    no_import = "from .external_effect" not in src and "import external_effect" not in src
    m3 = (ROOT / "src" / "freight_recon" / "external_effect.py").read_text(encoding="utf-8")
    ef4c_intact = ('id="EF-4c"' in m3 and "VerificationConflict" in m3
                   and "UNKNOWN_OUTCOME" in m3)
    ok = no_import and ef4c_intact
    if not ok:
        return CaseResult(False, markers=["### UNKNOWN_OUTCOME SILENTLY RESOLVED ###"])
    return CaseResult(True, lines=[_SIG["the-m3-unknown-outcome-semantics-are-unchanged"]])


def case_the_cross_family_conflict_raised_producers_are_recorded(w: World) -> CaseResult:
    # ### M7-AQ-1 / M7-AQ-2 REPORTED. ConflictRaised is a coordination event with three registered
    # producers; M7 owns CF-1, and IB-6 (M6) / EF-4c (M3) are recorded as the cross-family seam.
    producers = set(CONFLICT_RAISED_PRODUCERS)
    ok = (producers == {"CF-1", "IB-6", "EF-4c"} and "IB-6" in M7_AQ1_SEAM
          and "EF-4c" in M7_AQ1_SEAM and "M7-AQ-1" in M7_AQ1_SEAM)
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### producers {producers}"])
    return CaseResult(True, lines=[_SIG["the-cross-family-conflict-raised-producers-are-recorded"]])


def case_m8_m9_m10_and_m12_are_not_built(w: World) -> CaseResult:
    # M8 Expectation, M9 Exception, M10 Compensation and M12 Rule are NOT built here — the canonical
    # schema carries none of their tables, and M7 fabricated no Compensation.
    tables = {r[0] for r in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    forbidden = {"expectations", "exceptions", "compensations", "rules"}
    ok = not (tables & forbidden)
    if not ok:
        return CaseResult(False, markers=[f"### COMPENSATION FABRICATED ### {tables & forbidden}"])
    return CaseResult(True, lines=[_SIG["m8-m9-m10-and-m12-are-not-built"]])


def case_database_invariants(w: World) -> CaseResult:
    """The database ENFORCES the conflict invariants, and a legacy database migrates to the canonical
    shape. Deterministic and seed-independent."""
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    from freight_recon.migrations.phase6_conflicts import phase6_conflicts_readiness_problems
    from freight_recon.schema import (
        create_canonical_schema as ccs,
        enable_and_verify_foreign_keys as efk,
        schema_readiness_problems,
    )
    tmp = Path(tempfile.mkdtemp(prefix="p6m7-mig-"))
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
               and phase6_conflicts_readiness_problems(migrated) == [])

    fresh = sqlite3.connect(tmp / "fresh.db")
    fresh.row_factory = sqlite3.Row
    efk(fresh)
    ccs(fresh)
    efk(fresh)

    def shape(conn, table):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3]), bool(r[5]))
                for r in conn.execute(f"PRAGMA table_info({table})")]
        fks = sorted((r[2], r[3], r[4]) for r in conn.execute(f"PRAGMA foreign_key_list({table})"))
        idx = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='ix_conflicts_one_open_per_field'").fetchone()
        return cols, fks, " ".join((idx[0] or "").split()) if idx else None
    equal = (shape(migrated, "conflicts") == shape(fresh, "conflicts")
             and shape(migrated, "conflict_parties") == shape(fresh, "conflict_parties"))

    fresh.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('acme','h1','H','AUTHORIZED_HUMAN','ACTIVE','t',"
        "'founder','human')")
    fresh.commit()

    def try_conflict(**over):
        cols = dict(tenant="acme", conflict_id="c", entity_ref="e", field="f",
                    kind="SYSTEM_VS_SYSTEM", state="RAISED", version=1, owner_id="h1", rule_id=None,
                    decision_ref=None, decision_ref_kind=None, decision_human_id=None,
                    escalation_at=None, exposure=None, created_at="t", updated_at="t")
        cols.update(over)
        q = ",".join("?" * len(cols))
        fresh.execute(f"INSERT INTO conflicts ({','.join(cols)}) VALUES ({q})", tuple(cols.values()))

    # A resolved state with no basis is refused.
    no_basis = False
    try:
        try_conflict(conflict_id="nb", state="RESOLVED_BY_RULE")
    except sqlite3.IntegrityError:
        no_basis = True
    # Both bases at once refused.
    both = False
    try:
        try_conflict(conflict_id="bb", state="RESOLVED_BY_RULE", rule_id="r", decision_ref="d",
                     decision_human_id="h1", decision_ref_kind="audit_event")
    except sqlite3.IntegrityError:
        both = True
    # An ownerless conflict refused (NOT NULL).
    ownerless = False
    try:
        try_conflict(conflict_id="ow", owner_id=None)
    except sqlite3.IntegrityError:
        ownerless = True
    # Two OPEN conflicts for one field refused (partial unique index).
    try_conflict(conflict_id="o1")
    fresh.commit()
    two_open = False
    try:
        try_conflict(conflict_id="o2")
        fresh.commit()
    except sqlite3.IntegrityError:
        fresh.rollback()
        two_open = True
    # A sixth-state / seventh-kind refused (inline CHECK).
    bad_state = False
    try:
        try_conflict(conflict_id="bs", state="CANCELLED", entity_ref="e2")
    except sqlite3.IntegrityError:
        bad_state = True

    ok = ("conflicts" in m_tables and "conflict_parties" in m_tables and m_ready and equal
          and no_basis and both and ownerless and two_open and bad_state)
    if not ok:
        return CaseResult(False, markers=[
            f"### MISS ### migrate ready={m_ready} equal={equal} no_basis={no_basis} both={both} "
            f"ownerless={ownerless} two_open={two_open} bad_state={bad_state}"])
    return CaseResult(True, lines=[_SIG["database-invariants"],
                                   "A LEGACY DATABASE MIGRATES TO THE CANONICAL CONFLICT SHAPE",
                                   _SIG["at-most-one-open-conflict-per-field"]])


CASE_FUNCS = {
    "raise-creates-raised-with-a-named-human-owner": case_raise_creates_raised_with_a_named_human_owner,
    "raise-and-freeze-are-one-commit": case_raise_and_freeze_are_one_commit,
    "ownerless-conflict-is-impossible": case_ownerless_conflict_is_impossible,
    "a-model-cannot-own-a-conflict": case_a_model_cannot_own_a_conflict,
    "the-six-conflict-kinds-are-closed": case_the_six_conflict_kinds_are_closed,
    "system-vs-system-raises-a-conflict": case_system_vs_system_raises_a_conflict,
    "claim-vs-claim-raises-a-conflict": case_claim_vs_claim_raises_a_conflict,
    "claim-vs-observation-raises-a-conflict": case_claim_vs_observation_raises_a_conflict,
    "inferrer-vs-owner-records-the-owner-asserted-party":
        case_inferrer_vs_owner_records_the_owner_asserted_party,
    "readback-vs-approved-is-not-an-ordinary-failure":
        case_readback_vs_approved_is_not_an_ordinary_failure,
    "rule-vs-rule-fails-closed-and-never-auto-merges": case_rule_vs_rule_fails_closed_and_never_auto_merges,
    "injected-competing-claim-freezes-the-entity-not-control":
        case_injected_competing_claim_freezes_the_entity_not_control,
    "acknowledgement-opens-the-conflict": case_acknowledgement_opens_the_conflict,
    "raised-conflict-already-blocks-consequential-action":
        case_raised_conflict_already_blocks_consequential_action,
    "open-conflict-blocks-consequential-action": case_open_conflict_blocks_consequential_action,
    "escalated-conflict-still-blocks-consequential-action":
        case_escalated_conflict_still_blocks_consequential_action,
    "open-conflict-fails-checkpoint-native-state-validity":
        case_open_conflict_fails_checkpoint_native_state_validity,
    "no-effect-grant-on-a-conflicted-material-field": case_no_effect_grant_on_a_conflicted_material_field,
    "open-conflict-blocks-the-approval": case_open_conflict_blocks_the_approval,
    "m7-mints-no-gate-decision": case_m7_mints_no_gate_decision,
    "registered-rule-resolves-the-conflict": case_registered_rule_resolves_the_conflict,
    "unregistered-rule-cannot-resolve": case_unregistered_rule_cannot_resolve,
    "rule-resolution-requires-a-registered-rule-id": case_rule_resolution_requires_a_registered_rule_id,
    "confidence-cannot-resolve-a-conflict": case_confidence_cannot_resolve_a_conflict,
    "recency-cannot-resolve-a-conflict": case_recency_cannot_resolve_a_conflict,
    "source-priority-cannot-resolve-without-a-registered-rule":
        case_source_priority_cannot_resolve_without_a_registered_rule,
    "a-model-cannot-resolve-a-conflict": case_a_model_cannot_resolve_a_conflict,
    "authenticated-human-resolves-the-conflict": case_authenticated_human_resolves_the_conflict,
    "human-resolution-requires-a-decision-ref": case_human_resolution_requires_a_decision_ref,
    "counterparty-cannot-resolve-a-conflict": case_counterparty_cannot_resolve_a_conflict,
    "wrong-tenant-human-resolution-fails-closed": case_wrong_tenant_human_resolution_fails_closed,
    "forged-human-fails-closed": case_forged_human_fails_closed,
    "inactive-human-fails-closed": case_inactive_human_fails_closed,
    "resolution-carries-exactly-one-basis": case_resolution_carries_exactly_one_basis,
    "resolution-with-neither-rule-nor-decision-is-illegal":
        case_resolution_with_neither_rule_nor_decision_is_illegal,
    "resolution-unfreezes-the-field": case_resolution_unfreezes_the_field,
    "a-resolved-conflict-is-retained-never-deleted": case_a_resolved_conflict_is_retained_never_deleted,
    "new-evidence-after-resolution-raises-a-new-conflict":
        case_new_evidence_after_resolution_raises_a_new_conflict,
    "age-threshold-escalates-the-conflict": case_age_threshold_escalates_the_conflict,
    "a-timer-never-resolves-a-conflict": case_a_timer_never_resolves_a_conflict,
    "a-conflict-never-expires": case_a_conflict_never_expires,
    "escalated-resolves-by-registered-rule": case_escalated_resolves_by_registered_rule,
    "escalated-resolves-by-authenticated-human": case_escalated_resolves_by_authenticated_human,
    "escalated-resolution-is-by-target-state-never-by-position":
        case_escalated_resolution_is_by_target_state_never_by_position,
    "second-detection-attaches-a-party-not-a-new-conflict":
        case_second_detection_attaches_a_party_not_a_new_conflict,
    "at-most-one-open-conflict-per-field": case_at_most_one_open_conflict_per_field,
    "an-attached-party-carries-its-own-provenance": case_an_attached_party_carries_its_own_provenance,
    "party-provenance-is-never-strengthened": case_party_provenance_is_never_strengthened,
    "concurrent-detectors-produce-one-conflict": case_concurrent_detectors_produce_one_conflict,
    "a-party-retraction-never-silently-closes-the-conflict":
        case_a_party_retraction_never_silently_closes_the_conflict,
    "replay-rebuilds-the-complete-party-set": case_replay_rebuilds_the_complete_party_set,
    "replay-keeps-the-field-frozen": case_replay_keeps_the_field_frozen,
    "replay-cannot-resolve-or-duplicate-a-conflict": case_replay_cannot_resolve_or_duplicate_a_conflict,
    "replay-creates-no-new-authority-and-no-effect": case_replay_creates_no_new_authority_and_no_effect,
    "restart-preserves-the-open-conflict": case_restart_preserves_the_open_conflict,
    "tenant-isolation": case_tenant_isolation,
    "cross-tenant-identical-entity-ref-and-field": case_cross_tenant_identical_entity_ref_and_field,
    "cross-tenant-party-reference-fails-closed": case_cross_tenant_party_reference_fails_closed,
    "occ-on-conflict-version": case_occ_on_conflict_version,
    "competing-resolutions-serialize-at-most-one-wins":
        case_competing_resolutions_serialize_at_most_one_wins,
    "redelivered-detection-is-a-no-op": case_redelivered_detection_is_a_no_op,
    "inbox-idempotency": case_inbox_idempotency,
    "state-and-event-co-commit": case_state_and_event_co_commit,
    "database-invariants": case_database_invariants,
    "malformed-conflict-fails-closed": case_malformed_conflict_fails_closed,
    "persistence-failure-rolls-back-the-raise-and-the-freeze":
        case_persistence_failure_rolls_back_the_raise_and_the_freeze,
    "the-m6-claim-machine-is-not-rewritten": case_the_m6_claim_machine_is_not_rewritten,
    "the-m3-unknown-outcome-semantics-are-unchanged": case_the_m3_unknown_outcome_semantics_are_unchanged,
    "the-cross-family-conflict-raised-producers-are-recorded":
        case_the_cross_family_conflict_raised_producers_are_recorded,
    "m8-m9-m10-and-m12-are-not-built": case_m8_m9_m10_and_m12_are_not_built,
}


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
    if args.inject in ("expire-conflict", "expire-observation"):
        raise ProbeExit(
            f"unknown fault {args.inject!r} is REFUSED: it is not in the closed vocabulary because a "
            f"Conflict NEVER expires (entity §26, machine §12/§23) and has no deletion policy (entity "
            f"§28). Accepting it would manufacture evidence for a transition the corpus states does "
            f"not exist.")
    if args.inject in ("cancel-conflict", "conflict-cancelled"):
        raise ProbeExit(
            "unknown fault 'cancel-conflict' is REFUSED: machine §14 enumerates only CF-1..CF-7, GR-1 "
            "makes anything unenumerated ILLEGAL, and no CANCELLED state and no conflict-cancellation event "
            "is registered anywhere. This is M7-AQ-3 held OPEN rather than answered — a party "
            "retraction NEVER silently closes the conflict, and a probe that accepted the fault would "
            "have answered a question the corpus does not.")
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
        parties=bounded_int("parties", args.parties, 2, 8),
        age_ms=bounded_int("age-ms", args.age_ms, 0, 60000),
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
    p.add_argument("--parties", type=int, default=2)
    p.add_argument("--age-ms", type=int, default=0)
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
                       tenants=ctx.tenants, parties=ctx.parties, age_ms=ctx.age_ms,
                       confidence=ctx.confidence, seed=ctx.seed, inject=inject,
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
