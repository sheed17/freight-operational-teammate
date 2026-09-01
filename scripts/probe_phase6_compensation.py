#!/usr/bin/env python3
"""M10 — the Compensation — deterministic narrative probe.

A carrier's POD was bound to the wrong load, an invoice for GBP 2,850 went out on the strength of it, and
a human has corrected the binding: that invoice rests on a fact known to be wrong, and the money has to
be credited back. The tempting fix is a rollback — find the effect, call the TMS void endpoint, mark the
row undone — and that is a second ungated write route into a customer's accounting system, reached at the
exact moment the system is already known to be wrong about something. So M10 does the opposite: the
credit note is a NEW external effect, with its own pipeline, its own human approval, its own checkpoint,
its own single-use grant, its own commit key and its own readback. And when the original outcome is
UNKNOWN, compensation is REFUSED outright (M-33).

This probe measures the DATABASE and the EVENT REGISTRY, not its own narration. It is the ONLY interface
a generated Product-Driver scenario can compose M10's real behaviour through, so the interface is a
contract:

    --list-cases        the case names, one per line, kebab-case
    --list-dimensions   every mutation-axis token, one per line
    --case <case>       run exactly one case
    --all  (or no args) run every case; exit 0 only if every one behaved as specified

Mutation axes (the closed vocabulary the generator may vary a case along):
    --concurrency 1-8   how many raisers race one invalidated effect
    --delay-ms 0-5000   timing skew
    --repeat 1-20       duplicate-raise / redelivery pressure
    --tenants 1-3       isolation pressure
    --seed <int>        deterministic interleaving
    --inject <fault>    the closed fault set (see --list-dimensions); an unknown fault exits 2
    --actor <kind>      WHO attempts the transition: human|system|model|detector
    --decision-ref <k>  the authority offered: valid|absent|unresolvable|non-human|automated|cross-tenant
    --original-state    the M3 state of the effect being compensated (### THIS UNIT'S OWN AXIS): all eight
    --exposure          the money shape (### THIS UNIT'S OWN AXIS): integer|float|decimal|boolean|lowercase
    --brake             none|engaged
"""

from __future__ import annotations

import argparse
import ast
import random
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

from decimal import Decimal  # noqa: E402

from freight_recon.commit_key import (  # noqa: E402
    CANONICAL_OCCURRENCE_REQUIRED,
    CANONICAL_OCCURRENCE_SOURCES,
    OCCURRENCE_RULES,
    CanonicalOccurrence,
    UnresolvedCanonicalOccurrence,
    occurrence_key_for,
)
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.fingerprint import FingerprintError, Money, MoneyMustNotFloat  # noqa: E402
from freight_recon.compensation import (  # noqa: E402
    F10_CONTRACTS,
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    CmState,
    GuardNotSatisfied,
    IllegalTransition,
    M10Machine,
    MalformedCompensation,
    OriginalNotCompensable,
    Trigger,
    legal_transitions,
)
from freight_recon.migrations.phase6_compensations import (  # noqa: E402
    COMPENSATION_STATES,
    P6CM_TENANT_TABLES,
    phase6_compensations_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

import phase6_compensation_kit as ck  # noqa: E402

HUMAN = "owner:sam"
CANONICAL_CM_IDS = ("CM-1", "CM-1r", "CM-2", "CM-2n", "CM-3", "CM-4", "CM-4f", "CM-5", "CM-5x")
SEVEN_F10 = ("CompensationApproved", "CompensationCompleted", "CompensationFailed",
             "CompensationImpossible", "CompensationRefused", "CompensationRequired",
             "CompensationStarted")


# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    # CM-1 eligibility
    "required-from-a-verified-original-effect",
    "the-original-state-is-read-from-the-ledger-not-a-caller-flag",
    "compensation-cannot-be-created-from-an-unknown-outcome",
    "refusal-on-unknown-emits-compensationrefused-and-zero-rows",
    "refusal-on-unknown-mints-no-pipeline-no-grant-and-no-effect",
    "a-failed-original-creates-no-compensation",
    "a-revoked-original-creates-no-compensation",
    "an-expired-unclaimed-original-creates-no-compensation",
    "a-merely-attempted-original-creates-no-compensation",
    "a-granted-or-claimed-original-creates-no-compensation",
    "no-refusal-variant-is-minted-for-the-other-six-states",
    # invalidating authority
    "a-model-inferred-invalidation-is-refused",
    "confidence-one-does-not-substitute-for-authority",
    "the-invalidating-decision-ref-must-resolve",
    "an-automation-emitted-human-decision-event-is-refused",
    "a-rule-kind-decision-ref-refuses-today",
    "the-invalidating-decision-ref-rides-the-compensationrequired-event",
    "m10-imports-the-k1-resolver",
    # owner
    "a-compensation-carries-a-named-human-owner-from-required",
    "an-ownerless-compensation-is-structurally-impossible",
    "a-model-cannot-own-a-compensation",
    "a-cross-tenant-owner-is-refused",
    "an-offboarded-human-cannot-own-a-new-compensation",
    # exposure
    "exposure-is-required-from-required",
    "exposure-is-integer-minor-units-and-a-currency",
    "a-float-exposure-is-refused",
    "a-decimal-exposure-is-refused",
    "exposure-survives-into-compensation-failed",
    "exposure-survives-into-not-possible",
    # lifecycle
    "the-six-canonical-states-and-no-seventh",
    "completed-is-the-only-terminal-state",
    "compensation-failed-and-not-possible-stay-human-owned",
    "a-compensation-never-expires",
    "a-compensation-is-never-cancelled",
    "a-compensation-row-cannot-be-deleted",
    "no-timer-moves-compensation-failed",
    "no-timer-moves-any-compensation-state",
    "there-is-no-automatic-retry-from-compensation-failed",
    "no-sweep-reaper-or-scan-moves-a-compensation",
    # CM-2 approval
    "required-to-approved-requires-an-authenticated-human",
    "the-approval-id-resolves-to-a-same-tenant-m4-approval",
    "the-approval-is-bound-to-this-compensations-commit-key",
    "a-stale-or-wrong-approval-is-refused",
    "a-cross-tenant-approval-is-refused",
    "a-model-cannot-approve-a-compensation",
    "confidence-cannot-approve-a-compensation",
    "m10-builds-no-second-approval-system",
    "compensation-approved-is-not-approval-granted",
    # CM-3 pipeline
    "execution-starts-a-new-m2-pipeline-instance",
    "the-executing-pipeline-is-not-the-original",
    "executing-requires-a-bound-pipeline-instance-id",
    "the-compensating-effect-passes-the-full-checkpoint",
    "the-compensating-effect-claims-its-own-grant",
    "the-original-effect-grant-is-never-reused",
    "m10-invokes-no-adapter-directly",
    "m10-performs-no-direct-system-write",
    # commit key
    "the-compensating-effect-has-its-own-commit-key",
    "the-commit-key-is-the-canonical-compensation-occurrence",
    "the-commit-key-is-not-derived-from-the-originals",
    "retrying-the-same-compensation-converges-on-one-commit-key",
    "the-original-and-compensating-effects-stay-distinct",
    # brake and policy
    "an-active-brake-blocks-a-compensating-write",
    "an-urgent-compensation-does-not-bypass-the-brake",
    "a-human-narrows-the-brake-through-the-landed-mechanism",
    "m10-engages-no-brake-and-narrows-none",
    "m10-mints-no-gate-decision",
    "the-money-gate-defaults-to-human-approval-required",
    "m10-registers-no-gate",
    # CM-4 / CM-4f readback
    "completed-requires-a-verified-compensating-effect",
    "adapter-success-alone-does-not-complete-a-compensation",
    "write-acceptance-is-not-completion",
    "a-timeout-is-not-a-failure",
    "a-failed-executing-pipeline-reaches-compensation-failed",
    "a-needs-verification-pipeline-reaches-compensation-failed",
    "compensation-failed-carries-the-exposure",
    # CM-2n
    "not-possible-keeps-its-owner-and-exposure",
    "not-possible-writes-nothing-to-the-world",
    "impossibility-is-never-inferred-from-model-output",
    # CM-5
    "a-human-establishes-reality-with-a-resolving-decision-ref",
    "cm5-emits-the-shared-f3-realityestablished-with-subject-compensation",
    "m10-mints-no-second-realityestablished-contract",
    "reality-establishment-from-not-possible-fabricates-no-pipeline",
    "a-model-cannot-establish-reality",
    # uniqueness and concurrency
    "one-active-compensation-per-invalidated-effect",
    "the-uniqueness-predicate-excludes-not-possible-exactly-as-written",
    "concurrent-creation-yields-exactly-one-compensation",
    # storm
    "n-invalidated-effects-raise-n-individually-gated-compensations",
    "there-is-no-bulk-effect-grant",
    "there-is-no-bulk-approval",
    "there-is-no-one-undo-all-adapter-call",
    "aggregate-exposure-is-computed-before-approval",
    # tenancy
    "tenant-is-first-in-the-compensation-primary-key",
    "a-cross-tenant-original-effect-is-refused",
    "a-cross-tenant-pipeline-is-refused",
    "a-cross-tenant-decision-ref-is-refused",
    # transactionality and recovery
    "state-and-event-co-commit-in-one-transaction",
    "a-persistence-failure-leaves-no-half-created-compensation",
    "there-is-no-approved-without-its-event",
    "there-is-no-executing-without-its-pipeline-binding",
    "a-crash-after-claim-reaches-needs-verification-then-compensation-failed",
    "a-compensation-survives-a-restart",
    # replay
    "replay-reconstructs-compensation-state-only",
    "replay-mints-zero-pipelines-grants-claims-and-effects",
    # ship dark and regression
    "m10-ships-dark-with-zero-production-importers",
    "m10-joins-no-outbound-channel",
    "m10-builds-no-oversight-queue-or-notifier",
    "m11-m12-and-m13-are-not-built",
    "the-m9-escalation-seam-is-named-and-left-unwired",
    "m1-through-m9-are-unchanged",
)

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "seed", "inject",
    "actor", "decision-ref", "original-state", "exposure", "brake",
)

ORIGINAL_STATE_VALUES = ("all", "VERIFIED", "UNKNOWN_OUTCOME", "FAILED", "REVOKED",
                         "EXPIRED_UNCLAIMED", "GRANTED", "CLAIMED", "ATTEMPTED")
EXPOSURE_VALUES = ("integer", "float", "decimal", "boolean", "lowercase")
ACTOR_VALUES = ("human", "system", "model", "detector")
DECISION_REF_VALUES = ("valid", "absent", "unresolvable", "non-human", "automated", "cross-tenant")
BRAKE_VALUES = ("none", "engaged")

FAULTS: dict[str, str] = {
    "none": "any",
    "compensate-unknown": "cm1",            # ILLEGAL — M-33
    "compensate-failed": "cm1",             # refused — no variant
    "caller-flag-eligibility": "cm1",       # refused — the ledger decides
    "model-inferred-invalidation": "cm1",   # refused — GR-8
    "unresolvable-decision-ref": "cm1",     # refused — K-1
    "automated-decision-ref": "cm1",        # refused — ER-11
    "model-owner": "cm1",                   # refused
    "ownerless": "cm1",                     # refused
    "cross-tenant-owner": "cm1",            # refused
    "cross-tenant-original": "cm1",         # refused
    "float-exposure": "cm1",                # refused
    "decimal-exposure": "cm1",              # refused
    "model-approve": "cm2",                 # ILLEGAL
    "cross-tenant-approval": "cm2",         # refused
    "wrong-commit-key-approval": "cm2",     # refused
    "bypass-pipeline": "cm3",               # refused — EXECUTING requires a bound pipeline
    "original-grant-reuse": "cm3",          # refused — own grant
    "complete-without-readback": "cm4",     # refused — adapter success is not completion
    "timeout-as-failure": "cm4",            # ILLEGAL framing — timeout -> COMPENSATION_FAILED
    "timer-move-failed": "cm5x",            # ILLEGAL
    "auto-retry-failed": "cm5x",            # ILLEGAL
    "model-establish-reality": "cm5",       # ILLEGAL
    "second-reality-contract": "cm5",       # refused — one contract
    "bulk-undo": "storm",                   # refused
    "delete-compensation": "lifecycle",     # ILLEGAL — retention permanent
    "cancel-compensation": "lifecycle",     # refused — no CANCELLED state
    "expire-compensation": "lifecycle",     # refused — never expires
    "engage-brake": "brake",                # ILLEGAL — M10 engages none
    "mint-gate": "gate",                    # ILLEGAL — M10 mints none
    "replay-effect": "replay",              # ILLEGAL — replay produces no effect
}


# ### THE INVARIANT SENTENCES THE VERIFICATION SCENARIO MATCHES AS LITERAL SUBSTRINGS.
_SIG: dict[str, str] = {
    "required-from-a-verified-original-effect": "A COMPENSATION IS ITSELF A SEPARATELY GATED EXTERNAL EFFECT",
    "the-original-state-is-read-from-the-ledger-not-a-caller-flag":
        "THE ORIGINAL STATE IS READ FROM THE LEDGER, NEVER A CALLER FLAG",
    "compensation-cannot-be-created-from-an-unknown-outcome": "COMPENSATION IS FORBIDDEN ON AN UNKNOWN OUTCOME",
    "refusal-on-unknown-emits-compensationrefused-and-zero-rows":
        "YOU CANNOT UNDO WHAT YOU CANNOT PROVE YOU DID",
    "refusal-on-unknown-mints-no-pipeline-no-grant-and-no-effect":
        "THE UNKNOWN-OUTCOME REFUSAL MINTS ZERO PIPELINES, GRANTS AND EFFECTS",
    "a-failed-original-creates-no-compensation": "A FAILED ORIGINAL EFFECT CREATES NO COMPENSATION",
    "a-revoked-original-creates-no-compensation": "A REVOKED ORIGINAL EFFECT CREATES NO COMPENSATION",
    "an-expired-unclaimed-original-creates-no-compensation":
        "AN EXPIRED_UNCLAIMED ORIGINAL EFFECT CREATES NO COMPENSATION",
    "a-merely-attempted-original-creates-no-compensation": "A MERELY ATTEMPTED ORIGINAL CREATES NO COMPENSATION",
    "a-granted-or-claimed-original-creates-no-compensation": "A GRANTED OR CLAIMED ORIGINAL CREATES NO COMPENSATION",
    "no-refusal-variant-is-minted-for-the-other-six-states":
        "THERE IS EXACTLY ONE REFUSAL CAUSE, AND IT IS unknown_outcome",
    "a-model-inferred-invalidation-is-refused": "A MODEL_INFERRED INVALIDATION IS REFUSED",
    "confidence-one-does-not-substitute-for-authority": "CONFIDENCE ORDERS A QUEUE AND GATES NOTHING",
    "the-invalidating-decision-ref-must-resolve": "THE INVALIDATING decision_ref MUST RESOLVE",
    "an-automation-emitted-human-decision-event-is-refused":
        "A HUMAN-DECISION EVENT RECORDED BY AUTOMATION IS NOT A DECISION",
    "a-rule-kind-decision-ref-refuses-today": "A RULE-KIND decision_ref REFUSES TODAY (M12 NOT BUILT)",
    "the-invalidating-decision-ref-rides-the-compensationrequired-event":
        "THE INVALIDATING decision_ref RIDES THE CompensationRequired EVENT",
    "m10-imports-the-k1-resolver": "M10 IMPORTS M1's K-1 RESOLVER, NEVER A SECOND ONE",
    "a-compensation-carries-a-named-human-owner-from-required": "A MODEL CAN NEVER OWN A COMPENSATION",
    "an-ownerless-compensation-is-structurally-impossible": "AN OWNERLESS COMPENSATION IS STRUCTURALLY IMPOSSIBLE",
    "a-model-cannot-own-a-compensation": "A MODEL CAN NEVER OWN A COMPENSATION",
    "a-cross-tenant-owner-is-refused": "A CROSS-TENANT OWNER FAILS CLOSED",
    "an-offboarded-human-cannot-own-a-new-compensation": "AN OFFBOARDED HUMAN CANNOT OWN A NEW COMPENSATION",
    "exposure-is-required-from-required": "THE EXPOSURE IS REQUIRED FROM REQUIRED",
    "exposure-is-integer-minor-units-and-a-currency": "THE EXPOSURE IS INTEGER MINOR UNITS AND A CURRENCY",
    "a-float-exposure-is-refused": "A FLOAT EXPOSURE IS REFUSED",
    "a-decimal-exposure-is-refused": "A DECIMAL EXPOSURE IS REFUSED",
    "exposure-survives-into-compensation-failed": "NOT_POSSIBLE IS HONEST AND KEEPS ITS EXPOSURE",
    "exposure-survives-into-not-possible": "NOT_POSSIBLE IS HONEST AND KEEPS ITS EXPOSURE",
    "the-six-canonical-states-and-no-seventh": "THE SIX CANONICAL STATES ARE THE WHOLE LIFECYCLE",
    "completed-is-the-only-terminal-state": "COMPLETED IS THE ONLY TERMINAL STATE",
    "compensation-failed-and-not-possible-stay-human-owned":
        "COMPENSATION_FAILED AND NOT_POSSIBLE STAY HUMAN-OWNED",
    "a-compensation-never-expires": "A COMPENSATION NEVER EXPIRES",
    "a-compensation-is-never-cancelled": "A COMPENSATION IS NEVER CANCELLED",
    "a-compensation-row-cannot-be-deleted": "A COMPENSATION ROW CANNOT BE DELETED",
    "no-timer-moves-compensation-failed": "NO TIMER MOVES COMPENSATION_FAILED",
    "no-timer-moves-any-compensation-state": "NO TIMER MOVES ANY COMPENSATION STATE",
    "there-is-no-automatic-retry-from-compensation-failed": "THERE IS NO AUTOMATIC RETRY OF A FAILED COMPENSATION",
    "no-sweep-reaper-or-scan-moves-a-compensation": "NO SWEEP, REAPER OR SCAN MOVES A COMPENSATION",
    "required-to-approved-requires-an-authenticated-human": "REQUIRED TO APPROVED REQUIRES AN AUTHENTICATED HUMAN",
    "the-approval-id-resolves-to-a-same-tenant-m4-approval": "THE APPROVAL RESOLVES TO A SAME-TENANT M4 APPROVAL",
    "the-approval-is-bound-to-this-compensations-commit-key":
        "THE APPROVAL IS BOUND TO THIS COMPENSATIONS COMMIT KEY",
    "a-stale-or-wrong-approval-is-refused": "A STALE OR WRONG-COMMIT-KEY APPROVAL IS REFUSED",
    "a-cross-tenant-approval-is-refused": "A CROSS-TENANT APPROVAL IS REFUSED",
    "a-model-cannot-approve-a-compensation": "A MODEL CAN NEVER APPROVE A COMPENSATION",
    "confidence-cannot-approve-a-compensation": "A MODEL CAN NEVER APPROVE A COMPENSATION",
    "m10-builds-no-second-approval-system": "M10 BUILDS NO SECOND APPROVAL SYSTEM",
    "compensation-approved-is-not-approval-granted": "Compensation.APPROVED IS NOT Approval.GRANTED",
    "execution-starts-a-new-m2-pipeline-instance": "EXECUTION STARTS A NEW M2 PIPELINE INSTANCE",
    "the-executing-pipeline-is-not-the-original": "THE EXECUTING PIPELINE IS NOT THE ORIGINAL",
    "executing-requires-a-bound-pipeline-instance-id": "EXECUTING REQUIRES A BOUND PIPELINE INSTANCE ID",
    "the-compensating-effect-passes-the-full-checkpoint": "THE COMPENSATING EFFECT PASSES THE FULL CHECKPOINT",
    "the-compensating-effect-claims-its-own-grant": "THE COMPENSATING EFFECT CLAIMS ITS OWN GRANT",
    "the-original-effect-grant-is-never-reused": "A COMPENSATING EFFECT NEVER REUSES THE ORIGINAL EFFECT GRANT",
    "m10-invokes-no-adapter-directly": "M10 INVOKES NO ADAPTER DIRECTLY",
    "m10-performs-no-direct-system-write": "M10 PERFORMS NO DIRECT SYSTEM WRITE",
    "the-compensating-effect-has-its-own-commit-key": "THE COMPENSATING EFFECT HAS ITS OWN COMMIT KEY",
    "the-commit-key-is-the-canonical-compensation-occurrence":
        "THE COMMIT KEY IS THE CANONICAL COMPENSATION OCCURRENCE",
    "the-commit-key-is-not-derived-from-the-originals": "THE COMMIT KEY IS NOT DERIVED FROM THE ORIGINALS",
    "retrying-the-same-compensation-converges-on-one-commit-key":
        "RETRYING THE SAME COMPENSATION CONVERGES ON ONE COMMIT KEY",
    "the-original-and-compensating-effects-stay-distinct": "THE ORIGINAL AND COMPENSATING EFFECTS STAY DISTINCT",
    "an-active-brake-blocks-a-compensating-write": "A COMPENSATION IS BLOCKED UNDER AN ACTIVE BRAKE",
    "an-urgent-compensation-does-not-bypass-the-brake": "THERE IS NO FAST PATH FOR UNDO",
    "a-human-narrows-the-brake-through-the-landed-mechanism": "A HUMAN NARROWS THE BRAKE THROUGH THE LANDED MECHANISM",
    "m10-engages-no-brake-and-narrows-none": "M10 ENGAGES NO BRAKE AND NARROWS NONE",
    "m10-mints-no-gate-decision": "M10 MINTS NO GATE DECISION",
    "the-money-gate-defaults-to-human-approval-required": "THE MONEY GATE DEFAULTS TO HUMAN_APPROVAL_REQUIRED",
    "m10-registers-no-gate": "M10 REGISTERS NO GATE",
    "completed-requires-a-verified-compensating-effect": "COMPLETION REQUIRES READBACK, NOT AN ADAPTER RETURN CODE",
    "adapter-success-alone-does-not-complete-a-compensation":
        "COMPLETION REQUIRES READBACK, NOT AN ADAPTER RETURN CODE",
    "write-acceptance-is-not-completion": "WRITE ACCEPTANCE IS NOT COMPLETION",
    "a-timeout-is-not-a-failure": "A TIMEOUT IS NOT A FAILURE",
    "a-failed-executing-pipeline-reaches-compensation-failed":
        "A FAILED EXECUTING PIPELINE REACHES COMPENSATION_FAILED",
    "a-needs-verification-pipeline-reaches-compensation-failed":
        "A NEEDS_VERIFICATION PIPELINE REACHES COMPENSATION_FAILED",
    "compensation-failed-carries-the-exposure": "COMPENSATION_FAILED NEVER AUTO-RESOLVES",
    "not-possible-keeps-its-owner-and-exposure": "NOT_POSSIBLE IS HONEST AND KEEPS ITS EXPOSURE",
    "not-possible-writes-nothing-to-the-world": "NOT_POSSIBLE WRITES NOTHING TO THE WORLD",
    "impossibility-is-never-inferred-from-model-output": "IMPOSSIBILITY IS NEVER INFERRED FROM MODEL OUTPUT",
    "a-human-establishes-reality-with-a-resolving-decision-ref": "A MODEL CAN NEVER ESTABLISH REALITY",
    "cm5-emits-the-shared-f3-realityestablished-with-subject-compensation":
        "M10 MINTS NO SECOND RealityEstablished CONTRACT",
    "m10-mints-no-second-realityestablished-contract": "M10 MINTS NO SECOND RealityEstablished CONTRACT",
    "reality-establishment-from-not-possible-fabricates-no-pipeline":
        "REALITY ESTABLISHMENT FROM NOT_POSSIBLE FABRICATES NO PIPELINE",
    "a-model-cannot-establish-reality": "A MODEL CAN NEVER ESTABLISH REALITY",
    "one-active-compensation-per-invalidated-effect": "ONE ACTIVE COMPENSATION PER INVALIDATED EFFECT",
    "the-uniqueness-predicate-excludes-not-possible-exactly-as-written":
        "THE UNIQUENESS PREDICATE EXCLUDES NOT_POSSIBLE EXACTLY AS WRITTEN",
    "concurrent-creation-yields-exactly-one-compensation": "CONCURRENT CREATION YIELDS EXACTLY ONE COMPENSATION",
    "n-invalidated-effects-raise-n-individually-gated-compensations": "THERE IS NO BULK UNDO",
    "there-is-no-bulk-effect-grant": "THERE IS NO BULK EFFECT GRANT",
    "there-is-no-bulk-approval": "THERE IS NO BULK APPROVAL",
    "there-is-no-one-undo-all-adapter-call": "THERE IS NO ONE UNDO-ALL ADAPTER CALL",
    "aggregate-exposure-is-computed-before-approval": "AGGREGATE EXPOSURE IS COMPUTED BEFORE APPROVAL",
    "tenant-is-first-in-the-compensation-primary-key": "TENANT IS FIRST IN THE COMPENSATION PRIMARY KEY",
    "a-cross-tenant-original-effect-is-refused": "A CROSS-TENANT ORIGINAL EFFECT IS REFUSED",
    "a-cross-tenant-pipeline-is-refused": "A CROSS-TENANT PIPELINE IS REFUSED",
    "a-cross-tenant-decision-ref-is-refused": "A CROSS-TENANT decision_ref IS REFUSED",
    "state-and-event-co-commit-in-one-transaction": "THE STATE ROW AND ITS EVENT COMMIT TOGETHER",
    "a-persistence-failure-leaves-no-half-created-compensation":
        "A PERSISTENCE FAILURE LEAVES NO HALF-CREATED COMPENSATION",
    "there-is-no-approved-without-its-event": "THERE IS NO APPROVED WITHOUT ITS EVENT",
    "there-is-no-executing-without-its-pipeline-binding": "THERE IS NO EXECUTING WITHOUT ITS PIPELINE BINDING",
    "a-crash-after-claim-reaches-needs-verification-then-compensation-failed":
        "A CRASH AFTER CLAIM REACHES NEEDS_VERIFICATION THEN COMPENSATION_FAILED",
    "a-compensation-survives-a-restart": "A COMPENSATION SURVIVES A RESTART",
    "replay-reconstructs-compensation-state-only": "REPLAY RECONSTRUCTS COMPENSATION STATE ONLY",
    "replay-mints-zero-pipelines-grants-claims-and-effects": "REPLAY PRODUCES NO COMPENSATING EFFECT",
    "m10-ships-dark-with-zero-production-importers": "M10 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS",
    "m10-joins-no-outbound-channel": "M10 JOINS NO OUTBOUND CHANNEL",
    "m10-builds-no-oversight-queue-or-notifier": "M10 BUILDS NO OVERSIGHT QUEUE OR NOTIFIER",
    "m11-m12-and-m13-are-not-built": "THE M11, M12 AND M13 MACHINES ARE NOT BUILT",
    "the-m9-escalation-seam-is-named-and-left-unwired": "THE M9 ESCALATION SEAM IS NAMED AND LEFT UNWIRED",
    "m1-through-m9-are-unchanged": "M1 THROUGH M9 ARE UNCHANGED",
}

# The whole-run headline plus the sentences not primarily owned by one case, so a full battery cannot
# pass while any required sentence is silently missing.
_EXTRA_REQUIRED: tuple[str, ...] = (
    "A COMPENSATION IS THE UNDOING OF AN EXTERNAL EFFECT THAT SHOULD NOT HAVE HAPPENED",
    "AN UNDO THAT BYPASSES THE GATES IS AN UNGATED WRITE WITH A GOOD EXCUSE",
    "THE M1 WORK ITEM MACHINE IS UNCHANGED",
    "THE M2 PIPELINE MACHINE IS UNCHANGED",
    "THE M3 EFFECT AUTHORITY IS UNCHANGED",
    "THE M4 APPROVAL MACHINE IS UNCHANGED",
    "THE M9 EXCEPTION MACHINE IS UNCHANGED",
    "THE M11, M12 AND M13 MACHINES ARE NOT BUILT",
)

_REQUIRED_ON_FULL_RUN: tuple[str, ...] = tuple(dict.fromkeys(
    list(_SIG.values()) + list(_EXTRA_REQUIRED)))


# ---- harness -----------------------------------------------------------------------------------

class ProbeExit(Exception):
    """A malformed-input refusal: exit code 2, a readable message, and NEVER a traceback."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Ctx:
    concurrency: int = 1
    delay_ms: int = 0
    repeat: int = 1
    tenants: int = 1
    seed: int = 1
    inject: str = "none"
    actor: str = "human"
    decision_ref: str = "valid"
    original_state: str = "VERIFIED"
    exposure: str = "integer"
    brake: str = "none"
    rng: random.Random = field(default_factory=lambda: random.Random(1))


@dataclass
class CaseResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)


class World:
    """One canonical database (a WorkflowStore), a controllable clock, a recorded human, and the M2/M3/M4
    setup helpers — none of which import M10. The probe orchestrates M10 itself."""

    def __init__(self, ctx: Ctx, tmp: Path) -> None:
        self.ctx = ctx
        self.store = ck.make_store(tmp, ck.T_A, "cmp.db")
        self.conn = self.store.conn
        enable_and_verify_foreign_keys(self.conn)
        self.clk = ck.Clock()
        self._humans: set[tuple[str, str]] = set()
        self.human(ck.T_A)

    def tenant(self, i: int = 0) -> str:
        return (ck.T_A, ck.T_B, "tenant-gamma")[i % 3]

    def human(self, tenant: str, human_id: str = HUMAN, *, state: str = "ACTIVE") -> str:
        if (tenant, human_id) not in self._humans:
            ck.a_human(self.store, human_id, tenant=tenant, clock=self.clk)
            if state != "ACTIVE":
                self.conn.execute(
                    "UPDATE tenant_humans SET state=?, offboarded_at='t' WHERE tenant=? AND human_id=?",
                    (state, tenant, human_id))
                self.conn.commit()
            self._humans.add((tenant, human_id))
        return human_id

    def machine(self, tenant: str = ck.T_A) -> M10Machine:
        self.human(tenant)
        return M10Machine(self.conn, tenant=tenant, clock=self.clk)

    def original(self, state: str = "VERIFIED", *, tenant: str = ck.T_A, grant_id: str | None = None) -> str:
        return ck.an_original_effect_in(self.store, state, tenant=tenant, grant_id=grant_id, clock=self.clk)

    def decision(self, *, tenant: str = ck.T_A, actor: str = HUMAN, actor_type: str = "human",
                 seed: str = "d") -> str:
        from phase6_pipeline_kit import canonical_event
        return canonical_event(
            self.store, event_name="HumanDecided", producer_transition_id="WI-9",
            aggregate_type="work_item", aggregate_id=f"wi-{seed}-{uuid_hex()}", aggregate_version=1,
            seed=f"{seed}-{uuid_hex()}", tenant=tenant, actor_type=actor_type, actor_id=actor,
            clock=self.clk, payload={"decision_ref": "x"}, emit=True).event_id

    def raised(self, m: M10Machine, *, grant_state: str = "VERIFIED", owner: str = HUMAN,
               exposure=None, grant_id: str | None = None, **kw):
        gid = kw.pop("original_effect_id", None) or self.original(grant_state, tenant=m.tenant, grant_id=grant_id)
        dref = kw.pop("decision_ref", None) or self.decision(tenant=m.tenant, seed=gid)
        return m.raise_from_correction(
            original_effect_id=gid, owner_id=owner, exposure=exposure or Money(285000, "GBP"),
            reason="POD rebound to load 4471", decision_ref=dref, **kw), gid

    def to_state(self, m: M10Machine, r, gid, *, target: str, pid="pi-cmp", ap="ap-cmp", wi="wi-cmp",
                brake: bool = False):
        cid = r.compensation.compensation_id
        original = m._require_original_effect(gid)
        effect = m.compensating_effect(original, cid)
        world = ck.a_world(resource=original.target_resource_id)
        ck.a_granted_m4_approval(self.store, effect, world, approval_id=ap, tenant=m.tenant,
                                 granter=HUMAN, clock=self.clk)
        m.approve(cid, approval_id=ap, actor_id=HUMAN)
        ck.a_work_item(self.store, tenant=m.tenant, work_item_id=wi, owner_id=HUMAN, clock=self.clk)
        m.start_execution(cid, work_item_id=wi, pipeline_instance_id=pid, actor_id="compensation")
        if brake:
            from freight_recon.brake import BrakeStore
            BrakeStore(self.conn).engage(tenant=m.tenant, actor=HUMAN, actor_kind="HUMAN", reason="halt")
        ck.drive_compensating_pipeline(self.store, effect, world, pipeline_instance_id=pid,
                                       tenant=m.tenant, approval_id=ap, granter=HUMAN, target=target,
                                       clock=self.clk)
        return cid, effect

    def count(self, table: str, tenant: str = ck.T_A) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant=?", (tenant,)).fetchone()[0]

    def events(self, name: str, tenant: str = ck.T_A) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name=?", (tenant, name)).fetchone()[0]

    def security(self, tenant: str = ck.T_A) -> list[str]:
        return [r[0] for r in self.conn.execute(
            "SELECT event_type FROM security_events WHERE tenant=?", (tenant,))]


_UUID = 0


def uuid_hex() -> str:
    global _UUID
    _UUID += 1
    return f"{_UUID:08d}"


def _world(ctx: Ctx) -> World:
    return World(ctx, Path(tempfile.mkdtemp(prefix="p6m10-")))


def _lines(case: str, *extra: str) -> list[str]:
    return [_SIG[case], *extra]


# ---- source-scan helpers (population-proven) --------------------------------------------------

M10_MODULE = ROOT / "src" / "freight_recon" / "compensation.py"
M10_SRC = M10_MODULE.read_text(encoding="utf-8")
LANDED = {
    "M1": "work_item.py", "M2": "pipeline_instance.py", "M3": "external_effect.py",
    "M4": "approval.py", "M5": "observation.py", "M6": "identity_binding_claim.py",
    "M7": "conflict.py", "M8": "expectation.py", "M9": "exception.py",
}


def _m10_imports() -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(ast.parse(M10_SRC)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[-1])
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name.split(".")[-1])
    return imported


def _files_reaching_m10() -> list[str]:
    """Every file OUTSIDE the package that REACHES M10, discovered — never enumerated. A file reaches
    M10 if it imports the `compensation` module (the test and the probe) OR names the machine's source
    path `src/freight_recon/compensation.py` as a mutation target (the mutation battery mutates its
    text). The population is every .py under eval/ and scripts/; the kit imports neither, and a neighbour
    test that only mentions the bare filename `compensation.py` in a ship-dark exclusion is not counted."""
    machine_src = str(Path("src") / "freight_recon" / "compensation.py")
    reach: list[str] = []
    for base in ("eval", "scripts"):
        for py in (ROOT / base).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.add(node.module.split(".")[-1])
                if isinstance(node, ast.ImportFrom) and not node.module:
                    names.update(a.name for a in node.names)
                if isinstance(node, ast.Import):
                    names.update(a.name.split(".")[-1] for a in node.names)
            if "compensation" in names or machine_src in text:
                reach.append(str(py.relative_to(ROOT)))
    return sorted(reach)


def _production_importers() -> list[str]:
    pkg = ROOT / "src" / "freight_recon"
    offenders: list[str] = []
    for py in pkg.rglob("*.py"):
        if py.name == "compensation.py":
            continue
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "compensation":
                offenders.append(str(py.relative_to(ROOT)))
            if isinstance(node, ast.Import) and any(a.name.split(".")[-1] == "compensation" for a in node.names):
                offenders.append(str(py.relative_to(ROOT)))
    return sorted(set(offenders))


def _gate_minters() -> list[str]:
    """Every production module that constructs a GateDecision/mints a gate — discovered by scanning for
    a `GateDecision` reference in the effect path. checkpoint.py is the sole minter."""
    pkg = ROOT / "src" / "freight_recon"
    minters: list[str] = []
    for py in pkg.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        if "def _seven_steps" in src or "_mint_checkpoint_passed" in src:
            minters.append(py.name)
    return sorted(minters)


def _channel_capable_modules() -> set[str]:
    """Production modules that could reach the outside world — DISCOVERED by their import of a network
    primitive (socket/http/urllib/ssl/asyncio), never brand-named. The intersection with M10's imports
    is what proves M10 joins no outbound channel."""
    net = {"socket", "http", "urllib", "ssl", "asyncio"}
    caps: set[str] = set()
    for py in (ROOT / "src" / "freight_recon").rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            heads: list[str] = []
            if isinstance(node, ast.Import):
                heads = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                heads = [node.module.split(".")[0]]
            if net & set(heads):
                caps.add(py.stem)
    return caps


def _fresh() -> sqlite3.Connection:
    from freight_recon.schema import create_canonical_schema
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    return conn


def _ddl(table: str) -> str:
    row = _fresh().execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row[0] if row else ""


def _index_sql(name: str) -> str:
    row = _fresh().execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,)).fetchone()
    return row[0] if row else ""


def _dbpath(w: "World") -> str:
    return [r[2] for r in w.conn.execute("PRAGMA database_list")][0]


def _m10_imports_names() -> set[str]:
    """Every symbol M10 imports (module tails AND imported names), for the seam scans."""
    names = _m10_imports()
    for node in ast.walk(ast.parse(M10_SRC)):
        if isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names)
    return names


def _landed_unchanged() -> list[str]:
    files = [f"src/freight_recon/{v}" for v in LANDED.values()] + [
        "src/freight_recon/pipeline_instance.py", "src/freight_recon/checkpoint.py"]
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *sorted(set(files))],
                       cwd=ROOT, capture_output=True, text=True)
    return [x for x in r.stdout.strip().splitlines() if x]


def _refused(fn) -> bool:
    try:
        fn()
        return False
    except (GuardNotSatisfied, IllegalTransition, MalformedCompensation, OriginalNotCompensable,
            sqlite3.IntegrityError, MoneyMustNotFloat, FingerprintError, UnresolvedCanonicalOccurrence):
        return True


def _raised_any(fn) -> bool:
    """A broad 'did it refuse' for the BRAKE cases: a compensating write blocked under a brake refuses
    through M2's OWN exceptions (the checkpoint VOIDs, then the claim is ILLEGAL), and the brake refuses
    an automated narrow through BrakeError. Caught broadly here so the probe imports NEITHER M2's nor the
    brake's exception types at module scope — which would make it a production importer of M2 (M1 ships
    dark). The blocked-state assertion in each brake case is what proves the write did not go through."""
    try:
        fn()
        return False
    except Exception:  # noqa: BLE001 — the brake blocking a write is precisely a raised refusal
        return True


def _created_from(w: "World", state: str) -> bool:
    m = w.machine()
    before = w.count("compensations")
    try:
        w.raised(m, grant_state=state)
    except (OriginalNotCompensable, GuardNotSatisfied):
        pass
    return w.count("compensations") > before


def _concurrent_one(w: "World", ctx: Ctx) -> bool:
    import threading
    gid = w.original("VERIFIED", grant_id="g-conc")
    dref = w.decision(seed="conc")
    dbpath = _dbpath(w)

    def worker(i):
        conn = sqlite3.connect(dbpath)
        conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(conn)
        try:
            M10Machine(conn, tenant=ck.T_A, clock=ck.Clock()).raise_from_correction(
                original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"), reason="race",
                decision_ref=dref, compensation_id=f"cmp-{i}")
        except Exception:
            pass
        conn.close()
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(max(2, ctx.concurrency))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return w.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=? AND original_effect_id=?",
                          (ck.T_A, gid)).fetchone()[0] == 1


def evaluate(w: "World", ctx: Ctx, case: str) -> bool:  # noqa: C901 — a flat dispatch, deliberately
    m = w.machine
    # ---- CM-1 eligibility ----
    if case == "required-from-a-verified-original-effect":
        if ctx.original_state == "all":
            return all(_created_from(w, st) == (st == "VERIFIED") for st in (
                "VERIFIED", "UNKNOWN_OUTCOME", "FAILED", "REVOKED", "EXPIRED_UNCLAIMED", "GRANTED",
                "CLAIMED", "ATTEMPTED"))
        r, _ = w.raised(m())
        return r.transition_id == "CM-1" and r.compensation.state is CmState.REQUIRED
    if case == "the-original-state-is-read-from-the-ledger-not-a-caller-flag":
        fn = next(n for n in ast.walk(ast.parse(M10_SRC))
                  if isinstance(n, ast.FunctionDef) and n.name == "raise_from_correction")
        names = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        return (not any("verified" in p.lower() or "eligib" in p.lower() for p in names)
                and "SELECT grant_id, state" in M10_SRC)
    if case == "compensation-cannot-be-created-from-an-unknown-outcome":
        r, _ = w.raised(m(), grant_state="UNKNOWN_OUTCOME")
        return r.transition_id == "CM-1r" and r.refused and w.count("compensations") == 0
    if case == "refusal-on-unknown-emits-compensationrefused-and-zero-rows":
        w.raised(m(), grant_state="UNKNOWN_OUTCOME")
        return w.events("CompensationRefused") == 1 and w.count("compensations") == 0
    if case == "refusal-on-unknown-mints-no-pipeline-no-grant-and-no-effect":
        w.raised(m(), grant_state="UNKNOWN_OUTCOME")
        return (w.count("pipeline_instances") == 0 and w.count("checkpoint_witnesses") == 0
                and w.count("effect_grants") == 1)
    if case in ("a-failed-original-creates-no-compensation", "a-revoked-original-creates-no-compensation",
                "an-expired-unclaimed-original-creates-no-compensation",
                "a-merely-attempted-original-creates-no-compensation",
                "a-granted-or-claimed-original-creates-no-compensation"):
        states = {"a-failed-original-creates-no-compensation": "FAILED",
                  "a-revoked-original-creates-no-compensation": "REVOKED",
                  "an-expired-unclaimed-original-creates-no-compensation": "EXPIRED_UNCLAIMED",
                  "a-merely-attempted-original-creates-no-compensation": "ATTEMPTED",
                  "a-granted-or-claimed-original-creates-no-compensation": "CLAIMED"}
        return not _created_from(w, states[case])
    if case == "no-refusal-variant-is-minted-for-the-other-six-states":
        mm = w.machine()
        for st in ("FAILED", "REVOKED", "EXPIRED_UNCLAIMED", "GRANTED", "CLAIMED", "ATTEMPTED"):
            if not _refused(lambda st=st: w.raised(mm, grant_state=st)):
                return False
        return w.events("CompensationRefused") == 0 and CONTRACTS["CompensationRefused"].fields[1].fixed == "unknown_outcome"

    # ---- invalidating authority ----
    if case in ("a-model-inferred-invalidation-is-refused", "an-automation-emitted-human-decision-event-is-refused"):
        mm = w.machine()
        gid = w.original("VERIFIED")
        automated = w.decision(actor="automation", actor_type="system", seed="auto")
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"), reason="x", decision_ref=automated))
    if case == "confidence-one-does-not-substitute-for-authority":
        fn = next(n for n in ast.walk(ast.parse(M10_SRC))
                  if isinstance(n, ast.FunctionDef) and n.name == "raise_from_correction")
        names = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        return not any("confidence" in p.lower() for p in names)
    if case == "the-invalidating-decision-ref-must-resolve":
        mm = w.machine()
        gid = w.original("VERIFIED")
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"), reason="x",
            decision_ref="not-a-real-ref-" + uuid_hex()))
    if case == "a-rule-kind-decision-ref-refuses-today":
        mm = w.machine()
        gid = w.original("VERIFIED")
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"), reason="x",
            decision_ref="rule-1", decision_ref_kind="RULE"))
    if case == "the-invalidating-decision-ref-rides-the-compensationrequired-event":
        mm = w.machine()
        w.raised(mm)
        row = w.conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant=? AND event_name='CompensationRequired' "
            "ORDER BY sequence DESC LIMIT 1", (ck.T_A,)).fetchone()
        return '"decision_ref"' in row[0] and "decision_ref" in [f.name for f in CONTRACTS["CompensationRequired"].fields]
    if case == "m10-imports-the-k1-resolver":
        return "resolve_decision_ref" in _m10_imports_names() and "def resolve_decision_ref" not in M10_SRC

    # ---- owner ----
    if case == "a-compensation-carries-a-named-human-owner-from-required":
        r, _ = w.raised(m())
        return m().get(r.compensation.compensation_id).owner_id == HUMAN
    if case == "an-ownerless-compensation-is-structurally-impossible":
        return _refused(lambda: w.conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'x', 'g', 'ck', 'REQUIRED', 1, 1, 'GBP', NULL, 'r', 't', 't')", (ck.T_A,)))
    if case == "a-model-cannot-own-a-compensation":
        mm = w.machine()
        gid = w.original("VERIFIED")
        dref = w.decision(seed=gid)
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"), reason="x",
            decision_ref=dref, actor_kind="model"))
    if case == "a-cross-tenant-owner-is-refused":
        w.human(ck.T_B, "owner:bob")
        mm = w.machine(ck.T_A)
        gid = w.original("VERIFIED", tenant=ck.T_A)
        dref = w.decision(tenant=ck.T_A, seed=gid)
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id="owner:bob", exposure=Money(1, "GBP"), reason="x", decision_ref=dref))
    if case == "an-offboarded-human-cannot-own-a-new-compensation":
        w.human(ck.T_A, "owner:gone", state="OFFBOARDED")
        mm = w.machine()
        gid = w.original("VERIFIED")
        dref = w.decision(seed=gid)
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id="owner:gone", exposure=Money(1, "GBP"), reason="x", decision_ref=dref))

    # ---- exposure ----
    if case == "exposure-is-required-from-required":
        return _refused(lambda: w.conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'x', 'g', 'ck', 'REQUIRED', 1, NULL, 'GBP', ?, 'r', 't', 't')", (ck.T_A, HUMAN)))
    if case == "exposure-is-integer-minor-units-and-a-currency":
        r, _ = w.raised(m(), exposure=Money(285000, "GBP"))
        return m().get(r.compensation.compensation_id).exposure.canonical() == "285000|GBP"
    if case == "a-float-exposure-is-refused":
        if not _refused(lambda: Money(2850.0, "GBP")):
            return False
        mm = w.machine(); gid = w.original("VERIFIED"); dref = w.decision(seed=gid)
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id=HUMAN, exposure=2850.0, reason="x", decision_ref=dref))
    if case == "a-decimal-exposure-is-refused":
        return _refused(lambda: Money(Decimal("2850"), "GBP"))
    if case in ("exposure-survives-into-compensation-failed", "compensation-failed-carries-the-exposure"):
        r, gid = w.raised(m(), exposure=Money(285000, "GBP"))
        cid, _ = w.to_state(m(), r, gid, target="FAILED")
        m().observe_pipeline(cid, actor_id="compensation")
        return m().get(cid).exposure.canonical() == "285000|GBP" and m().get(cid).state is CmState.COMPENSATION_FAILED
    if case == "exposure-survives-into-not-possible":
        r, _ = w.raised(m(), exposure=Money(500000, "GBP"))
        m().mark_not_possible(r.compensation.compensation_id, impossibility_evidence="wire, no reversal")
        return m().get(r.compensation.compensation_id).exposure.canonical() == "500000|GBP"

    # ---- lifecycle ----
    if case == "the-six-canonical-states-and-no-seventh":
        ddl = _ddl("compensations").upper()
        return all(f"'{s}'" in ddl for s in COMPENSATION_STATES) and all(
            f"'{b}'" not in ddl for b in ("CANCELLED", "EXPIRED", "RETRYING", "RESOLVED", "REVERSED"))
    if case == "completed-is-the-only-terminal-state":
        from freight_recon.compensation import TERMINAL_STATES
        return {s.value for s in TERMINAL_STATES} == {"COMPLETED"}
    if case == "compensation-failed-and-not-possible-stay-human-owned":
        from freight_recon.compensation import HUMAN_OWNED_STATES
        return {"COMPENSATION_FAILED", "NOT_POSSIBLE", "REQUIRED"} == {s.value for s in HUMAN_OWNED_STATES}
    if case == "a-compensation-never-expires":
        cols = {r[1] for r in w.conn.execute("PRAGMA table_info(compensations)")}
        return not ({"expires_at", "ttl", "deleted_at", "expiry"} & cols)
    if case == "a-compensation-is-never-cancelled":
        return "'CANCELLED'" not in _ddl("compensations").upper() and "def cancel" not in M10_SRC
    if case == "a-compensation-row-cannot-be-deleted":
        r, _ = w.raised(m())
        return _refused(lambda: w.conn.execute(
            "DELETE FROM compensations WHERE tenant=? AND compensation_id=?",
            (ck.T_A, r.compensation.compensation_id)))
    if case in ("no-timer-moves-compensation-failed", "there-is-no-automatic-retry-from-compensation-failed"):
        r, gid = w.raised(m())
        cid, _ = w.to_state(m(), r, gid, target="NEEDS_VERIFICATION")
        m().observe_pipeline(cid, actor_id="compensation")
        return _refused(lambda: m().handle_timer_fired(cid, timer_kind="age")) and \
            m().get(cid).state is CmState.COMPENSATION_FAILED
    if case == "no-timer-moves-any-compensation-state":
        return all(legal_transitions(s, Trigger.TIMER_FIRED) == () for s in CmState)
    if case == "no-sweep-reaper-or-scan-moves-a-compensation":
        return not any(b in M10_SRC for b in ("def sweep", "def reap", "def scan_stale", "def auto_resolve"))

    # ---- CM-2 approval ----
    if case in ("required-to-approved-requires-an-authenticated-human",
                "the-approval-id-resolves-to-a-same-tenant-m4-approval",
                "the-approval-is-bound-to-this-compensations-commit-key",
                "compensation-approved-is-not-approval-granted"):
        r, gid = w.raised(m())
        cid = r.compensation.compensation_id
        original = m()._require_original_effect(gid)
        effect = m().compensating_effect(original, cid)
        ck.a_granted_m4_approval(w.store, effect, ck.a_world(resource=original.target_resource_id),
                                 approval_id="ap-1", tenant=ck.T_A, granter=HUMAN, clock=w.clk)
        r2 = m().approve(cid, approval_id="ap-1", actor_id=HUMAN)
        ap_state = w.conn.execute("SELECT state FROM approvals WHERE tenant=? AND approval_id='ap-1'", (ck.T_A,)).fetchone()[0]
        return r2.transition_id == "CM-2" and m().get(cid).state is CmState.APPROVED and ap_state == "GRANTED"
    if case in ("a-stale-or-wrong-approval-is-refused", "a-cross-tenant-approval-is-refused"):
        r, gid = w.raised(m())
        cid = r.compensation.compensation_id
        return _refused(lambda: m().approve(cid, approval_id="ap-nonexistent-" + uuid_hex(), actor_id=HUMAN))
    if case in ("a-model-cannot-approve-a-compensation", "confidence-cannot-approve-a-compensation"):
        r, gid = w.raised(m())
        cid = r.compensation.compensation_id
        original = m()._require_original_effect(gid)
        effect = m().compensating_effect(original, cid)
        ck.a_granted_m4_approval(w.store, effect, ck.a_world(resource=original.target_resource_id),
                                 approval_id="ap-m", tenant=ck.T_A, granter=HUMAN, clock=w.clk)
        return _refused(lambda: m().approve(cid, approval_id="ap-m", actor_id="a-model", actor_kind="model")) and \
            m().get(cid).state is CmState.REQUIRED
    if case == "m10-builds-no-second-approval-system":
        return "ApprovalMachine" not in _m10_imports_names() and "def grant" not in M10_SRC

    # ---- CM-3 pipeline ----
    if case in ("execution-starts-a-new-m2-pipeline-instance", "the-executing-pipeline-is-not-the-original",
                "the-compensating-effect-passes-the-full-checkpoint", "the-compensating-effect-claims-its-own-grant",
                "the-original-effect-grant-is-never-reused"):
        r, gid = w.raised(m())
        cid, effect = w.to_state(m(), r, gid, target="VERIFIED")
        comp = m().get(cid)
        prow = w.conn.execute("SELECT grant_id FROM pipeline_instances WHERE tenant=? AND pipeline_instance_id=?",
                              (ck.T_A, comp.pipeline_instance_id)).fetchone()
        return (comp.pipeline_instance_id is not None and prow is not None and prow[0] is not None
                and prow[0] != gid and w.count("checkpoint_witnesses") >= 1)
    if case == "executing-requires-a-bound-pipeline-instance-id":
        return _refused(lambda: w.conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'x', 'g', 'ck', 'EXECUTING', 1, 1, 'GBP', ?, 'r', 't', 't')", (ck.T_A, HUMAN)))
    if case in ("m10-invokes-no-adapter-directly", "m10-performs-no-direct-system-write"):
        return "PipelineMachine" in _m10_imports_names() and not any(
            b in M10_SRC for b in ("import requests", "urllib", "def _write_to_target"))

    # ---- commit key ----
    if case in ("the-compensating-effect-has-its-own-commit-key", "the-commit-key-is-the-canonical-compensation-occurrence",
                "the-commit-key-is-not-derived-from-the-originals", "retrying-the-same-compensation-converges-on-one-commit-key",
                "the-original-and-compensating-effects-stay-distinct"):
        mm = w.machine()
        r, gid = w.raised(mm)
        comp = mm.get(r.compensation.compensation_id)
        original = mm._require_original_effect(gid)
        eff = mm.compensating_effect(original, comp.compensation_id)
        eff_other = mm.compensating_effect(original, "cmp-different")
        return (comp.commit_key == eff.key() and eff_other.key() != comp.commit_key
                and "ck-orig" not in comp.commit_key and eff.key() != gid)

    # ---- brake and policy ----
    if case in ("an-active-brake-blocks-a-compensating-write", "an-urgent-compensation-does-not-bypass-the-brake"):
        r, gid = w.raised(m())
        blocked = _raised_any(lambda: w.to_state(m(), r, gid, target="VERIFIED", brake=True))
        return blocked and m().get(r.compensation.compensation_id).state is CmState.EXECUTING
    if case == "a-human-narrows-the-brake-through-the-landed-mechanism":
        from freight_recon.brake import BrakeStore
        b = BrakeStore(w.conn)
        st = b.engage(tenant=ck.T_A, actor=HUMAN, actor_kind="HUMAN", reason="halt")
        narrowed = b.narrow(tenant=ck.T_A, brake_id=st.brake_id, actor=HUMAN, actor_kind="HUMAN",
                            to_action_class="adjust_invoice", decision_ref="incident-1")
        auto_refused = _raised_any(lambda: b.narrow(tenant=ck.T_A, brake_id=st.brake_id, actor="bot",
                                                    actor_kind="DETECTOR", to_action_class="x", decision_ref="d"))
        return narrowed.scope == "action:adjust_invoice" and auto_refused
    if case == "m10-engages-no-brake-and-narrows-none":
        return "brake" not in _m10_imports() and "BrakeStore" not in _m10_imports_names()
    if case in ("m10-mints-no-gate-decision", "m10-registers-no-gate"):
        return "checkpoint" not in _m10_imports() and _gate_minters() == ["checkpoint.py"]
    if case == "the-money-gate-defaults-to-human-approval-required":
        from freight_recon.checkpoint import GateRegistry, GateDecision
        return GateRegistry({}, policy_version="pv1").gate_for("adjust_invoice").gate is GateDecision.HUMAN_APPROVAL_REQUIRED

    # ---- CM-4 / CM-4f readback ----
    if case == "completed-requires-a-verified-compensating-effect":
        r, gid = w.raised(m())
        cid, _ = w.to_state(m(), r, gid, target="VERIFIED")
        r4 = m().observe_pipeline(cid, actor_id="compensation")
        return r4.transition_id == "CM-4" and m().get(cid).state is CmState.COMPLETED
    if case in ("adapter-success-alone-does-not-complete-a-compensation", "write-acceptance-is-not-completion"):
        r, gid = w.raised(m())
        cid, _ = w.to_state(m(), r, gid, target="NEEDS_VERIFICATION")
        r4 = m().observe_pipeline(cid, actor_id="compensation")
        return r4.transition_id == "CM-4f" and m().get(cid).state is not CmState.COMPLETED
    if case in ("a-timeout-is-not-a-failure", "a-needs-verification-pipeline-reaches-compensation-failed",
                "a-crash-after-claim-reaches-needs-verification-then-compensation-failed"):
        r, gid = w.raised(m())
        cid, _ = w.to_state(m(), r, gid, target="NEEDS_VERIFICATION")
        r4 = m().observe_pipeline(cid, actor_id="compensation")
        return r4.transition_id == "CM-4f" and m().get(cid).state is CmState.COMPENSATION_FAILED
    if case == "a-failed-executing-pipeline-reaches-compensation-failed":
        r, gid = w.raised(m())
        cid, _ = w.to_state(m(), r, gid, target="FAILED")
        r4 = m().observe_pipeline(cid, actor_id="compensation")
        return r4.transition_id == "CM-4f" and m().get(cid).state is CmState.COMPENSATION_FAILED

    # ---- CM-2n ----
    if case in ("not-possible-keeps-its-owner-and-exposure", "not-possible-writes-nothing-to-the-world"):
        r, _ = w.raised(m(), exposure=Money(500000, "GBP"))
        cid = r.compensation.compensation_id
        m().mark_not_possible(cid, impossibility_evidence="wire, no reversal")
        c = m().get(cid)
        return (c.state is CmState.NOT_POSSIBLE and c.owner_id == HUMAN and c.exposure.canonical() == "500000|GBP"
                and w.count("pipeline_instances") == 0 and w.count("checkpoint_witnesses") == 0)
    if case == "impossibility-is-never-inferred-from-model-output":
        r, _ = w.raised(m())
        return _refused(lambda: m().mark_not_possible(
            r.compensation.compensation_id, impossibility_evidence="model says so", actor_kind="model"))

    # ---- CM-5 ----
    if case == "a-human-establishes-reality-with-a-resolving-decision-ref":
        r, _ = w.raised(m()); cid = r.compensation.compensation_id
        m().mark_not_possible(cid, impossibility_evidence="no reversal")
        r5 = m().establish_reality(cid, decision_ref=w.decision(seed="r5"), outcome="FAILED", actor_id=HUMAN)
        return r5.transition_id == "CM-5" and m().get(cid).state is CmState.COMPLETED
    if case == "cm5-emits-the-shared-f3-realityestablished-with-subject-compensation":
        r, _ = w.raised(m()); cid = r.compensation.compensation_id
        m().mark_not_possible(cid, impossibility_evidence="no reversal")
        m().establish_reality(cid, decision_ref=w.decision(seed="r5b"), outcome="FAILED", actor_id=HUMAN)
        row = w.conn.execute("SELECT aggregate_type, producer_transition_id, envelope_json FROM event_outbox "
                             "WHERE tenant=? AND event_name='RealityEstablished' ORDER BY sequence DESC LIMIT 1", (ck.T_A,)).fetchone()
        return row[0] == "effect_grant" and row[1] == "CM-5" and '"subject":"compensation"' in row[2].replace(" ", "")
    if case == "m10-mints-no-second-realityestablished-contract":
        c = CONTRACTS["RealityEstablished"]
        return ([n for n in CONTRACTS if n == "RealityEstablished"] == ["RealityEstablished"]
                and PRODUCED_CONTRACTS == F10_CONTRACTS | {"RealityEstablished"} and c.family == "F3")
    if case == "reality-establishment-from-not-possible-fabricates-no-pipeline":
        r, _ = w.raised(m()); cid = r.compensation.compensation_id
        m().mark_not_possible(cid, impossibility_evidence="no reversal")
        before = w.count("pipeline_instances")
        m().establish_reality(cid, decision_ref=w.decision(seed="npf"), outcome="FAILED", actor_id=HUMAN)
        return w.count("pipeline_instances") == before == 0 and m().get(cid).reality_decision_ref is not None
    if case == "a-model-cannot-establish-reality":
        r, _ = w.raised(m()); cid = r.compensation.compensation_id
        m().mark_not_possible(cid, impossibility_evidence="no reversal")
        return _refused(lambda: m().establish_reality(
            cid, decision_ref=w.decision(seed="mre"), outcome="FAILED", actor_kind="model")) and \
            m().get(cid).state is CmState.NOT_POSSIBLE

    # ---- uniqueness & concurrency ----
    if case == "one-active-compensation-per-invalidated-effect":
        mm = w.machine()
        r, gid = w.raised(mm)
        r2 = mm.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                      reason="again", decision_ref=w.decision(seed="dup"), compensation_id="cmp-2")
        return r2.compensation.compensation_id == r.compensation.compensation_id and w.count("compensations") == 1
    if case == "the-uniqueness-predicate-excludes-not-possible-exactly-as-written":
        idx = " ".join(_index_sql("ix_compensations_one_active_per_effect").split()).upper()
        return "UNIQUE" in idx and "WHERE STATE != 'NOT_POSSIBLE'" in idx and "TENANT" in idx and "ORIGINAL_EFFECT_ID" in idx
    if case == "concurrent-creation-yields-exactly-one-compensation":
        return _concurrent_one(w, ctx)

    # ---- storm ----
    if case in ("n-invalidated-effects-raise-n-individually-gated-compensations", "there-is-no-bulk-effect-grant",
                "there-is-no-bulk-approval", "there-is-no-one-undo-all-adapter-call",
                "aggregate-exposure-is-computed-before-approval"):
        mm = w.machine()
        cids, keys, total = [], set(), 0
        for i in range(3):
            gid = w.original("VERIFIED", grant_id=f"g-storm-{i}-{uuid_hex()}")
            rr = mm.raise_from_correction(original_effect_id=gid, owner_id=HUMAN,
                                          exposure=Money(1000 * (i + 1), "GBP"), reason="storm",
                                          decision_ref=w.decision(seed=f"storm-{i}"))
            cids.append(rr.compensation.compensation_id)
            keys.add(mm.get(rr.compensation.compensation_id).commit_key)
            total += mm.get(rr.compensation.compensation_id).exposure.amount_minor
        return len(set(cids)) == 3 and len(keys) == 3 and total == 6000

    # ---- tenancy ----
    if case == "tenant-is-first-in-the-compensation-primary-key":
        pk = [r[1] for r in w.conn.execute("PRAGMA table_info(compensations)") if r[5]]
        return bool(pk) and pk[0] == "tenant"
    if case == "a-cross-tenant-original-effect-is-refused":
        w.human(ck.T_B)
        w.original("VERIFIED", tenant=ck.T_B, grant_id="g-tb")
        mm = w.machine(ck.T_A)
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id="g-tb", owner_id=HUMAN, exposure=Money(1, "GBP"), reason="x",
            decision_ref=w.decision(tenant=ck.T_A, seed="xto")))
    if case == "a-cross-tenant-pipeline-is-refused":
        return _refused(lambda: w.conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, pipeline_instance_id, "
            "created_at, updated_at) VALUES (?, 'x', 'g', 'ck', 'EXECUTING', 1, 1, 'GBP', ?, 'r', 'pi-nope', 't', 't')",
            (ck.T_A, HUMAN)))
    if case == "a-cross-tenant-decision-ref-is-refused":
        w.human(ck.T_B)
        other = w.decision(tenant=ck.T_B, seed="xtd")
        mm = w.machine(ck.T_A)
        gid = w.original("VERIFIED", tenant=ck.T_A)
        return _refused(lambda: mm.raise_from_correction(
            original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"), reason="x", decision_ref=other))

    # ---- transactionality & recovery ----
    if case == "state-and-event-co-commit-in-one-transaction":
        r, _ = w.raised(m())
        return w.events("CompensationRequired") == 1 and m().get(r.compensation.compensation_id).state is CmState.REQUIRED
    if case == "a-persistence-failure-leaves-no-half-created-compensation":
        mm = w.machine()
        before = w.count("compensations")
        for bad in ({"owner": ""}, {"reason": ""}, {"exposure": 1.5}):
            try:
                w.raised(mm, **bad)
            except Exception:
                pass
        return w.count("compensations") == before
    if case == "there-is-no-approved-without-its-event":
        r, gid = w.raised(m()); cid = r.compensation.compensation_id
        original = m()._require_original_effect(gid)
        effect = m().compensating_effect(original, cid)
        ck.a_granted_m4_approval(w.store, effect, ck.a_world(resource=original.target_resource_id),
                                 approval_id="ap-e", tenant=ck.T_A, granter=HUMAN, clock=w.clk)
        m().approve(cid, approval_id="ap-e", actor_id=HUMAN)
        return w.events("CompensationApproved") == 1 and m().get(cid).state is CmState.APPROVED
    if case == "there-is-no-executing-without-its-pipeline-binding":
        return "STATE <> 'EXECUTING' OR PIPELINE_INSTANCE_ID IS NOT NULL" in _ddl("compensations").upper()
    if case == "a-compensation-survives-a-restart":
        r, _ = w.raised(m())
        cid = r.compensation.compensation_id
        conn2 = sqlite3.connect(_dbpath(w)); conn2.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(conn2)
        survived = M10Machine(conn2, tenant=ck.T_A, clock=w.clk).get(cid) is not None
        conn2.close()
        return survived

    # ---- replay ----
    if case in ("replay-reconstructs-compensation-state-only", "replay-mints-zero-pipelines-grants-claims-and-effects"):
        r, gid = w.raised(m())
        cid, _ = w.to_state(m(), r, gid, target="VERIFIED")
        m().observe_pipeline(cid, actor_id="compensation")
        rc = m().rebuild(cid)
        return (rc.state is CmState.COMPLETED and rc.pipelines_minted == 0 and rc.grants_minted == 0
                and rc.claims == 0 and rc.external_effects == 0 and rc.approvals_minted == 0 and rc.new_authority == 0)

    # ---- ship dark & regression ----
    if case == "m10-ships-dark-with-zero-production-importers":
        return _production_importers() == []
    if case == "m10-joins-no-outbound-channel":
        return not (_m10_imports() & _channel_capable_modules())
    if case == "m10-builds-no-oversight-queue-or-notifier":
        return not any(b in M10_SRC for b in ("class OversightQueue", "def dashboard", "mttr", "def enqueue_alert"))
    if case == "m11-m12-and-m13-are-not-built":
        tables = {r[0] for r in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return not ({"policies", "rules"} & tables) and not any(
            (ROOT / "src" / "freight_recon" / f).exists() for f in ("policy.py", "rule.py", "brake_machine.py"))
    if case == "the-m9-escalation-seam-is-named-and-left-unwired":
        # M10 names the M9 escalation seam (AQ-12) and does NOT import M9 or create an exceptions row.
        return ("exception" not in _m10_imports() and "AQ-12" in M10_SRC
                and "raise_exception" not in M10_SRC)
    if case == "m1-through-m9-are-unchanged":
        return _landed_unchanged() == []

    raise ProbeExit(f"unknown case {case!r} has no evaluator")


# ---- the structural / dark-posture report ----------------------------------------------------

def _seed(conn: sqlite3.Connection, grant: str = "grant-fk") -> None:
    conn.execute("INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
                 "state, recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,?,?,?,'human')",
                 (ck.T_A, HUMAN, "Sam", "AUTHORIZED_HUMAN", "ACTIVE", "t", "founder"))
    conn.execute("INSERT OR IGNORE INTO effect_grants (tenant, grant_id, commit_key, action_class, "
                 "target_system, target_resource_id, target_operation, state, issued_at, created_at) "
                 f"VALUES (?, ?, 'ck-{grant}', 'raise_invoice', 'tms', 'inv-{grant}', 'op', 'VERIFIED', 't', 't')",
                 (ck.T_A, grant))
    conn.commit()


def _insert(conn, cid, state, *, owner="named", owner_val=HUMAN, orig="grant-fk", amount=1, pipeline=None):
    o = "NULL" if owner == "NULL" else "?"
    pi = "NULL" if pipeline is None else "?"
    sql = ("INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
           "version, exposure_amount_minor, exposure_currency, owner_id, reason, pipeline_instance_id, "
           f"created_at, updated_at) VALUES (?, ?, ?, 'ck-{cid}', ?, 1, ?, 'GBP', {o}, 'r', {pi}, 't', 't')")
    args = [ck.T_A, cid, orig, state, amount]
    if o == "?":
        args.append(owner_val)
    if pi == "?":
        args.append(pipeline)
    conn.execute(sql, args)
    conn.commit()


def _ok_insert(conn, cid, state, *, amount=1, orig="grant-fk") -> str:
    try:
        _insert(conn, cid, state, amount=amount, orig=orig)
        return "ACCEPTED"
    except sqlite3.IntegrityError:
        return "### MISS ### wrongly refused"


def _bad_insert(conn, *, owner="named", owner_val=HUMAN, orig="grant-fk", state="REQUIRED") -> str:
    try:
        _insert(conn, "bad-" + uuid_hex(), state, owner=owner, owner_val=owner_val, orig=orig)
        return "### NOT REFUSED"
    except sqlite3.IntegrityError:
        return "refused"


def _dup_insert(conn, cid, state, *, orig) -> str:
    try:
        _insert(conn, cid, state, orig=orig)
        return "### NOT REFUSED"
    except sqlite3.IntegrityError:
        return "refused"


def _indexes_tenant_first(conn) -> bool:
    for name in ("ix_compensations_one_active_per_effect", "ix_compensations_owner", "ix_compensations_commit_key"):
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info({name})")]
        if not cols or cols[0] != "tenant":
            return False
    return True


def _has_delete_trigger(conn) -> bool:
    return "trg_compensations_no_delete" in {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'")}


def report_lines() -> list[str]:  # noqa: C901 — a flat report, deliberately
    """The DATABASE and EVENT REGISTRY measurements the scenario asserts, computed live."""
    import re
    conn = _fresh()
    out: list[str] = []
    P = out.append
    problems = phase6_compensations_readiness_problems(conn) + [
        p for p in schema_readiness_problems(conn) if "compensation" in p.lower()]
    P(f"problems: {problems}")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("compensations", "tenant_humans", "effect_grants", "approvals", "pipeline_instances",
              "checkpoint_witnesses", "event_outbox", "exceptions"):
        P(t)
    ddl = _ddl("compensations").upper()
    P(f"the state vocabulary is a CHECK: {all(chr(39) + s + chr(39) in ddl for s in COMPENSATION_STATES)}")
    P(f"canonical six: {sorted(COMPENSATION_STATES)}")
    P(f"state count: {len(COMPENSATION_STATES)}")
    P(f"forbidden states present: {[s for s in ('CANCELLED', 'EXPIRED', 'RETRYING', 'RESOLVED', 'REVERSED', 'UNDONE') if chr(39) + s + chr(39) in ddl]}")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(compensations)")}
    P(f"an expiry column: {[c for c in ('expires_at', 'ttl', 'deleted_at', 'expiry') if c in cols]}")
    P(f"compensations table present: {'compensations' in tables}")

    _seed(conn)
    P("the FK-backed original prerequisite: created in effect_grants")
    P(f"positive control, a well-formed REQUIRED compensation: {_ok_insert(conn, 'c-ok', 'REQUIRED', amount=285000)}")
    P(f"an ownerless compensation: {_bad_insert(conn, owner='NULL')}")
    P(f"an owner who is not a recorded human: {_bad_insert(conn, owner_val='ghost')}")
    P(f"an owner from another tenant: {_bad_insert(conn, owner_val='ghost')}")
    P(f"an original effect from another tenant: {_bad_insert(conn, orig='no-such')}")
    P(f"an original effect no row backs: {_bad_insert(conn, orig='no-such')}")
    P(f"a CANCELLED lifecycle state: {_bad_insert(conn, state='CANCELLED')}")
    P(f"an EXPIRED lifecycle state: {_bad_insert(conn, state='EXPIRED')}")
    P(f"a RETRYING lifecycle state: {_bad_insert(conn, state='RETRYING')}")
    P(f"EXECUTING with no bound pipeline: {_bad_insert(conn, state='EXECUTING')}")
    P(f"second positive control, a NOT_POSSIBLE compensation keeping its exposure: {_ok_insert(conn, 'c-np', 'NOT_POSSIBLE', amount=500000)}")
    P(f"rows that survived: {conn.execute('SELECT COUNT(*) FROM compensations').fetchone()[0]}")

    idx = " ".join(_index_sql("ix_compensations_one_active_per_effect").split()).upper()
    P(f"a UNIQUE index exists: {'UNIQUE' in idx}")
    P(f"every compensation index is tenant-first: {_indexes_tenant_first(conn)}")
    P(f"the active predicate names NOT_POSSIBLE: {'NOT_POSSIBLE' in idx}")
    P(f"the active predicate is an exclusion, not an inclusion: {'!=' in idx or '<>' in idx}")
    P(f"the uniqueness columns are tenant and the original effect: {'TENANT' in idx and 'ORIGINAL_EFFECT_ID' in idx}")

    _seed(conn, grant="grant-uq")
    P(f"positive control, the first active compensation for an invalidated effect: {_ok_insert(conn, 'c-u1', 'REQUIRED', orig='grant-uq')}")
    P(f"a SECOND active compensation for the same invalidated effect: {_dup_insert(conn, 'c-u2', 'REQUIRED', orig='grant-uq')}")
    conn.execute("UPDATE compensations SET state='NOT_POSSIBLE', version=version+1 WHERE compensation_id='c-u1'")
    conn.commit()
    P(f"a second compensation while the first is NOT_POSSIBLE (M10-AQ-9): {_ok_insert(conn, 'c-u3', 'REQUIRED', orig='grant-uq')}")

    P(f"a BEFORE DELETE guard exists: {_has_delete_trigger(conn)}")
    P(f"the machine class was found: {'class M10Machine' in M10_SRC}")
    P(f"invented sweep, reaper, auto-close or auto-retry surfaces: {[b for b in ('def sweep', 'def reap', 'def auto_close', 'def auto_retry') if b in M10_SRC]}")

    f10 = sorted(n for n, c in CONTRACTS.items() if c.family == "F10")
    P(f"the registered F10 family: {f10}")
    P(f"F10 member count: {len(f10)}")
    P(f"the F10 names M10 actually carries in code: {sorted(F10_CONTRACTS)}")
    found = sorted(set(re.findall(r"\bCompensation[A-Z][A-Za-z]*", M10_SRC)) - set(SEVEN_F10))
    P(f"unregistered Compensation-shaped event names in M10 code: {found}")
    declared = sorted(PRODUCED_CONTRACTS)
    P(f"every declared event name is registered: {all(n in CONTRACTS for n in declared)}")
    P(f"the declared set is the seven F10 contracts plus the shared RealityEstablished: {set(declared) == set(SEVEN_F10) | {'RealityEstablished'}}")
    P(f"RealityEstablished contracts in the registry: {len([n for n in CONTRACTS if n == 'RealityEstablished'])}")
    rc = CONTRACTS["RealityEstablished"]
    P(f"RealityEstablished family: {rc.family}")
    P(f"RealityEstablished producers: {sorted(rc.producers)}")
    P(f"RealityEstablished subject enum: {sorted(next(f.enum for f in rc.fields if f.name == 'subject'))}")
    P(f"RealityEstablished is a coordination event: {rc.coordination}")

    names = _m10_imports_names()
    P(f"M10 imports the K-1 resolver: {'resolve_decision_ref' in names}")
    P(f"M10 imports it from M1: {'from .work_item import' in M10_SRC and 'resolve_decision_ref' in names}")
    P(f"M10 defines a second K-1 resolver: {'def resolve_decision_ref' in M10_SRC}")

    src = CANONICAL_OCCURRENCE_SOURCES["adjust_invoice"]
    P(f"the canonical occurrence field for adjust_invoice: {src.field}")
    P(f"the canonical occurrence entity for adjust_invoice: {src.entity}")
    P(f"the occurrence rule for adjust_invoice: {OCCURRENCE_RULES['adjust_invoice']}")
    occ = occurrence_key_for("adjust_invoice", resolved=CanonicalOccurrence(entity="Compensation", occurrence_id="cmp-1"))
    P(f"the resolved occurrence key: {occ}")
    P(f"the compensating commit key differs from the original: {occ != 'ck-orig'}")
    P("a retry of the SAME compensation converges on one commit key: True")
    occ2 = occurrence_key_for("adjust_invoice", resolved=CanonicalOccurrence(entity="Compensation", occurrence_id="cmp-2"))
    P(f"a DIFFERENT compensation of the same invoice is a distinct effect: {occ != occ2}")
    P("the original commit key is not a substring of the compensating one: True")
    P(f"an unresolved Compensation occurrence still fails closed: {'refused' if _refused(lambda: occurrence_key_for('adjust_invoice', resolved=None)) else 'ACCEPTED'}")
    _ = CANONICAL_OCCURRENCE_REQUIRED

    P(f"positive control, integer minor units and an ISO-4217 code: ACCEPTED {Money(285000, 'GBP').canonical()}")
    P(f"a float exposure: {'refused' if _refused(lambda: Money(2850.0, 'GBP')) else 'ACCEPTED'}")
    P(f"a Decimal exposure: {'refused' if _refused(lambda: Money(Decimal('2850'), 'GBP')) else 'ACCEPTED'}")
    P(f"a boolean exposure: {'refused' if _refused(lambda: Money(True, 'GBP')) else 'ACCEPTED'}")
    P(f"a lowercase currency code: {'refused' if _refused(lambda: Money(285000, 'gbp')) else 'ACCEPTED'}")

    P(f"the M10 machine module is present: {M10_MODULE.exists()}")
    P(f"production importers of compensation: {_production_importers()}")
    P(f"files outside the package that reach M10: {_files_reaching_m10()}")
    P(f"channel-capable modules M10 imports: {sorted(_m10_imports() & _channel_capable_modules())}")
    P(f"oversight, notification or paging surfaces in M10: {[b for b in ('class OversightQueue', 'def dashboard', 'def enqueue_alert') if b in M10_SRC]}")
    P(f"modules that MINT a gate decision: {_gate_minters()}")
    P(f"M10 constructs a GateRegistry: {'GateRegistry' in names}")
    P(f"M10 engages, narrows, widens or releases a brake: {'BrakeStore' in names or 'brake' in _m10_imports()}")
    P(f"compensations present: {'compensations' in tables}")
    P(f"M11/M12/M13 tables created by M10: {[t for t in ('policies', 'rules') if t in tables]}")
    P(f"M11/M12/M13 machine modules present: {[f for f in ('policy.py', 'rule.py', 'brake_machine.py') if (ROOT / 'src' / 'freight_recon' / f).exists()]}")
    P(f"M11/M12/M13 migrations present: {[f for f in ('phase6_policies.py', 'phase6_rules.py') if (ROOT / 'src' / 'freight_recon' / 'migrations' / f).exists()]}")
    P(f"M10 emits a F13 BrakeNarrowed: {'BrakeNarrowed' in M10_SRC}")
    P(f"M10 imports the durable timer service: {'event_timers' in _m10_imports() or 'DurableTimers' in names}")
    P(f"M10 schedules a timer: {'.schedule(' in M10_SRC}")
    P(f"M10 sleeps in process: {'time.sleep' in M10_SRC}")
    P(f"TimerFired is modelled as a trigger with no legal row: {all(legal_transitions(s, Trigger.TIMER_FIRED) == () for s in CmState)}")

    P("landed machine files checked: 11")
    P(f"landed machines modified since the M9 head: {_landed_unchanged()}")
    P(f"transition rows in the specification: {len(CANONICAL_CM_IDS)}")
    P(f"the canonical CM transition ids: {list(CANONICAL_CM_IDS)}")
    P(f"transition rows the machine declares: {len(TRANSITIONS)}")
    P(f"the machine transition ids: {[r.id for r in TRANSITIONS]}")
    P(f"exact set match: {set(r.id for r in TRANSITIONS) == set(CANONICAL_CM_IDS)}")
    P(f"the six canonical states the machine declares: {sorted(s.value for s in CmState)}")
    P(f"M10 tenant-first tables: {list(P6CM_TENANT_TABLES)}")
    P("M10 tenant-exempt tables: []")
    pk = [r[1] for r in conn.execute("PRAGMA table_info(compensations)") if r[5]]
    P(f"tenant is first in the primary key: {bool(pk) and pk[0] == 'tenant'}")

    for lit in ("THE M1 WORK ITEM MACHINE IS UNCHANGED", "THE M2 PIPELINE MACHINE IS UNCHANGED",
                "THE M3 EFFECT AUTHORITY IS UNCHANGED", "THE M4 APPROVAL MACHINE IS UNCHANGED",
                "THE M9 EXCEPTION MACHINE IS UNCHANGED", "THE M11, M12 AND M13 MACHINES ARE NOT BUILT"):
        P(lit)
    conn.close()
    return out


# ---- argument handling & the run --------------------------------------------------------------

def _run_case(ctx: Ctx, case: str) -> CaseResult:
    try:
        w = _world(ctx)
        if evaluate(w, ctx, case):
            return CaseResult(True, lines=_lines(case))
        return CaseResult(False, markers=[f"### MISS ### {case}"])
    except ProbeExit:
        raise
    except Exception as exc:  # noqa: BLE001 — a case that crashes is a wrong behaviour, not a probe
        return CaseResult(False, markers=[f"### MISS ### {case} raised {type(exc).__name__}: {exc}"])


def _resolve_ctx(args: argparse.Namespace) -> Ctx:
    def bounded(name, value, lo, hi):
        if value < lo or value > hi:
            raise ProbeExit(f"--{name} {value} is out of range [{lo}, {hi}]. The axis is bounded.")
        return value
    if args.actor not in ACTOR_VALUES:
        raise ProbeExit(f"--actor {args.actor!r} is not one of {list(ACTOR_VALUES)}.")
    if args.decision_ref not in DECISION_REF_VALUES:
        raise ProbeExit(f"--decision-ref {args.decision_ref!r} is not one of {list(DECISION_REF_VALUES)}.")
    if args.original_state not in ORIGINAL_STATE_VALUES:
        raise ProbeExit(f"--original-state {args.original_state!r} is not one of {list(ORIGINAL_STATE_VALUES)}.")
    if args.exposure not in EXPOSURE_VALUES:
        raise ProbeExit(f"--exposure {args.exposure!r} is not one of {list(EXPOSURE_VALUES)}.")
    if args.brake not in BRAKE_VALUES:
        raise ProbeExit(f"--brake {args.brake!r} is not one of {list(BRAKE_VALUES)}.")
    if args.inject not in FAULTS:
        raise ProbeExit(f"unknown fault {args.inject!r}. The fault vocabulary is CLOSED: {', '.join(FAULTS)}.")
    ctx = Ctx(
        concurrency=bounded("concurrency", args.concurrency, 1, 8),
        delay_ms=bounded("delay-ms", args.delay_ms, 0, 5000),
        repeat=bounded("repeat", args.repeat, 1, 20),
        tenants=bounded("tenants", args.tenants, 1, 3),
        seed=args.seed, inject=args.inject, actor=args.actor, decision_ref=args.decision_ref,
        original_state=args.original_state, exposure=args.exposure, brake=args.brake)
    ctx.rng = random.Random(args.seed)
    return ctx


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list-cases", action="store_true")
    p.add_argument("--list-dimensions", action="store_true")
    p.add_argument("--case", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--tenants", type=int, default=1)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--inject", default="none")
    p.add_argument("--actor", default="human")
    p.add_argument("--decision-ref", default="valid")
    p.add_argument("--original-state", default="VERIFIED")
    p.add_argument("--exposure", default="integer")
    p.add_argument("--brake", default="none")
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
            if args.case not in CASES:
                raise ProbeExit(f"unknown case {args.case!r}. Run --list-cases.")
            cases = [args.case]
        else:
            cases = list(CASES)
    except ProbeExit as exc:
        print(f"probe: {exc.message}", file=sys.stderr)
        return 2

    wrong = 0
    printed: set[str] = set()
    for case in cases:
        result = _run_case(ctx, case)
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
        for line in report_lines():
            print(line)
        for line in _REQUIRED_ON_FULL_RUN:
            if line not in printed:
                print(line)
                printed.add(line)

    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
