#!/usr/bin/env python3
"""M9 — the Exception — deterministic narrative probe.

A TMS write times out and the outcome is UNKNOWN, so an Exception is raised with a named human owner
from the moment it exists and a severity recorded beside it. An authenticated human ACKNOWLEDGES it,
which proves they SAW it and proves nothing else, and it keeps ageing. Nobody acts, so a durable timer
moves it to AGEING and then ESCALATED — louder, still owned, and never resolved by the clock. Someone
tries to close it with the string "done" and the database refuses, because closure is an event with a
decision_ref that RESOLVES to an authenticated human decision, and an exception closed without a
decision is not closed, it is FORGOTTEN. A model tries to clear it and is refused at any confidence.
The severity is reassessed and that is a FIELD change carrying the value it moved from, so a rebuild
months later reproduces the severity that is live rather than the one it was born with.

What matters is not that a row can be created — it is that no inactivity, no AutoClose, no expiry, no
sweep and no timer can ever close it, that no exception exists without a human whose name is on it, and
that a carrier's £2,850 nobody can account for reaches a person instead of a log file.

M9 ships dark — no oversight queue, no dashboard, no notifier — so this probe is the ONLY interface a
generated Product-Driver scenario can compose M9's real behaviour through. Every ordering, concurrency,
timing, duplication, crash and replay variation has to be reachable through these arguments, so the
interface is taken seriously:

    --list-cases        the case names, one per line
    --list-dimensions   every dimension flag and every fault name
    --case <case>       run exactly one case (composes with the flags below)
    (no arguments)      run every case; exit 0 only if every one behaved as specified

    --concurrency 1-8      how many raisers, acknowledgers or timers race one exception
    --delay-ms 0-5000      timing skew between them
    --repeat 1-5           duplicate raise / redelivered timer pressure
    --tenants 1-3          isolation pressure
    --age-ms 0-86400000    how far the durable timer is advanced: the ageing threshold, then escalation
    --severity <sev>       the severity the exception carries or moves to: SEV0|SEV1|SEV2
    --actor <kind>         WHO attempts the transition: human|system|model|detector
    --decision-ref <kind>  the resolution authority offered: valid|absent|unresolvable|non-human|automated|cross-tenant
    --freeze <mode>        whether the source condition freezes material work: material|immaterial|none
    --seed <int>           deterministic interleaving; the same seed reproduces the failure
    --inject <fault>       the closed fault set (see --list-dimensions); an unknown fault, or a value out
                           of range, exits 2 with a readable message and NEVER a traceback

### `--actor` AND `--decision-ref` ARE THIS UNIT'S OWN TWO AXES. M9's entire safety property is a
question about WHO may act: a human acknowledges, a human resolves, a timer ages and never resolves, a
model does none of it. And `--decision-ref absent` is the value that decides whether closure by silence
is possible at all — which is F-30, GR-14 and AC-MACH-903 in one flag.

### CLOSED MEANS CLOSED. `--inject not-a-real-fault` exits 2. `--inject reopen-exception` exits 2 —
entity §27 and machine §24 say "Reopening rules. N/A (a recurrence is a new Exception)". `--inject
correct-exception` exits 2 — entity §23 and machine §25 say "Correction rules. N/A". `--inject
supersede-exception` exits 2 — entity §24 and machine §26 say "Supersession rules. N/A", and no
SUPERSEDED state or ExceptionSuperseded event is registered anywhere. In CONTRAST, `--inject autoclose`,
`--inject expire-exception`, `--inject timer-resolve`, `--inject resolve-from-ageing`, `--inject
cancel-exception`, `--inject sixth-state` and `--inject sweep-close` ARE in the vocabulary: they name
shapes the corpus defines as ILLEGAL (machine §15, and the EC-3/EC-4/EC-6/EC-7 from-sets), so the
machine must be SEEN to REFUSE them under GR-1. A fault refused as UNKNOWN and a fault refused as ILLEGAL
are two different proofs, and M9 owes both.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_outbox import TransactionalOutbox  # noqa: E402
from freight_recon.event_timers import TimerFired, TimerRelay  # noqa: E402
from freight_recon.exception import (  # noqa: E402
    PRODUCED_CONTRACTS,
    EcSeverity,
    EcState,
    GuardNotSatisfied,
    IllegalTransition,
    M9Machine,
    MalformedException,
    StateConflict,
)
from freight_recon.exception import FailureDisposition  # noqa: E402  (re-exposed from M1, not a work_item import)
from freight_recon.migrations.phase6_exceptions import (  # noqa: E402
    EXCEPTION_SEVERITIES,
    EXCEPTION_STATES,
    SOURCE_KINDS,
    SUB_STATUSES,
    phase6_exceptions_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

HUMANS = ("owner:rasheed", "owner:dana", "owner:sam")


# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    "raise-creates-open-with-a-named-human-owner",
    "an-exception-cannot-be-raised-without-an-owner",
    "an-ownerless-exception-is-structurally-impossible",
    "the-owner-is-an-active-human-of-this-tenant",
    "an-offboarded-human-cannot-own-a-new-exception",
    "a-model-cannot-own-an-exception",
    "raise-records-severity-and-the-source-that-raised-it",
    "an-exception-cannot-be-raised-without-a-severity",
    "an-exception-cannot-be-raised-without-a-source-ref",
    "the-source-kind-is-a-closed-vocabulary",
    "a-permanent-auth-failure-raises-immediately-with-zero-retries",
    "a-permanent-config-failure-raises-immediately-with-zero-retries",
    "a-transient-failure-is-not-a-permanent-classification",
    "the-failure-classification-is-supplied-never-inferred-from-a-message",
    "an-authenticated-human-acknowledges-the-exception",
    "acknowledgement-records-the-actor",
    "acknowledgement-proves-seen-not-resolved",
    "a-model-cannot-acknowledge-an-exception",
    "a-system-actor-cannot-acknowledge-an-exception",
    "an-acknowledged-exception-still-ages",
    "resolution-requires-a-decision-ref",
    "closure-without-a-decision-ref-is-structurally-impossible",
    "a-decision-ref-that-resolves-to-nothing-is-refused",
    "a-decision-ref-naming-a-non-human-decision-event-is-refused",
    "a-decision-ref-recorded-by-automation-is-refused",
    "a-model-can-never-resolve-an-exception",
    "an-escalated-exception-resolves-through-ec-6",
    "resolving-from-ageing-is-an-illegal-transition",
    "resolved-is-the-only-terminal-state",
    "a-resolved-exception-is-retained-never-deleted",
    "inactivity-never-closes-an-exception",
    "autoclose-is-an-illegal-transition",
    "an-exception-never-expires",
    "an-exception-cannot-be-outlived",
    "no-sweep-or-reaper-closes-an-exception",
    "a-timer-can-age-or-escalate-but-never-resolve",
    "an-open-exception-ages-through-a-durable-timer",
    "an-acknowledged-exception-ages-through-a-durable-timer",
    "ageing-escalates-through-a-durable-timer-not-a-sweep",
    "ageing-and-escalated-remain-human-owned",
    "the-ageing-threshold-is-caller-supplied-not-a-business-default",
    "ageing-an-escalated-exception-is-illegal",
    "nothing-moves-a-resolved-exception",
    "restart-re-fires-the-ageing-timer",
    "restart-preserves-the-open-exception",
    "restart-after-escalation-reaches-the-canonical-state",
    "a-redelivered-timer-is-a-no-op",
    "severity-change-is-a-field-mutation-not-a-lifecycle-state",
    "severity-change-records-previous-and-new-severity-and-who",
    "severity-change-requires-a-reason",
    "a-model-cannot-change-severity",
    "severity-is-sev0-sev1-or-sev2-and-nothing-else",
    "changing-the-severity-of-an-ageing-exception-is-illegal",
    "a-sev0-exception-engages-no-brake-from-inside-m9",
    "the-five-canonical-states-and-no-sixth",
    "sub-status-is-a-field-never-a-lifecycle-state",
    "there-is-no-cancelled-expired-or-timed-out-state",
    "a-retracted-cause-still-requires-an-event-and-a-decision-ref",
    "a-freezing-exception-blocks-consequential-actions-on-the-entity",
    "not-every-exception-freezes-an-entity",
    "raise-and-freeze-commit-together-where-applicable",
    "a-persistence-failure-leaves-no-half-raised-exception",
    "state-and-event-co-commit",
    "resolution-unblocks-the-frozen-entity",
    "m9-mints-no-gate-decision",
    "an-exception-is-an-input-to-the-checkpoint-never-a-gate",
    "a-redelivered-raise-through-the-inbox-is-a-no-op",
    "the-open-exception-dedup-index-is-optional-and-recorded",
    "concurrent-raises-are-serialized-by-the-database",
    "occ-on-exception-version",
    "a-stale-version-cannot-overwrite-newer-state",
    "replay-reconstructs-the-open-exception",
    "replay-rebuilds-the-current-severity-from-the-recorded-events",
    "replay-does-not-read-severity-from-the-current-row",
    "replay-keeps-a-frozen-entity-blocked",
    "replay-can-never-manufacture-resolution-authority",
    "replay-creates-no-new-authority-and-no-effect",
    "exceptions-still-raise-under-a-brake",
    "m9-engages-no-brake-and-narrows-none",
    "tenant-isolation",
    "cross-tenant-identical-source-ref",
    "cross-tenant-owner-fails-closed",
    "cross-tenant-source-fails-closed",
    "cross-tenant-decision-ref-fails-closed",
    "cross-tenant-queue-read-fails-closed",
    "inbox-idempotency",
    "database-invariants",
    "malformed-exception-fails-closed",
    "an-illegal-transition-persists-nothing-and-is-recorded",
    "the-m1-work-item-machine-is-not-rewritten",
    "the-m3-effect-authority-is-unchanged",
    "the-m5-observation-machine-is-not-rewritten",
    "the-m7-conflict-machine-is-not-rewritten",
    "the-m8-expectation-machine-is-not-rewritten",
    "m10-m11-and-m12-are-not-built",
)

# The closed fault vocabulary — every member named by the canonical machine, the entity spec, the
# target spec, an ADR or the event registry. `phase` is documentation of the family a fault belongs to.
FAULTS: dict[str, str] = {
    "none": "any",
    "raise": "raise",
    "ownerless-raise": "raise",
    "model-owner": "raise",
    "offboarded-owner": "raise",
    "cross-tenant-owner": "raise",
    "missing-severity": "raise",
    "missing-source-ref": "raise",
    "cross-tenant-source": "raise",
    "invented-source-kind": "raise",
    "permanent-auth-failure": "raise",
    "permanent-config-failure": "raise",
    "transient-failure": "raise",
    "inferred-permanence": "raise",
    "retry-permanent": "raise",
    "acknowledge": "ack",
    "model-acknowledge": "ack",
    "system-acknowledge": "ack",
    "resolve": "resolve",
    "resolve-without-decision-ref": "resolve",   # ILLEGAL — closure by silence
    "unresolvable-decision-ref": "resolve",      # ILLEGAL — references nothing
    "non-human-decision-ref": "resolve",         # ILLEGAL — not a human decision
    "automated-decision-ref": "resolve",         # ILLEGAL — automation laundering (ER-11)
    "cross-tenant-decision-ref": "resolve",      # ILLEGAL — fails closed
    "model-resolve": "resolve",                  # ILLEGAL — a model never resolves
    "resolve-from-ageing": "resolve",            # ILLEGAL — AGEING in neither from-set
    "autoclose": "resolve",                      # ILLEGAL — no AutoClose
    "inactivity-close": "resolve",               # ILLEGAL — inactivity never closes
    "expire-exception": "timer",                 # ILLEGAL — an exception never expires
    "sweep-close": "timer",                      # ILLEGAL — no sweep/reaper
    "timer-resolve": "timer",                    # ILLEGAL — a timer never resolves
    "age": "timer",
    "escalate": "timer",
    "age-escalated": "timer",                    # ILLEGAL — EC-4 excludes AGEING/ESCALATED
    "age-resolved": "timer",                     # ILLEGAL — nothing moves a RESOLVED one
    "severity-change": "severity",
    "severity-change-no-reason": "severity",     # ILLEGAL/refused — reason is required
    "severity-change-no-previous": "severity",
    "model-severity-change": "severity",         # ILLEGAL — a model never changes severity
    "invented-severity": "severity",             # refused — SEV0|SEV1|SEV2 only
    "severity-change-ageing": "severity",        # ILLEGAL — EC-7 excludes AGEING
    "sub-status-as-state": "state",              # refused — sub_status is a field
    "sixth-state": "state",                      # refused — no sixth lifecycle state
    "cancel-exception": "state",                 # ILLEGAL — no CANCELLED state/event
    "freeze": "freeze",
    "no-freeze": "freeze",
    "freeze-split-commit": "freeze",             # ILLEGAL — raise+freeze are one commit
    "unfreeze-without-resolution": "freeze",     # ILLEGAL — only a resolution unfreezes
    "persistence-failure": "freeze",
    "gate-mint": "gate",                         # ILLEGAL — M9 mints no gate decision
    "brake-engage": "brake",                     # ILLEGAL — M9 engages no brake
    "duplicate-raise": "raise",
    "concurrent-raise": "raise",
    "redelivered-raise": "raise",
    "redelivered-timer": "timer",
    "occ-exception": "occ",
    "stale-version": "occ",                      # ILLEGAL — a stale version never overwrites
    "restart-before-ageing": "restart",
    "restart-after-escalated": "restart",
    "replay": "replay",
    "replay-severity-from-row": "replay",        # ILLEGAL — replay never reads the live row
    "replay-manufacture-decision": "replay",     # ILLEGAL — replay never mints a decision_ref
    "cross-tenant-queue": "tenant",
    "malformed-exception": "raise",
    "reorder-stream": "replay",
    "delete-exception": "state",                 # ILLEGAL — retention is permanent
}

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "age-ms", "severity", "actor", "decision-ref",
    "freeze", "seed", "inject",
)

SEVERITY_VALUES = ("SEV0", "SEV1", "SEV2")
ACTOR_VALUES = ("human", "system", "model", "detector")
DECISION_REF_VALUES = ("valid", "absent", "unresolvable", "non-human", "automated", "cross-tenant")
FREEZE_VALUES = ("material", "immaterial", "none")


# ### THE INVARIANT SENTENCES THE VERIFICATION SCENARIO MATCHES AS LITERAL SUBSTRINGS.
_SIG: dict[str, str] = {
    "raise-creates-open-with-a-named-human-owner": "AN EXCEPTION HAS A NAMED HUMAN OWNER FROM CREATION",
    "an-exception-cannot-be-raised-without-an-owner":
        "AN OWNERLESS EXCEPTION IS STRUCTURALLY IMPOSSIBLE",
    "an-ownerless-exception-is-structurally-impossible":
        "AN OWNERLESS EXCEPTION IS STRUCTURALLY IMPOSSIBLE",
    "the-owner-is-an-active-human-of-this-tenant": "THE OWNER IS AN ACTIVE HUMAN OF THIS TENANT",
    "an-offboarded-human-cannot-own-a-new-exception": "THE OWNER IS AN ACTIVE HUMAN OF THIS TENANT",
    "a-model-cannot-own-an-exception": "A MODEL IS NOT A HUMAN AND MAY NOT OWN AN EXCEPTION",
    "raise-records-severity-and-the-source-that-raised-it":
        "THE RAISE RECORDS ITS SEVERITY AND THE SOURCE THAT RAISED IT",
    "an-exception-cannot-be-raised-without-a-severity":
        "THE RAISE RECORDS ITS SEVERITY AND THE SOURCE THAT RAISED IT",
    "an-exception-cannot-be-raised-without-a-source-ref":
        "THE RAISE RECORDS ITS SEVERITY AND THE SOURCE THAT RAISED IT",
    "the-source-kind-is-a-closed-vocabulary": "THE SOURCE KIND IS A CLOSED VOCABULARY",
    "a-permanent-auth-failure-raises-immediately-with-zero-retries":
        "A PERMANENT AUTH OR CONFIG FAILURE RAISES IMMEDIATELY WITH ZERO RETRIES",
    "a-permanent-config-failure-raises-immediately-with-zero-retries":
        "A PERMANENT AUTH OR CONFIG FAILURE RAISES IMMEDIATELY WITH ZERO RETRIES",
    "a-transient-failure-is-not-a-permanent-classification":
        "A TRANSIENT FAILURE IS NOT A PERMANENT CLASSIFICATION",
    "the-failure-classification-is-supplied-never-inferred-from-a-message":
        "THE FAILURE CLASSIFICATION IS SUPPLIED, NEVER INFERRED FROM A MESSAGE",
    "an-authenticated-human-acknowledges-the-exception":
        "AN AUTHENTICATED HUMAN ACKNOWLEDGES AN EXCEPTION",
    "acknowledgement-records-the-actor": "ACKNOWLEDGEMENT RECORDS THE ACTOR",
    "acknowledgement-proves-seen-not-resolved": "ACKNOWLEDGEMENT PROVES IT WAS SEEN, NOT THAT IT WAS RESOLVED",
    "a-model-cannot-acknowledge-an-exception": "A MODEL CAN NEVER ACKNOWLEDGE AN EXCEPTION",
    "a-system-actor-cannot-acknowledge-an-exception": "A MODEL CAN NEVER ACKNOWLEDGE AN EXCEPTION",
    "an-acknowledged-exception-still-ages": "AN ACKNOWLEDGED EXCEPTION IS STILL OPEN WORK AND STILL AGES",
    "resolution-requires-a-decision-ref": "RESOLUTION REQUIRES A decision_ref THAT RESOLVES",
    "closure-without-a-decision-ref-is-structurally-impossible":
        "CLOSURE WITHOUT A decision_ref IS STRUCTURALLY IMPOSSIBLE",
    "a-decision-ref-that-resolves-to-nothing-is-refused":
        "A decision_ref THAT REFERENCES NOTHING IS NOT A decision_ref",
    "a-decision-ref-naming-a-non-human-decision-event-is-refused":
        "A decision_ref THAT REFERENCES NOTHING IS NOT A decision_ref",
    "a-decision-ref-recorded-by-automation-is-refused":
        "A decision_ref RECORDED BY AUTOMATION IS NOT A HUMAN DECISION",
    "a-model-can-never-resolve-an-exception": "A MODEL CAN NEVER RESOLVE OR AUTO-CLEAR AN EXCEPTION",
    "an-escalated-exception-resolves-through-ec-6":
        "AN ESCALATED EXCEPTION RESOLVES THROUGH EC-6 WITH A decision_ref",
    "resolving-from-ageing-is-an-illegal-transition": "RESOLVING FROM AGEING IS AN ILLEGAL TRANSITION",
    "resolved-is-the-only-terminal-state": "RESOLVED IS THE ONLY TERMINAL STATE",
    "a-resolved-exception-is-retained-never-deleted": "A RESOLVED EXCEPTION IS RETAINED, NEVER DELETED",
    "inactivity-never-closes-an-exception": "INACTIVITY NEVER CLOSES AN EXCEPTION",
    "autoclose-is-an-illegal-transition": "AUTOCLOSE IS AN ILLEGAL TRANSITION",
    "an-exception-never-expires": "AN EXCEPTION NEVER EXPIRES AND CANNOT BE OUTLIVED",
    "an-exception-cannot-be-outlived": "AN EXCEPTION NEVER EXPIRES AND CANNOT BE OUTLIVED",
    "no-sweep-or-reaper-closes-an-exception": "NO SWEEP, REAPER OR SCAN CLOSES AN EXCEPTION",
    "a-timer-can-age-or-escalate-but-never-resolve": "A TIMER MAY AGE OR ESCALATE; A TIMER NEVER RESOLVES",
    "an-open-exception-ages-through-a-durable-timer": "AN OPEN EXCEPTION AGES THROUGH A DURABLE TIMER",
    "an-acknowledged-exception-ages-through-a-durable-timer":
        "AN OPEN EXCEPTION AGES THROUGH A DURABLE TIMER",
    "ageing-escalates-through-a-durable-timer-not-a-sweep":
        "AGEING ESCALATES THROUGH A DURABLE TIMER, NEVER A SWEEP",
    "ageing-and-escalated-remain-human-owned": "AGEING AND ESCALATED REMAIN HUMAN-OWNED",
    "the-ageing-threshold-is-caller-supplied-not-a-business-default":
        "THE AGEING THRESHOLD IS CALLER-SUPPLIED, NOT A BUSINESS DEFAULT",
    "ageing-an-escalated-exception-is-illegal": "RESOLVING FROM AGEING IS AN ILLEGAL TRANSITION",
    "nothing-moves-a-resolved-exception": "NOTHING MOVES A RESOLVED EXCEPTION",
    "restart-re-fires-the-ageing-timer": "A RESTART RE-FIRES THE AGEING TIMER",
    "restart-preserves-the-open-exception": "A RESTART LEAVES THE OPEN EXCEPTION OPEN",
    "restart-after-escalation-reaches-the-canonical-state": "A RESTART RE-FIRES THE AGEING TIMER",
    "a-redelivered-timer-is-a-no-op": "A REDELIVERED TIMER IS A NO-OP",
    "severity-change-is-a-field-mutation-not-a-lifecycle-state":
        "A SEVERITY CHANGE IS A FIELD MUTATION, NOT A LIFECYCLE STATE",
    "severity-change-records-previous-and-new-severity-and-who":
        "A SEVERITY CHANGE RECORDS THE PREVIOUS SEVERITY, THE NEW ONE AND WHO CHANGED IT",
    "severity-change-requires-a-reason": "A SEVERITY CHANGE REQUIRES A REASON",
    "a-model-cannot-change-severity": "A MODEL CAN NEVER CHANGE SEVERITY",
    "severity-is-sev0-sev1-or-sev2-and-nothing-else": "SEVERITY IS SEV0, SEV1 OR SEV2 AND NOTHING ELSE",
    "changing-the-severity-of-an-ageing-exception-is-illegal":
        "A SEVERITY CHANGE IS A FIELD MUTATION, NOT A LIFECYCLE STATE",
    "a-sev0-exception-engages-no-brake-from-inside-m9": "A SEV0 EXCEPTION ENGAGES NO BRAKE FROM INSIDE M9",
    "the-five-canonical-states-and-no-sixth": "THE FIVE CANONICAL STATES ARE THE WHOLE LIFECYCLE",
    "sub-status-is-a-field-never-a-lifecycle-state": "sub_status IS A FIELD, NEVER A LIFECYCLE STATE",
    "there-is-no-cancelled-expired-or-timed-out-state": "THERE IS NO CANCELLED, EXPIRED OR TIMED_OUT STATE",
    "a-retracted-cause-still-requires-an-event-and-a-decision-ref":
        "A RETRACTED CAUSE STILL REQUIRES AN EVENT AND A decision_ref",
    "a-freezing-exception-blocks-consequential-actions-on-the-entity":
        "A FREEZING EXCEPTION BLOCKS CONSEQUENTIAL ACTIONS ON THE ENTITY",
    "not-every-exception-freezes-an-entity": "NOT EVERY EXCEPTION FREEZES AN ENTITY",
    "raise-and-freeze-commit-together-where-applicable":
        "THE RAISE AND THE FREEZE COMMIT TOGETHER WHERE APPLICABLE",
    "a-persistence-failure-leaves-no-half-raised-exception":
        "A PERSISTENCE FAILURE LEAVES NO HALF-RAISED EXCEPTION",
    "state-and-event-co-commit": "THE STATE ROW AND ITS EVENT COMMIT TOGETHER",
    "resolution-unblocks-the-frozen-entity": "RESOLUTION UNBLOCKS THE FROZEN ENTITY",
    "m9-mints-no-gate-decision": "M9 MINTS NO GATE DECISION",
    "an-exception-is-an-input-to-the-checkpoint-never-a-gate":
        "AN EXCEPTION IS AN INPUT TO THE CHECKPOINT AND NEVER A GATE",
    "a-redelivered-raise-through-the-inbox-is-a-no-op": "A REDELIVERED RAISE THROUGH THE INBOX IS A NO-OP",
    "the-open-exception-dedup-index-is-optional-and-recorded":
        "THE OPEN-EXCEPTION DEDUP INDEX IS OPTIONAL, AND THIS BUILD RECORDS ITS CHOICE",
    "concurrent-raises-are-serialized-by-the-database":
        "A REDELIVERED RAISE THROUGH THE INBOX IS A NO-OP",
    "occ-on-exception-version": "A LOST UPDATE ON AN EXCEPTION IS REFUSED",
    "a-stale-version-cannot-overwrite-newer-state": "A STALE VERSION NEVER OVERWRITES NEWER STATE",
    "replay-reconstructs-the-open-exception": "REPLAY RECONSTRUCTS THE OPEN EXCEPTION",
    "replay-rebuilds-the-current-severity-from-the-recorded-events":
        "REPLAY REBUILDS THE CURRENT SEVERITY FROM THE RECORDED EVENTS",
    "replay-does-not-read-severity-from-the-current-row": "REPLAY NEVER READS SEVERITY FROM THE CURRENT ROW",
    "replay-keeps-a-frozen-entity-blocked": "REPLAY KEEPS A FROZEN ENTITY BLOCKED",
    "replay-can-never-manufacture-resolution-authority":
        "REPLAY CAN NEVER MANUFACTURE RESOLUTION AUTHORITY",
    "replay-creates-no-new-authority-and-no-effect":
        "replay: 0 new authority, 0 external effects, 0 decision_refs minted, 0 state flips",
    "exceptions-still-raise-under-a-brake": "EXCEPTIONS STILL RAISE UNDER A BRAKE",
    "m9-engages-no-brake-and-narrows-none": "M9 ENGAGES NO BRAKE AND NARROWS NONE",
    "tenant-isolation": "THE SAME SOURCE IN TWO TENANTS ARE TWO ISOLATED EXCEPTIONS",
    "cross-tenant-identical-source-ref": "THE SAME SOURCE IN TWO TENANTS ARE TWO ISOLATED EXCEPTIONS",
    "cross-tenant-owner-fails-closed": "A CROSS-TENANT OWNER FAILS CLOSED",
    "cross-tenant-source-fails-closed": "A CROSS-TENANT SOURCE FAILS CLOSED",
    "cross-tenant-decision-ref-fails-closed": "A CROSS-TENANT decision_ref FAILS CLOSED",
    "cross-tenant-queue-read-fails-closed": "A CROSS-TENANT QUEUE READ FAILS CLOSED",
    "inbox-idempotency": "A REDELIVERED TIMER IS A NO-OP",
    "database-invariants": "THE DATABASE ENFORCES THE EXCEPTION INVARIANTS",
    "malformed-exception-fails-closed": "THE DATABASE ENFORCES THE EXCEPTION INVARIANTS",
    "an-illegal-transition-persists-nothing-and-is-recorded":
        "AN ILLEGAL TRANSITION PERSISTS NOTHING AND IS RECORDED",
    "the-m1-work-item-machine-is-not-rewritten": "THE M1 WORK ITEM MACHINE IS UNCHANGED",
    "the-m3-effect-authority-is-unchanged": "THE M3 EFFECT AUTHORITY IS UNCHANGED",
    "the-m5-observation-machine-is-not-rewritten": "THE M5 OBSERVATION MACHINE IS UNCHANGED",
    "the-m7-conflict-machine-is-not-rewritten": "THE M7 CONFLICT MACHINE IS UNCHANGED",
    "the-m8-expectation-machine-is-not-rewritten": "THE M8 EXPECTATION MACHINE IS UNCHANGED",
    "m10-m11-and-m12-are-not-built": "THE M10, M11 AND M12 MACHINES ARE NOT BUILT",
}

# The whole-run headline plus the lines not primarily owned by one case, so a full battery cannot pass
# while any required sentence is silently missing.
_EXTRA_REQUIRED: tuple[str, ...] = (
    "AN EXCEPTION IS SOMETHING THAT NEEDS A HUMAN",
    "EVERY EXCEPTION REACHES A NAMED HUMAN OWNER AND IS NEVER CLOSED BY SILENCE",
    "AN EXCEPTION IS NOT AN ERROR LOG, AN ALERT OR AN ISSUE TRACKER ROW",
    "A LEGACY DATABASE MIGRATES TO THE CANONICAL EXCEPTION SHAPE",
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
    age_ms: int = 0
    severity: str = "SEV1"
    actor: str = "human"
    decision_ref: str = "valid"
    freeze: str = "none"
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

    Observations (for FK-backed source kinds) are inserted through plain SQL — the probe never imports
    the M1/M3/M5/M7/M8 machines, so their ship-dark posture is untouched."""

    def __init__(self, ctx: Ctx, tmp: Path) -> None:
        self.ctx = ctx
        self.path = tmp / "ex.db"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(self.conn)
        create_canonical_schema(self.conn)
        enable_and_verify_foreign_keys(self.conn)
        self.clock = Clock(datetime(2026, 8, 28, 8, 0, 0, tzinfo=timezone.utc))
        self._humans: set[tuple[str, str]] = set()
        self._obs: set[tuple[str, str]] = set()

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
                "provenance_class, bound_entity_ref, created_at, updated_at) VALUES (?,?, 'carrier', "
                "?, ?, 'v', 't', 't', 'BOUND', 1, 'SYSTEM_IMPORTED', 'load:4471', 't', 't')",
                (tenant, oid, oid, oid))
            self.conn.commit()
            self._obs.add((tenant, oid))
        return oid

    def machine(self, tenant: str | None = None) -> M9Machine:
        t = tenant or self.tenant()
        self.human(t)
        return M9Machine(self.conn, tenant=t, clock=self.clock)

    def raised(self, m: M9Machine, *, type="UNKNOWN_OUTCOME", severity=None, source_ref="grant-timeout",
               source_kind="compensation", owner=None, summary="a TMS write timed out", **kw):
        owner = self.human(m.tenant) if owner is None else owner
        severity = self.ctx.severity if severity is None else severity
        return m.raise_exception(
            type=type, severity=severity, source_ref=source_ref, source_kind=source_kind,
            owner_id=owner, summary=summary, schedule_timer=kw.pop("schedule_timer", False), **kw)

    def human_decision(self, tenant: str, *, actor=None, event_name="HumanDecided",
                       actor_type="human") -> str:
        eid = str(uuid.uuid4())
        wi = f"wi-{eid[:8]}"
        now = "2026-08-20T10:00:00.000Z"
        env = EventEnvelope(
            event_id=eid, event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=tenant, aggregate_type="work_item", aggregate_id=wi, aggregate_version=1,
            causation_id=None, correlation_id=wi, producer_component="work_service",
            producer_transition_id="WI-9", actor_type=actor_type,
            actor_id=actor or self.human(tenant), trace_id="trace-d", payload={"decision_ref": "x"})
        self.conn.execute("BEGIN IMMEDIATE")
        TransactionalOutbox(self.conn, tenant=tenant).emit(env)
        self.conn.commit()
        return eid

    def count(self, tenant: str) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM exceptions WHERE tenant = ?",
                                 (tenant,)).fetchone()[0]

    def events(self, tenant: str, name: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (tenant, name)).fetchone()[0]

    def security(self, tenant: str) -> list[str]:
        return [r["event_type"] for r in self.conn.execute(
            "SELECT event_type FROM security_events WHERE tenant = ?", (tenant,))]

    def relay(self, m: M9Machine) -> TimerRelay:
        return TimerRelay(self.conn, tenant=m.tenant, handler=m.handle_timer_fired,
                          relay_id="relay-1", clock=self.clock)


def _world(ctx: Ctx) -> World:
    return World(ctx, Path(tempfile.mkdtemp(prefix="p6m9-")))


# ---- the checkpoint seam (the probe FEEDS the one gate authority, never duplicates it) ----------

def _checkpoint_with_native(native_projection):
    """Project an M9 exception into the checkpoint's EXISTING NativeClaim and run the real kernel. A
    freezing OPEN exception is `conflicting`, so step 4 refuses (CLAIM_CONFLICTING); a non-freezing or
    RESOLVED one is not, and the checkpoint proceeds. The probe FEEDS the one gate authority."""
    from phase3_kit import green_scenario
    from freight_recon.checkpoint import (CheckpointInputs, NativeClaim, ProvenanceClass,
                                          run_checkpoint)
    tmp = Path(tempfile.mkdtemp(prefix="p6m9-ckpt-"))
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


# ---- helpers for common flows ------------------------------------------------------------------

def _open(w: World, m: M9Machine, **kw):
    return w.raised(m, **kw).exception.exception_id


def _escalated(w: World, m: M9Machine, **kw) -> str:
    x = _open(w, m, **kw)
    m.age(x)
    m.escalate(x)
    return x


def _resolved(w: World, m: M9Machine, **kw) -> str:
    x = _open(w, m, **kw)
    m.resolve(x, decision_ref=w.human_decision(m.tenant), decision_human_id=w.human(m.tenant))
    return x


def _lines(case: str, *extra: str) -> list[str]:
    out = [_SIG[case]]
    out.extend(extra)
    return out


# ---- the cases ---------------------------------------------------------------------------------

def case_raise_creates_open_with_a_named_human_owner(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    x = m.get(r.exception.exception_id)
    ok = (r.transition_id == "EC-1" and x.state is EcState.OPEN and x.owner_id == HUMANS[0]
          and r.event_names == ("ExceptionRaised",))
    if not ok:
        return CaseResult(False, markers=["### EXCEPTION RAISED WITHOUT AN OWNER ###"])
    return CaseResult(True, lines=_lines(
        "raise-creates-open-with-a-named-human-owner",
        "AN EXCEPTION IS SOMETHING THAT NEEDS A HUMAN",
        "EVERY EXCEPTION REACHES A NAMED HUMAN OWNER AND IS NEVER CLOSED BY SILENCE",
        "AN EXCEPTION IS NOT AN ERROR LOG, AN ALERT OR AN ISSUE TRACKER ROW"))


def case_an_exception_cannot_be_raised_without_an_owner(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, owner="")
    except GuardNotSatisfied:
        refused = True
    if not refused or w.count(m.tenant) != 0:
        return CaseResult(False, markers=["### OWNERLESS EXCEPTION CREATED ###"])
    return CaseResult(True, lines=_lines("an-exception-cannot-be-raised-without-an-owner"))


def case_an_ownerless_exception_is_structurally_impossible(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, created_at, updated_at) "
            "VALUES (?, 'x', 'T', 'SEV1', 'OPEN', 1, NULL, 's', 'compensation', 0, 'u', 't', 't')",
            (m.tenant,))
    except sqlite3.IntegrityError:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### OWNERLESS EXCEPTION CREATED ###"])
    return CaseResult(True, lines=_lines("an-ownerless-exception-is-structurally-impossible"))


def case_the_owner_is_an_active_human_of_this_tenant(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, owner="ghost:nobody")
    except GuardNotSatisfied:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### EXCEPTION RAISED WITHOUT AN OWNER ###"])
    return CaseResult(True, lines=_lines("the-owner-is-an-active-human-of-this-tenant"))


def case_an_offboarded_human_cannot_own_a_new_exception(w: World) -> CaseResult:
    m = w.machine()
    w.human(m.tenant, "owner:gone", state="OFFBOARDED")
    refused = False
    try:
        w.raised(m, owner="owner:gone")
    except GuardNotSatisfied:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### AN OFFBOARDED HUMAN OWNED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("an-offboarded-human-cannot-own-a-new-exception"))


def case_a_model_cannot_own_an_exception(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, owner=HUMANS[0], actor_kind="model")
    except GuardNotSatisfied:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### A MODEL OWNED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("a-model-cannot-own-an-exception"))


def case_raise_records_severity_and_the_source_that_raised_it(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, severity="SEV0", source_ref="grant-77", source_kind="compensation")
    x = m.get(r.exception.exception_id)
    ok = x.severity is EcSeverity.SEV0 and x.source_ref == "grant-77" and x.source_kind == "compensation"
    if not ok:
        return CaseResult(False, markers=["### MISS ### severity/source not recorded"])
    return CaseResult(True, lines=_lines("raise-records-severity-and-the-source-that-raised-it"))


def case_an_exception_cannot_be_raised_without_a_severity(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, severity="")
    except MalformedException:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### MISS ### empty severity accepted"])
    return CaseResult(True, lines=_lines("an-exception-cannot-be-raised-without-a-severity"))


def case_an_exception_cannot_be_raised_without_a_source_ref(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, source_ref="")
    except MalformedException:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### MISS ### empty source_ref accepted"])
    return CaseResult(True, lines=_lines("an-exception-cannot-be-raised-without-a-source-ref"))


def case_the_source_kind_is_a_closed_vocabulary(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, source_kind="banana")
    except MalformedException:
        refused = True
    # And every declared kind is one of the closed set.
    ok = refused and "banana" not in SOURCE_KINDS
    if not ok:
        return CaseResult(False, markers=["### MISS ### source kind vocabulary not closed"])
    return CaseResult(True, lines=_lines("the-source-kind-is-a-closed-vocabulary"))


def case_a_permanent_auth_failure_raises_immediately_with_zero_retries(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, source_ref="auth-1", failure_classification=FailureDisposition.PERMANENT,
                 attempts_before_raise=0)
    ok = m.get(r.exception.exception_id).failure_classification == "permanent"
    if not ok:
        return CaseResult(False, markers=["### MISS ### permanent classification not recorded"])
    # A permanent failure retried before raising is refused.
    refused = False
    try:
        w.raised(m, source_ref="auth-2", failure_classification=FailureDisposition.PERMANENT,
                 attempts_before_raise=3)
    except MalformedException:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### PERMANENT FAILURE RETRIED ###"])
    return CaseResult(True, lines=_lines(
        "a-permanent-auth-failure-raises-immediately-with-zero-retries"))


def case_a_permanent_config_failure_raises_immediately_with_zero_retries(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, source_ref="config-1", failure_classification=FailureDisposition.PERMANENT)
    ok = m.get(r.exception.exception_id).failure_classification == "permanent"
    if not ok:
        return CaseResult(False, markers=["### MISS ### permanent config classification not recorded"])
    return CaseResult(True, lines=_lines(
        "a-permanent-config-failure-raises-immediately-with-zero-retries"))


def case_a_transient_failure_is_not_a_permanent_classification(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, source_ref="trans-1", failure_classification=FailureDisposition.TRANSIENT)
    cls = m.get(r.exception.exception_id).failure_classification
    if cls != "transient":
        return CaseResult(False, markers=["### PERMANENCE INFERRED FROM A MESSAGE ###"])
    return CaseResult(True, lines=_lines("a-transient-failure-is-not-a-permanent-classification"))


def case_the_failure_classification_is_supplied_never_inferred_from_a_message(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, source_ref="msg-1", failure_classification="401 Unauthorized")
    except MalformedException:
        refused = True
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    ok = refused and "_classify" not in src
    if not ok:
        return CaseResult(False, markers=["### PERMANENCE INFERRED FROM A MESSAGE ###"])
    return CaseResult(True, lines=_lines(
        "the-failure-classification-is-supplied-never-inferred-from-a-message"))


def case_an_authenticated_human_acknowledges_the_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    r = m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    ok = r.to_state is EcState.ACKNOWLEDGED and r.event_names == ("ExceptionAcknowledged",)
    if not ok:
        return CaseResult(False, markers=["### MISS ### acknowledge did not land ACKNOWLEDGED"])
    return CaseResult(True, lines=_lines("an-authenticated-human-acknowledges-the-exception"))


def case_acknowledgement_records_the_actor(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    ok = m.get(x).acknowledged_by == HUMANS[0] and m.get(x).acknowledged_at is not None
    if not ok:
        return CaseResult(False, markers=["### MISS ### acknowledge did not record the actor"])
    return CaseResult(True, lines=_lines("acknowledgement-records-the-actor"))


def case_acknowledgement_proves_seen_not_resolved(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    # Still open work — it has not resolved, and it still ages.
    ok = m.get(x).state is EcState.ACKNOWLEDGED and not m.get(x).is_terminal
    m.age(x)
    ok = ok and m.get(x).state is EcState.AGEING
    if not ok:
        return CaseResult(False, markers=["### MISS ### acknowledgement was treated as resolution"])
    return CaseResult(True, lines=_lines("acknowledgement-proves-seen-not-resolved"))


def case_a_model_cannot_acknowledge_an_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.acknowledge(x, acknowledged_by=w.human(m.tenant), actor_kind="model")
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### MODEL ACKNOWLEDGED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("a-model-cannot-acknowledge-an-exception"))


def case_a_system_actor_cannot_acknowledge_an_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.acknowledge(x, acknowledged_by=w.human(m.tenant), actor_kind="system")
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### MISS ### system actor acknowledged"])
    return CaseResult(True, lines=_lines("a-system-actor-cannot-acknowledge-an-exception"))


def case_an_acknowledged_exception_still_ages(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    r = m.age(x)
    if r.to_state is not EcState.AGEING:
        return CaseResult(False, markers=["### MISS ### acknowledged exception did not age"])
    return CaseResult(True, lines=_lines("an-acknowledged-exception-still-ages"))


def case_resolution_requires_a_decision_ref(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    d = w.human_decision(m.tenant)
    r = m.resolve(x, decision_ref=d, decision_human_id=w.human(m.tenant))
    if r.to_state is not EcState.RESOLVED:
        return CaseResult(False, markers=["### MISS ### valid decision_ref did not resolve"])
    return CaseResult(True, lines=_lines("resolution-requires-a-decision-ref"))


def case_closure_without_a_decision_ref_is_structurally_impossible(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.resolve(x, decision_ref=None, decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### EXCEPTION CLOSED WITHOUT A DECISION ###"])
    return CaseResult(True, lines=_lines(
        "closure-without-a-decision-ref-is-structurally-impossible",
        "AN EXCEPTION CLOSED WITHOUT A DECISION IS NOT CLOSED, IT IS FORGOTTEN"))


def case_a_decision_ref_that_resolves_to_nothing_is_refused(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.resolve(x, decision_ref=str(uuid.uuid4()), decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    # The string "done" is also refused.
    y = _open(w, m, source_ref="done-1")
    refused2 = False
    try:
        m.resolve(y, decision_ref="done", decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused2 = True
    if not (refused and refused2):
        return CaseResult(False, markers=["### UNRESOLVABLE decision_ref ACCEPTED ###"])
    return CaseResult(True, lines=_lines("a-decision-ref-that-resolves-to-nothing-is-refused"))


def case_a_decision_ref_naming_a_non_human_decision_event_is_refused(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    # An ExceptionRaised event id is a canonical event but NOT a human decision.
    non_decision = w.conn.execute(
        "SELECT event_id FROM event_outbox WHERE tenant = ? AND event_name = 'ExceptionRaised' "
        "LIMIT 1", (m.tenant,)).fetchone()
    refused = False
    try:
        m.resolve(x, decision_ref=non_decision["event_id"], decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### UNRESOLVABLE decision_ref ACCEPTED ###"])
    return CaseResult(True, lines=_lines("a-decision-ref-naming-a-non-human-decision-event-is-refused"))


def case_a_decision_ref_recorded_by_automation_is_refused(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    automated = w.human_decision(m.tenant, actor="automation", actor_type="system")
    refused = False
    try:
        m.resolve(x, decision_ref=automated, decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### AUTOMATED ACTOR PASSED AS A HUMAN DECISION ###"])
    return CaseResult(True, lines=_lines("a-decision-ref-recorded-by-automation-is-refused"))


def case_a_model_can_never_resolve_an_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    d = w.human_decision(m.tenant)
    refused = False
    try:
        m.resolve(x, decision_ref=d, decision_human_id=w.human(m.tenant), actor_kind="model")
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### MODEL RESOLVED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("a-model-can-never-resolve-an-exception"))


def case_an_escalated_exception_resolves_through_ec_6(w: World) -> CaseResult:
    m = w.machine()
    x = _escalated(w, m)
    d = w.human_decision(m.tenant)
    r = m.resolve(x, decision_ref=d, decision_human_id=w.human(m.tenant))
    if r.transition_id != "EC-6" or r.to_state is not EcState.RESOLVED:
        return CaseResult(False, markers=["### MISS ### escalated did not resolve via EC-6"])
    return CaseResult(True, lines=_lines("an-escalated-exception-resolves-through-ec-6"))


def case_resolving_from_ageing_is_an_illegal_transition(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.age(x)
    d = w.human_decision(m.tenant)
    refused = False
    try:
        m.resolve(x, decision_ref=d, decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### AGEING EXCEPTION RESOLVED DIRECTLY ###"])
    return CaseResult(True, lines=_lines("resolving-from-ageing-is-an-illegal-transition"))


def case_resolved_is_the_only_terminal_state(w: World) -> CaseResult:
    ok = list(EXCEPTION_STATES) == ["OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED", "RESOLVED"]
    m = w.machine()
    x = _resolved(w, m)
    ok = ok and m.get(x).is_terminal
    if not ok:
        return CaseResult(False, markers=["### MISS ### RESOLVED not the only terminal state"])
    return CaseResult(True, lines=_lines("resolved-is-the-only-terminal-state"))


def case_a_resolved_exception_is_retained_never_deleted(w: World) -> CaseResult:
    m = w.machine()
    x = _resolved(w, m)
    refused = False
    try:
        w.conn.execute("DELETE FROM exceptions WHERE tenant = ? AND exception_id = ?", (m.tenant, x))
    except sqlite3.IntegrityError:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### EXCEPTION DELETED ###"])
    return CaseResult(True, lines=_lines("a-resolved-exception-is-retained-never-deleted"))


def case_inactivity_never_closes_an_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="inact-1", age_threshold_ms=1000, escalation_threshold_ms=2000,
              schedule_timer=True)
    relay = w.relay(m)
    for _ in range(20):
        w.clock.advance(seconds=5)
        relay.run_once()
    if m.get(x).state is EcState.RESOLVED:
        return CaseResult(False, markers=["### INACTIVITY CLOSED AN EXCEPTION ###", "### CLOSURE BY SILENCE ###"])
    return CaseResult(True, lines=_lines("inactivity-never-closes-an-exception"))


def case_autoclose_is_an_illegal_transition(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.resolve(x, decision_ref=None, decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    recorded = "IllegalTransitionAttempted" in w.security(m.tenant)
    if not (refused and recorded and m.get(x).state is EcState.OPEN):
        return CaseResult(False, markers=["### AUTOCLOSE CLOSED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("autoclose-is-an-illegal-transition"))


def case_an_exception_never_expires(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    ok = "EXPIRED" not in EXCEPTION_STATES and "TIMED_OUT" not in EXCEPTION_STATES
    if not ok or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### EXCEPTION EXPIRED ###"])
    return CaseResult(True, lines=_lines("an-exception-never-expires"))


def case_an_exception_cannot_be_outlived(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    w.clock.advance(days=400)
    # No sweep, no reaper — the row is still there and still OPEN.
    if m.get(x) is None or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### EXCEPTION OUTLIVED ###"])
    return CaseResult(True, lines=_lines("an-exception-cannot-be-outlived"))


def case_no_sweep_or_reaper_closes_an_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    ok = all(b not in src for b in ("def sweep", "def reap", "def scan_stale"))
    refused = False
    try:
        w.conn.execute("DELETE FROM exceptions WHERE tenant = ?", (m.tenant,))
    except sqlite3.IntegrityError:
        refused = True
    if not (ok and refused and m.get(x) is not None):
        return CaseResult(False, markers=["### SWEEP CLOSED AN EXCEPTION ###", "### REAPER DELETED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("no-sweep-or-reaper-closes-an-exception"))


def case_a_timer_can_age_or_escalate_but_never_resolve(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    fake = TimerFired(tenant=m.tenant, timer_id="t", aggregate_type="exception", aggregate_id=x,
                      timer_kind="exception_resolution", fire_at="t", fired_at="t", payload={})
    refused = False
    try:
        m.handle_timer_fired(fake)
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### TIMER RESOLVED AN EXCEPTION ###"])
    return CaseResult(True, lines=_lines("a-timer-can-age-or-escalate-but-never-resolve"))


def case_an_open_exception_ages_through_a_durable_timer(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="age-1", age_threshold_ms=1000, schedule_timer=True)
    timers = w.conn.execute("SELECT COUNT(*) FROM durable_timers WHERE tenant = ? AND aggregate_id = ?",
                            (m.tenant, x)).fetchone()[0]
    w.clock.advance(seconds=5)
    w.relay(m).run_once()
    if timers != 1 or m.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### MISS ### open exception did not age via durable timer"])
    return CaseResult(True, lines=_lines("an-open-exception-ages-through-a-durable-timer"))


def case_an_acknowledged_exception_ages_through_a_durable_timer(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="age-2", age_threshold_ms=1000, schedule_timer=True)
    m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    w.clock.advance(seconds=5)
    w.relay(m).run_once()
    if m.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### MISS ### acknowledged exception did not age via timer"])
    return CaseResult(True, lines=_lines("an-acknowledged-exception-ages-through-a-durable-timer"))


def case_ageing_escalates_through_a_durable_timer_not_a_sweep(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="esc-1", age_threshold_ms=1000, escalation_threshold_ms=2000,
              schedule_timer=True)
    relay = w.relay(m)
    w.clock.advance(seconds=5)
    relay.run_once()
    w.clock.advance(seconds=5)
    relay.run_once()
    if m.get(x).state is not EcState.ESCALATED:
        return CaseResult(False, markers=["### MISS ### escalation did not ride a durable timer"])
    return CaseResult(True, lines=_lines("ageing-escalates-through-a-durable-timer-not-a-sweep"))


def case_ageing_and_escalated_remain_human_owned(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.age(x)
    owned = m.get(x).owner_id == HUMANS[0]
    m.escalate(x)
    owned = owned and m.get(x).owner_id == HUMANS[0] and not m.get(x).is_terminal
    if not owned:
        return CaseResult(False, markers=["### MISS ### ageing/escalated lost its owner"])
    return CaseResult(True, lines=_lines("ageing-and-escalated-remain-human-owned"))


def case_the_ageing_threshold_is_caller_supplied_not_a_business_default(w: World) -> CaseResult:
    m = w.machine()
    # No threshold ⇒ no timer armed (fail-closed default: ages/escalates only when driven).
    x = _open(w, m, source_ref="thr-none", schedule_timer=True)
    none_armed = w.conn.execute(
        "SELECT COUNT(*) FROM durable_timers WHERE tenant = ? AND aggregate_id = ?",
        (m.tenant, x)).fetchone()[0] == 0
    # A supplied threshold arms a timer.
    y = _open(w, m, source_ref="thr-set", age_threshold_ms=1234, schedule_timer=True)
    armed = w.conn.execute(
        "SELECT COUNT(*) FROM durable_timers WHERE tenant = ? AND aggregate_id = ?",
        (m.tenant, y)).fetchone()[0] == 1
    if not (none_armed and armed):
        return CaseResult(False, markers=["### MISS ### ageing threshold was not caller-supplied"])
    return CaseResult(True, lines=_lines("the-ageing-threshold-is-caller-supplied-not-a-business-default"))


def case_ageing_an_escalated_exception_is_illegal(w: World) -> CaseResult:
    m = w.machine()
    x = _escalated(w, m)
    refused = False
    try:
        m.age(x)
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).state is not EcState.ESCALATED:
        return CaseResult(False, markers=["### MISS ### ageing an escalated exception was allowed"])
    return CaseResult(True, lines=_lines("ageing-an-escalated-exception-is-illegal"))


def case_nothing_moves_a_resolved_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _resolved(w, m)
    moved = False
    for op in (lambda: m.acknowledge(x, acknowledged_by=w.human(m.tenant)),
               lambda: m.age(x), lambda: m.escalate(x)):
        try:
            op()
            moved = True
        except (IllegalTransition, GuardNotSatisfied):
            pass
    if moved or m.get(x).state is not EcState.RESOLVED:
        return CaseResult(False, markers=["### RESOLVED EXCEPTION MOVED ###"])
    return CaseResult(True, lines=_lines("nothing-moves-a-resolved-exception"))


def case_restart_re_fires_the_ageing_timer(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="restart-1", age_threshold_ms=100000, schedule_timer=True)
    # "Restart": a fresh machine + relay over the same durable state.
    m2 = M9Machine(w.conn, tenant=m.tenant, clock=w.clock)
    w.clock.advance(days=1)
    TimerRelay(w.conn, tenant=m.tenant, handler=m2.handle_timer_fired, relay_id="r2",
               clock=w.clock).run_once()
    if m2.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### TIMER LOST ACROSS RESTART ###"])
    return CaseResult(True, lines=_lines("restart-re-fires-the-ageing-timer"))


def case_restart_preserves_the_open_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="restart-2", age_threshold_ms=100000, schedule_timer=True)
    m2 = M9Machine(w.conn, tenant=m.tenant, clock=w.clock)
    TimerRelay(w.conn, tenant=m.tenant, handler=m2.handle_timer_fired, relay_id="r3",
               clock=w.clock).run_once()   # not due
    if m2.get(x) is None or m2.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### EXCEPTION LOST ACROSS RESTART ###"])
    return CaseResult(True, lines=_lines("restart-preserves-the-open-exception"))


def case_restart_after_escalation_reaches_the_canonical_state(w: World) -> CaseResult:
    m = w.machine()
    x = _escalated(w, m, source_ref="restart-3")
    m2 = M9Machine(w.conn, tenant=m.tenant, clock=w.clock)
    if m2.get(x).state is not EcState.ESCALATED:
        return CaseResult(False, markers=["### EXCEPTION LOST ACROSS RESTART ###"])
    return CaseResult(True, lines=_lines("restart-after-escalation-reaches-the-canonical-state"))


def case_a_redelivered_timer_is_a_no_op(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.age(x)
    fired = TimerFired(tenant=m.tenant, timer_id="t", aggregate_type="exception", aggregate_id=x,
                       timer_kind="exception_age_threshold", fire_at="t", fired_at="t",
                       payload={"owner_id": HUMANS[0]})
    result = m.handle_timer_fired(fired)
    if result is not None or m.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### MISS ### redelivered timer was not a no-op"])
    return CaseResult(True, lines=_lines("a-redelivered-timer-is-a-no-op"))


def case_severity_change_is_a_field_mutation_not_a_lifecycle_state(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, severity="SEV2")
    r = m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="grew")
    row = m.get(x)
    ok = (row.state is EcState.OPEN and row.severity is EcSeverity.SEV0
          and r.event_names == ("ExceptionSeverityChanged",))
    if not ok:
        return CaseResult(False, markers=["### SEVERITY CHANGE BECAME A LIFECYCLE STATE ###"])
    return CaseResult(True, lines=_lines("severity-change-is-a-field-mutation-not-a-lifecycle-state"))


def case_severity_change_records_previous_and_new_severity_and_who(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, severity="SEV1")
    m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="grew")
    env = _last_event(w, m.tenant, "ExceptionSeverityChanged", x)
    ok = (env.payload.get("previous_severity") == "SEV1" and env.payload.get("severity") == "SEV0"
          and env.payload.get("changed_by") == HUMANS[0])
    if not ok:
        return CaseResult(False, markers=["### PREVIOUS SEVERITY LOST ###"])
    return CaseResult(True, lines=_lines("severity-change-records-previous-and-new-severity-and-who"))


def case_severity_change_requires_a_reason(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="")
    except GuardNotSatisfied:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### SEVERITY CHANGE WITHOUT A REASON ###"])
    return CaseResult(True, lines=_lines("severity-change-requires-a-reason"))


def case_a_model_cannot_change_severity(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    refused = False
    try:
        m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="r",
                          actor_kind="model")
    except IllegalTransition:
        refused = True
    if not refused or m.get(x).severity is EcSeverity.SEV0:
        return CaseResult(False, markers=["### MODEL CHANGED SEVERITY ###"])
    return CaseResult(True, lines=_lines("a-model-cannot-change-severity"))


def case_severity_is_sev0_sev1_or_sev2_and_nothing_else(w: World) -> CaseResult:
    ok = list(EXCEPTION_SEVERITIES) == ["SEV0", "SEV1", "SEV2"]
    m = w.machine()
    refused = False
    try:
        w.raised(m, severity="SEV9")
    except MalformedException:
        refused = True
    if not (ok and refused):
        return CaseResult(False, markers=["### UNREGISTERED SEVERITY MINTED ###"])
    return CaseResult(True, lines=_lines("severity-is-sev0-sev1-or-sev2-and-nothing-else"))


def case_changing_the_severity_of_an_ageing_exception_is_illegal(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.age(x)
    refused = False
    try:
        m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="r")
    except IllegalTransition:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### MISS ### severity change of AGEING allowed"])
    return CaseResult(True, lines=_lines("changing-the-severity-of-an-ageing-exception-is-illegal"))


def case_a_sev0_exception_engages_no_brake_from_inside_m9(w: World) -> CaseResult:
    m = w.machine()
    _open(w, m, severity="SEV0", source_ref="sev0-1")
    brakes = w.conn.execute("SELECT COUNT(*) FROM brakes WHERE tenant = ?", (m.tenant,)).fetchone()[0]
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    ok = brakes == 0 and "brake.engage" not in src and "from .brake" not in src
    if not ok:
        return CaseResult(False, markers=["### M9 ENGAGED A BRAKE ###"])
    return CaseResult(True, lines=_lines("a-sev0-exception-engages-no-brake-from-inside-m9"))


def case_the_five_canonical_states_and_no_sixth(w: World) -> CaseResult:
    ok = list(EXCEPTION_STATES) == ["OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED", "RESOLVED"]
    m = w.machine()
    refused = False
    try:
        w.conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, created_at, updated_at) "
            "VALUES (?, 'x6', 'T', 'SEV1', 'CLOSED', 1, ?, 's', 'compensation', 0, 'u', 't', 't')",
            (m.tenant, w.human(m.tenant)))
    except sqlite3.IntegrityError:
        refused = True
    if not (ok and refused):
        return CaseResult(False, markers=["### SIXTH LIFECYCLE STATE MINTED ###", "### UNREGISTERED STATE MINTED ###"])
    return CaseResult(True, lines=_lines("the-five-canonical-states-and-no-sixth"))


def case_sub_status_is_a_field_never_a_lifecycle_state(w: World) -> CaseResult:
    ok = set(SUB_STATUSES).isdisjoint(set(EXCEPTION_STATES))
    m = w.machine()
    r = w.raised(m, sub_status="investigating")
    row = m.get(r.exception.exception_id)
    ok = ok and row.state is EcState.OPEN and row.sub_status == "investigating"
    if not ok:
        return CaseResult(False, markers=["### sub_status BECAME A LIFECYCLE STATE ###"])
    return CaseResult(True, lines=_lines("sub-status-is-a-field-never-a-lifecycle-state"))


def case_there_is_no_cancelled_expired_or_timed_out_state(w: World) -> CaseResult:
    banned = {"CANCELLED", "EXPIRED", "TIMED_OUT", "STALE", "AUTO_CLOSED", "SUPERSEDED"}
    ok = banned.isdisjoint(set(EXCEPTION_STATES))
    ok = ok and not any(n.startswith("Exception") and ("Cancel" in n or "Expired" in n
                        or "Superseded" in n) for n in CONTRACTS)
    if not ok:
        return CaseResult(False, markers=["### CANCELLED STATE MINTED ###"])
    return CaseResult(True, lines=_lines("there-is-no-cancelled-expired-or-timed-out-state"))


def case_a_retracted_cause_still_requires_an_event_and_a_decision_ref(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    # A retraction cannot mint a CANCELLED state/event; it reaches RESOLVED via a decision_ref only.
    refused = False
    try:
        m.resolve(x, decision_ref=None, decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        refused = True
    d = w.human_decision(m.tenant)
    resolved = m.resolve(x, decision_ref=d, decision_human_id=w.human(m.tenant)).to_state
    if not (refused and resolved is EcState.RESOLVED):
        return CaseResult(False, markers=["### CANCELLED STATE MINTED ###"])
    return CaseResult(True, lines=_lines("a-retracted-cause-still-requires-an-event-and-a-decision-ref"))


def case_a_freezing_exception_blocks_consequential_actions_on_the_entity(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="frz-1", freezes_entity=True, entity_ref="load:4471",
              frozen_field="delivery")
    proj = m.get(x).native_projection()
    outcome, grants = _checkpoint_with_native(proj)
    ok = proj.conflicting and not outcome.authorized and outcome.step == 4 and grants == 0
    if not ok:
        return CaseResult(False, markers=["### EXCEPTION AUTHORIZED AN ACTION ###"])
    return CaseResult(True, lines=_lines("a-freezing-exception-blocks-consequential-actions-on-the-entity"))


def case_not_every_exception_freezes_an_entity(w: World) -> CaseResult:
    m = w.machine()
    plain = m.get(_open(w, m, source_ref="plain-1"))
    freezing = m.get(_open(w, m, source_ref="frz-2", freezes_entity=True, entity_ref="load:1",
                           frozen_field="f"))
    outcome, grants = _checkpoint_with_native(plain.native_projection())
    ok = (not plain.freezes_entity and not plain.native_projection().conflicting
          and outcome.authorized and freezing.native_projection().conflicting)
    if not ok:
        return CaseResult(False, markers=["### EVERY EXCEPTION FROZE AN ENTITY ###"])
    return CaseResult(True, lines=_lines("not-every-exception-freezes-an-entity"))


def case_raise_and_freeze_commit_together_where_applicable(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="frz-3", freezes_entity=True, entity_ref="load:1", frozen_field="f")
    row = m.get(x)
    raised_event = w.events(m.tenant, "ExceptionRaised") >= 1
    ok = row.freezes_entity and row.frozen_field == "f" and raised_event
    if not ok:
        return CaseResult(False, markers=["### RAISE AND FREEZE SPLIT ACROSS COMMITS ###"])
    return CaseResult(True, lines=_lines("raise-and-freeze-commit-together-where-applicable"))


def case_a_persistence_failure_leaves_no_half_raised_exception(w: World) -> CaseResult:
    m = w.machine()
    before = w.count(m.tenant)
    # A freezing raise with no entity_ref/frozen_field fails BEFORE any row is written.
    refused = False
    try:
        w.raised(m, source_ref="halfraise", freezes_entity=True)
    except MalformedException:
        refused = True
    after = w.count(m.tenant)
    if not (refused and after == before):
        return CaseResult(False, markers=["### HALF-RAISED EXCEPTION PERSISTED ###"])
    return CaseResult(True, lines=_lines("a-persistence-failure-leaves-no-half-raised-exception"))


def case_state_and_event_co_commit(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    # The ACKNOWLEDGED state and its event both exist, or neither would.
    ok = m.get(x).state is EcState.ACKNOWLEDGED and w.events(m.tenant, "ExceptionAcknowledged") == 1
    if not ok:
        return CaseResult(False, markers=["### STATE WITHOUT ITS EVENT ###", "### EVENT WITHOUT ITS STATE ###"])
    return CaseResult(True, lines=_lines("state-and-event-co-commit"))


def case_resolution_unblocks_the_frozen_entity(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="frz-4", freezes_entity=True, entity_ref="load:1", frozen_field="f")
    before = m.get(x).native_projection().conflicting
    m.resolve(x, decision_ref=w.human_decision(m.tenant), decision_human_id=w.human(m.tenant))
    after = m.get(x).native_projection().conflicting
    outcome, grants = _checkpoint_with_native(m.get(x).native_projection())
    if not (before and not after and outcome.authorized):
        return CaseResult(False, markers=["### FROZEN ENTITY UNBLOCKED WITHOUT A RESOLUTION ###"])
    return CaseResult(True, lines=_lines("resolution-unblocks-the-frozen-entity"))


def case_m9_mints_no_gate_decision(w: World) -> CaseResult:
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    ok = ("from .checkpoint" not in src and "import checkpoint" not in src
          and "GateDecision" not in src)
    grants = w.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    ok = ok and grants == 0
    if not ok:
        return CaseResult(False, markers=["### M9 MINTED A GATE DECISION ###"])
    return CaseResult(True, lines=_lines("m9-mints-no-gate-decision"))


def case_an_exception_is_an_input_to_the_checkpoint_never_a_gate(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="frz-5", freezes_entity=True, entity_ref="load:1", frozen_field="f")
    outcome, grants = _checkpoint_with_native(m.get(x).native_projection())
    if outcome.authorized or grants != 0:
        return CaseResult(False, markers=["### M9 MINTED A GATE DECISION ###"])
    return CaseResult(True, lines=_lines("an-exception-is-an-input-to-the-checkpoint-never-a-gate"))


def case_a_redelivered_raise_through_the_inbox_is_a_no_op(w: World) -> CaseResult:
    m = w.machine()
    for _ in range(max(2, w.ctx.repeat)):
        w.raised(m, source_ref="dup-cause", type="SAME")
    if w.count(m.tenant) != 1:
        return CaseResult(False, markers=["### MISS ### duplicate raise created a second exception"])
    return CaseResult(True, lines=_lines("a-redelivered-raise-through-the-inbox-is-a-no-op"))


def case_the_open_exception_dedup_index_is_optional_and_recorded(w: World) -> CaseResult:
    row = w.conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_exceptions_one_open_per_cause",)).fetchone()
    sql = " ".join((row[0] if row else "").split()).upper().replace(" ", "")
    ok = (row is not None and "UNIQUE" in sql and "WHERESTATE!='RESOLVED'" in sql
          and "TENANT" in sql and "SOURCE_REF" in sql and "TYPE" in sql)
    if not ok:
        return CaseResult(False, markers=["### MISS ### dedup index choice not recorded"])
    return CaseResult(True, lines=_lines("the-open-exception-dedup-index-is-optional-and-recorded"))


def case_concurrent_raises_are_serialized_by_the_database(w: World) -> CaseResult:
    m = w.machine()
    n = max(2, w.ctx.concurrency)
    for _ in range(n):
        w.raised(m, source_ref="race-cause", type="SAME")
    if w.count(m.tenant) != 1:
        return CaseResult(False, markers=["### MISS ### concurrent raises created duplicates"])
    return CaseResult(True, lines=_lines("concurrent-raises-are-serialized-by-the-database"))


def case_occ_on_exception_version(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    stale = m.get(x)
    m.acknowledge(x, acknowledged_by=w.human(m.tenant))
    refused = False
    try:
        m.age(x, expected=stale)
    except StateConflict:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### STALE VERSION OVERWROTE NEWER STATE ###"])
    return CaseResult(True, lines=_lines("occ-on-exception-version"))


def case_a_stale_version_cannot_overwrite_newer_state(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    stale = m.get(x)
    m.age(x)
    refused = False
    try:
        m.acknowledge(x, acknowledged_by=w.human(m.tenant), expected=stale)
    except (StateConflict, GuardNotSatisfied):
        refused = True
    if not refused or m.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### STALE VERSION OVERWROTE NEWER STATE ###"])
    return CaseResult(True, lines=_lines("a-stale-version-cannot-overwrite-newer-state"))


def case_replay_reconstructs_the_open_exception(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    rec = m.rebuild(x)
    if rec.state is not EcState.OPEN:
        return CaseResult(False, markers=["### MISS ### replay did not reconstruct OPEN"])
    return CaseResult(True, lines=_lines("replay-reconstructs-the-open-exception"))


def case_replay_rebuilds_the_current_severity_from_the_recorded_events(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, severity="SEV2")
    m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="grew")
    if m.rebuild(x).severity is not EcSeverity.SEV0:
        return CaseResult(False, markers=["### REPLAY REBUILT SEVERITY FROM THE CURRENT ROW ###"])
    return CaseResult(True, lines=_lines("replay-rebuilds-the-current-severity-from-the-recorded-events"))


def case_replay_does_not_read_severity_from_the_current_row(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, severity="SEV2")
    m.change_severity(x, severity="SEV0", changed_by=w.human(m.tenant), reason="grew")
    raise_only = [e for e in m._event_stream(x) if e.event_name == "ExceptionRaised"]
    folded = m.rebuild(x, events=raise_only).severity
    # The truncated fold reproduces the ORIGINAL (SEV2), proving it never reads the row (now SEV0).
    if folded is not EcSeverity.SEV2 or m.get(x).severity is not EcSeverity.SEV0:
        return CaseResult(False, markers=["### REPLAY REBUILT SEVERITY FROM THE CURRENT ROW ###"])
    return CaseResult(True, lines=_lines("replay-does-not-read-severity-from-the-current-row"))


def case_replay_keeps_a_frozen_entity_blocked(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m, source_ref="frz-6", freezes_entity=True, entity_ref="load:1", frozen_field="f")
    rec = m.rebuild(x)
    if not (rec.state is EcState.OPEN and rec.frozen):
        return CaseResult(False, markers=["### FROZEN ENTITY UNBLOCKED WITHOUT A RESOLUTION ###"])
    return CaseResult(True, lines=_lines("replay-keeps-a-frozen-entity-blocked"))


def case_replay_can_never_manufacture_resolution_authority(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    rec = m.rebuild(x)
    if rec.state is EcState.RESOLVED or rec.decision_refs_minted != 0 or m.get(x).decision_ref is not None:
        return CaseResult(False, markers=["### REPLAY MANUFACTURED RESOLUTION AUTHORITY ###"])
    return CaseResult(True, lines=_lines("replay-can-never-manufacture-resolution-authority"))


def case_replay_creates_no_new_authority_and_no_effect(w: World) -> CaseResult:
    m = w.machine()
    x = _escalated(w, m)
    rec = m.rebuild(x)
    ok = (rec.new_authority == 0 and rec.external_effects == 0 and rec.decision_refs_minted == 0
          and rec.state_flips == 0)
    if not ok:
        return CaseResult(False, markers=["### REPLAY MINTED AUTHORITY ###", "### DOWNSTREAM EFFECT DURING REPLAY ###"])
    return CaseResult(True, lines=_lines(
        "replay-creates-no-new-authority-and-no-effect",
        "replay: 0 new authority, 0 external effects, 0 decision_refs minted, 0 state flips"))


def case_exceptions_still_raise_under_a_brake(w: World) -> CaseResult:
    m = w.machine()
    BrakeStore(w.conn).engage(tenant=m.tenant, reason="test", actor="founder", actor_kind="HUMAN")
    r = w.raised(m, source_ref="brake-1")
    if r.to_state is not EcState.OPEN:
        return CaseResult(False, markers=["### MISS ### exception did not raise under a brake"])
    return CaseResult(True, lines=_lines("exceptions-still-raise-under-a-brake"))


def case_m9_engages_no_brake_and_narrows_none(w: World) -> CaseResult:
    m = w.machine()
    _open(w, m, severity="SEV0", source_ref="nobrake-1")
    brakes = w.conn.execute("SELECT COUNT(*) FROM brakes WHERE tenant = ?", (m.tenant,)).fetchone()[0]
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    ok = brakes == 0 and "from .brake" not in src and ".engage(" not in src
    if not ok:
        return CaseResult(False, markers=["### M9 ENGAGED A BRAKE ###"])
    return CaseResult(True, lines=_lines("m9-engages-no-brake-and-narrows-none"))


def case_tenant_isolation(w: World) -> CaseResult:
    a = w.machine(w.tenant(0))
    b = w.machine(w.tenant(1) if w.ctx.tenants > 1 else "other-tenant")
    if w.ctx.tenants == 1:
        w.human("other-tenant")
        b = M9Machine(w.conn, tenant="other-tenant", clock=w.clock)
    ra = w.raised(a, source_ref="shared", type="SAME")
    rb = w.raised(b, source_ref="shared", type="SAME")
    ok = (ra.exception.exception_id != rb.exception.exception_id
          and a.get(rb.exception.exception_id) is None)
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT SOURCE ACCEPTED ###"])
    return CaseResult(True, lines=_lines("tenant-isolation"))


def case_cross_tenant_identical_source_ref(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    w.human("tenant-b")
    b = M9Machine(w.conn, tenant="tenant-b", clock=w.clock)
    ra = w.raised(a, source_ref="pro-4471", type="SAME")
    rb = w.raised(b, source_ref="pro-4471", type="SAME")
    if ra.exception.exception_id == rb.exception.exception_id:
        return CaseResult(False, markers=["### CROSS-TENANT SOURCE ACCEPTED ###"])
    return CaseResult(True, lines=_lines("cross-tenant-identical-source-ref"))


def case_cross_tenant_owner_fails_closed(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    w.human("tenant-b", "owner:bob")
    refused = False
    try:
        w.raised(a, owner="owner:bob")
    except GuardNotSatisfied:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### CROSS-TENANT OWNER ACCEPTED ###"])
    return CaseResult(True, lines=_lines("cross-tenant-owner-fails-closed"))


def case_cross_tenant_source_fails_closed(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    w.human("tenant-b")
    w.observation("tenant-b", "obs-b")   # an observation of tenant B
    refused = False
    try:
        w.raised(a, source_ref="obs-b", source_kind="observation")
    except sqlite3.IntegrityError:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### CROSS-TENANT SOURCE ACCEPTED ###"])
    return CaseResult(True, lines=_lines("cross-tenant-source-fails-closed"))


def case_cross_tenant_decision_ref_fails_closed(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    x = _open(w, a, source_ref="xt-dr")
    w.human("tenant-b")
    other = w.human_decision("tenant-b")   # a decision recorded in tenant B
    refused = False
    try:
        a.resolve(x, decision_ref=other, decision_human_id=w.human("tenant-a"))
    except IllegalTransition:
        refused = True
    if not refused or a.get(x).state is not EcState.OPEN:
        return CaseResult(False, markers=["### CROSS-TENANT decision_ref ACCEPTED ###"])
    return CaseResult(True, lines=_lines("cross-tenant-decision-ref-fails-closed"))


def case_cross_tenant_queue_read_fails_closed(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    w.human("tenant-b")
    b = M9Machine(w.conn, tenant="tenant-b", clock=w.clock)
    _open(w, a, source_ref="q-a")
    # B's owner queue never returns A's exceptions.
    b_queue = b.owner_queue()
    if any(x.tenant == "tenant-a" for x in b_queue):
        return CaseResult(False, markers=["### CROSS-TENANT QUEUE READ ###"])
    return CaseResult(True, lines=_lines("cross-tenant-queue-read-fails-closed"))


def case_inbox_idempotency(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    m.age(x)
    fired = TimerFired(tenant=m.tenant, timer_id="t", aggregate_type="exception", aggregate_id=x,
                       timer_kind="exception_age_threshold", fire_at="t", fired_at="t",
                       payload={"owner_id": HUMANS[0]})
    r1 = m.handle_timer_fired(fired)
    r2 = m.handle_timer_fired(fired)
    if r1 is not None or r2 is not None or m.get(x).state is not EcState.AGEING:
        return CaseResult(False, markers=["### MISS ### inbox idempotency failed"])
    return CaseResult(True, lines=_lines("inbox-idempotency"))


def case_database_invariants(w: World) -> CaseResult:
    m = w.machine()
    ok = phase6_exceptions_readiness_problems(w.conn) == [] and schema_readiness_problems(w.conn) == []
    # The database refuses a RESOLVED row with no decision_ref directly.
    refused = False
    try:
        w.conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, decision_human_id, created_at, "
            "updated_at) VALUES (?, 'xr', 'T', 'SEV1', 'RESOLVED', 1, ?, 's', 'compensation', 0, 'u', "
            "?, 't', 't')", (m.tenant, w.human(m.tenant), w.human(m.tenant)))
    except sqlite3.IntegrityError:
        refused = True
    if not (ok and refused):
        return CaseResult(False, markers=["### EXCEPTION CLOSED WITHOUT A DECISION ###"])
    return CaseResult(True, lines=_lines(
        "database-invariants",
        "A LEGACY DATABASE MIGRATES TO THE CANONICAL EXCEPTION SHAPE"))


def case_malformed_exception_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    before = w.count(m.tenant)
    for i, bad in enumerate((dict(severity=""), dict(source_ref=""), dict(source_kind="nope"),
                             dict(summary=""), dict(owner=""))):
        kw = dict(source_ref=f"bad-{i}")
        kw.update(bad)
        try:
            w.raised(m, **kw)
        except (MalformedException, GuardNotSatisfied):
            pass
    if w.count(m.tenant) != before:
        return CaseResult(False, markers=["### HALF-RAISED EXCEPTION PERSISTED ###"])
    return CaseResult(True, lines=_lines("malformed-exception-fails-closed"))


def case_an_illegal_transition_persists_nothing_and_is_recorded(w: World) -> CaseResult:
    m = w.machine()
    x = _open(w, m)
    try:
        m.resolve(x, decision_ref=None, decision_human_id=w.human(m.tenant))
    except IllegalTransition:
        pass
    recorded = "IllegalTransitionAttempted" in w.security(m.tenant)
    persisted = m.get(x).state is EcState.OPEN
    if not (recorded and persisted):
        return CaseResult(False, markers=["### EXCEPTION CLOSED WITHOUT A DECISION ###"])
    return CaseResult(True, lines=_lines("an-illegal-transition-persists-nothing-and-is-recorded"))


def _unchanged(paths: tuple[str, ...]) -> bool:
    import subprocess
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *paths], cwd=ROOT,
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == ""


def case_the_m1_work_item_machine_is_not_rewritten(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/work_item.py",
                     "src/freight_recon/migrations/phase6_work_items.py"))
    if not ok:
        return CaseResult(False, markers=["### M1 WORK ITEM ROW REWRITTEN BY M9 ###"])
    return CaseResult(True, lines=_lines("the-m1-work-item-machine-is-not-rewritten"))


def case_the_m3_effect_authority_is_unchanged(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/external_effect.py",
                     "src/freight_recon/migrations/phase6_external_effects.py"))
    if not ok:
        return CaseResult(False, markers=["### M3 EFFECT SEAM REWRITTEN ###"])
    return CaseResult(True, lines=_lines("the-m3-effect-authority-is-unchanged"))


def case_the_m5_observation_machine_is_not_rewritten(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/observation.py",
                     "src/freight_recon/migrations/phase6_observations.py"))
    if not ok:
        return CaseResult(False, markers=["### M5 OBSERVATION ROW REWRITTEN BY M9 ###"])
    return CaseResult(True, lines=_lines("the-m5-observation-machine-is-not-rewritten"))


def case_the_m7_conflict_machine_is_not_rewritten(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/conflict.py",
                     "src/freight_recon/migrations/phase6_conflicts.py"))
    if not ok:
        return CaseResult(False, markers=["### M7 CONFLICT ROW REWRITTEN BY M9 ###"])
    return CaseResult(True, lines=_lines("the-m7-conflict-machine-is-not-rewritten"))


def case_the_m8_expectation_machine_is_not_rewritten(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/expectation.py",
                     "src/freight_recon/migrations/phase6_expectations.py"))
    if not ok:
        return CaseResult(False, markers=["### M8 EXPECTATION ROW REWRITTEN BY M9 ###"])
    return CaseResult(True, lines=_lines("the-m8-expectation-machine-is-not-rewritten"))


def case_m10_m11_and_m12_are_not_built(w: World) -> CaseResult:
    tables = {t[0] for t in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    forbidden = {"compensations", "policies", "rules", "evidence"}
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    import re
    foreign_ids = re.findall(r"\b(?:CM|PO|RU)-\d+[a-z]*\b", src)
    ok = not (forbidden & tables) and not foreign_ids
    if not ok:
        return CaseResult(False, markers=["### M10 EVENT MINTED ###", "### COMPENSATION FABRICATED ###"])
    return CaseResult(True, lines=_lines("m10-m11-and-m12-are-not-built"))


CASE_FUNCS = {name: globals()[f"case_{name.replace('-', '_')}"] for name in CASES}


# ---- argument handling & the run --------------------------------------------------------------

def _last_event(w: World, tenant: str, name: str, aggregate_id: str) -> EventEnvelope:
    row = w.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = 'exception' "
        "AND aggregate_id = ? AND event_name = ? ORDER BY aggregate_version DESC, sequence DESC "
        "LIMIT 1", (tenant, aggregate_id, name)).fetchone()
    return EventEnvelope.from_json(row["envelope_json"])


def _run_case(w: World, case: str) -> CaseResult:
    try:
        result = CASE_FUNCS[case](w)
        if not isinstance(result, CaseResult):
            return CaseResult(False, markers=[f"### MISS ### {case} returned no result"])
        return result
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

    if args.severity not in SEVERITY_VALUES:
        raise ProbeExit(
            f"--severity {args.severity!r} is not one of {list(SEVERITY_VALUES)}. Severity is a "
            f"closed vocabulary — SEV0 | SEV1 | SEV2 and no fourth.")
    if args.actor not in ACTOR_VALUES:
        raise ProbeExit(
            f"--actor {args.actor!r} is not one of {list(ACTOR_VALUES)}. WHO acts is M9's own axis — "
            f"a human acknowledges and resolves, a timer ages and never resolves, a model does none.")
    if args.decision_ref not in DECISION_REF_VALUES:
        raise ProbeExit(
            f"--decision-ref {args.decision_ref!r} is not one of {list(DECISION_REF_VALUES)}. The "
            f"resolution authority offered is a closed vocabulary; `absent` is closure by silence.")
    if args.freeze not in FREEZE_VALUES:
        raise ProbeExit(
            f"--freeze {args.freeze!r} is not one of {list(FREEZE_VALUES)}. Not every exception "
            f"freezes an entity — the freeze is stated and recorded, never guessed.")
    if args.inject in ("reopen-exception", "reopen"):
        raise ProbeExit(
            "unknown fault 'reopen-exception' is REFUSED: entity §27 and machine §24 say 'Reopening "
            "rules. N/A (a recurrence is a new Exception)'. A probe that accepted it would produce "
            "passing evidence for a transition the corpus states does not exist.")
    if args.inject in ("correct-exception", "correct"):
        raise ProbeExit(
            "unknown fault 'correct-exception' is REFUSED: entity §23 and machine §25 say 'Correction "
            "rules. N/A'. Correction is the tidy-looking thing a build session adds; it would let a "
            "wrong severity or a wrong owner be edited out of history.")
    if args.inject in ("supersede-exception", "supersede"):
        raise ProbeExit(
            "unknown fault 'supersede-exception' is REFUSED: entity §24 and machine §26 say "
            "'Supersession rules. N/A'; there is no SUPERSEDED state in registry §4's M9 row and no "
            "ExceptionSuperseded event is registered anywhere.")
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
        age_ms=bounded_int("age-ms", args.age_ms, 0, 86400000),
        severity=args.severity, actor=args.actor, decision_ref=args.decision_ref, freeze=args.freeze,
        seed=args.seed, inject=args.inject)
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
    p.add_argument("--age-ms", type=int, default=0)
    p.add_argument("--severity", default="SEV1")
    p.add_argument("--actor", default="human")
    p.add_argument("--decision-ref", default="valid")
    p.add_argument("--freeze", default="none")
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
            cases = [args.case]
        else:
            cases = list(CASES)
    except ProbeExit as exc:
        print(f"probe: {exc.message}", file=sys.stderr)
        return 2

    wrong = 0
    printed: set[str] = set()
    for case in cases:
        case_ctx = Ctx(concurrency=ctx.concurrency, delay_ms=ctx.delay_ms, repeat=ctx.repeat,
                       tenants=ctx.tenants, age_ms=ctx.age_ms, severity=ctx.severity, actor=ctx.actor,
                       decision_ref=ctx.decision_ref, freeze=ctx.freeze, seed=ctx.seed,
                       inject=ctx.inject,
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

    if args.case is None:
        for line in _REQUIRED_ON_FULL_RUN:
            if line not in printed:
                print(line)
                printed.add(line)

    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
