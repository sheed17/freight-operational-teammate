"""The canonical effect boundary: the single containment layer through which every external
effect must pass (Implementation Phase 4). THIS IS THE UNIT THAT CLOSES R-07.

WHERE THIS SITS. P3 built the lock and the one-time authority: the seven-step atomic checkpoint
mints a grant and a witness, and `claim_grant_cas` performs the atomic GRANTED -> CLAIMED
compare-and-set (the P3-owned prefix of the adapter algorithm, ADR-004 §3.7 steps 1-5). This
module owns the REST of that algorithm — step 6 (record the attempt BEFORE the call), step 7
(touch the world through the one adapter invocation site), and the outcome aspect of machine M3:

    CLAIMED --EF-3--> ATTEMPTED --EF-4--> VERIFIED           (healthy readback matches the approval)
            \\-EF-3f-> FAILED                                 (PROVABLE non-occurrence, with proof)
            \\-EF-3u-> UNKNOWN_OUTCOME                         (timeout | crash | lost response)
                       ATTEMPTED --EF-4c-> UNKNOWN_OUTCOME    (readback contradicts the approval)
                       ATTEMPTED --EF-4u-> UNKNOWN_OUTCOME    (no positive health signal — blind)
    UNKNOWN_OUTCOME --EF-5--> {VERIFIED, FAILED}              (a human, or deterministic later proof)

THE TWO KEYS, AT THE ADAPTER (ADR-004 §2.2). An external effect is producible only by an adapter,
and an adapter acts only when presented with (a) a claimable Effect Grant AND (b) a fresh
Checkpoint Witness. `execute_effect` is the sole entry point that satisfies both: it claims through
the P3 CAS (which revalidates witness freshness, the confusion check, state, expiry, brake and
policy) and only then mints a single-use `ExecutionCapability` — which has NO PUBLIC CONSTRUCTOR,
exactly as `CheckpointPassed` has none. Code that has not claimed a grant cannot express a call to
an adapter effect: it has nothing to pass as the capability.

WHAT AN ADAPTER MAY NOT DO (adapters/registry.md — a boundary, not a brain). It may not mint
authority, claim authority for itself, construct the execution capability, call another adapter to
bypass the boundary, convert replay into authority, treat an attempted call as verified success,
convert an ambiguous outcome into ordinary failure, retry UNKNOWN_OUTCOME, operate under the wrong
tenant, bypass a brake, or run from an unauthorized import path. Every one of those is refused
here structurally, and the import gate (test_import_gate.py) makes the last one a build failure.

WHAT THIS MODULE IS NOT. Not the policy runtime (P8): the gate decision arrives already made, on
the grant row. Not the event system (P5): the attempt/outcome are recorded through the EXISTING
tenant-scoped audit and security event tables, never a new outbox. Not the Pipeline Instance (P6)
or an Evidence store (P7). No migration: the ledger already carries the eight states and the
`verification_outcome`/`unknown_reason` columns; outcome timestamps, exposure and proof travel in
`payload_json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from weakref import WeakSet

from .brake import DETECTOR
from .checkpoint import (
    CheckpointKernel,
    ClaimParams,
    EffectGrantHandle,
    claim_grant_cas,
)
from .freight_operations import InvoiceWriteOperation

# The claimed-or-committed states: a grant in any of these HELD the world's attention — a matching
# claimed grant, in the sense ADR-004 §4.5 means when it demands one behind every EffectAttempted.
CLAIMED_OR_LATER: frozenset[str] = frozenset(
    {"CLAIMED", "ATTEMPTED", "VERIFIED", "UNKNOWN_OUTCOME"}
)


class OperationClass(str, Enum):
    """The four canonical operation classes (adapters/registry.md — every operation is EXACTLY
    one). Only a CONSEQUENTIAL_EFFECT requires a grant and a witness; the three read classes never
    do (AC-ADPT-002). The read classes are carried here so the registry bijection (AC-ADPT-000) can
    assert every operation declares one, and so a read can never be routed as an effect."""

    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    DECISION_SUPPORT_READ = "DECISION_SUPPORT_READ"
    CONSEQUENTIAL_FRESHNESS_READ = "CONSEQUENTIAL_FRESHNESS_READ"
    CONSEQUENTIAL_EFFECT = "CONSEQUENTIAL_EFFECT"


class VerificationMode(str, Enum):
    """The three verification modes (adapters/registry.md point 40). READBACK reads the exact
    target back and matches it to the approved facts; RECEIPT distinguishes transmission from
    business completion (SMTP 250 is `ATTEMPTED`, never `delivered`); UNVERIFIABLE has no positive
    control and therefore may NEVER be autonomous (AC-ADPT-007)."""

    READBACK_VERIFIABLE = "READBACK_VERIFIABLE"
    RECEIPT_VERIFIABLE = "RECEIPT_VERIFIABLE"
    UNVERIFIABLE = "UNVERIFIABLE"


class VerificationOutcome(str, Enum):
    """The machine's decision after an attempt — set by THIS module, never by an adapter. The
    adapter returns a `ReadbackObservation` (structured evidence); the boundary decides."""

    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    OBSERVATION_CONFLICTING = "OBSERVATION_CONFLICTING"
    OBSERVATION_UNAVAILABLE = "OBSERVATION_UNAVAILABLE"


class UnknownReason(str, Enum):
    """Why an effect is in UNKNOWN_OUTCOME. Each names a distinct, honest ambiguity; none may be
    laundered into FAILED (ADR-004 §3.9, AC-ADPT-011/015)."""

    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"                    # EF-3u: timeout | crash | lost response
    OBSERVATION_CONFLICTING = "OBSERVATION_CONFLICTING"    # EF-4c: readback contradicts the approval
    OBSERVATION_UNAVAILABLE = "OBSERVATION_UNAVAILABLE"    # EF-4u: no positive health signal (blind)


# The grant states this module writes, and the from-state each transition requires. Named so the
# guards read against membership, not against a scattered set of string literals.
ATTEMPTED = "ATTEMPTED"
VERIFIED = "VERIFIED"
FAILED = "FAILED"
UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


class BoundaryError(RuntimeError):
    """A structural misuse of the boundary (not an effect refusal). Fail closed."""


class NotAGenuineCapability(BoundaryError):
    """Something that is not a genuine, unconsumed ExecutionCapability was offered to an adapter.
    A forged, copied, replayed or already-spent capability authorizes nothing (the type analogue
    of ADR-004 §4.1)."""


class OrphanEffectDetected(BoundaryError):
    """An adapter effect was reached without a valid, currently-claimed grant behind it. Fail
    closed: nothing is treated as success, and (in the detective sweep) the brake auto-engages
    (ADR-004 §4.5, M3 §38)."""


class AdapterPreflightRejected(RuntimeError):
    """The adapter proved the world was NOT touched — a pre-flight rejection before any external
    attempt (GR-5). This is the ONLY path to FAILED (EF-3f): FAILED requires affirmative proof of
    non-occurrence, never a timeout or an exception of unknown timing.

    `proof` is the structured evidence of non-occurrence; an empty proof is not proof."""

    def __init__(self, proof: str) -> None:
        if not str(proof or "").strip():
            raise BoundaryError(
                "AdapterPreflightRejected requires PROOF of non-occurrence; an empty proof is not "
                "proof. Without proof the honest outcome is UNKNOWN_OUTCOME, never FAILED (GR-5)."
            )
        super().__init__(proof)
        self.proof = str(proof)


class AdapterOutcomeUnknown(RuntimeError):
    """The adapter attempt's outcome cannot be established: a timeout, a crash, or a lost response
    after the call may have touched the world (GR-6). The effect enters UNKNOWN_OUTCOME (EF-3u) and
    is NEVER retried as though nothing happened.

    `reason` is a human-readable cause; `exposure` is the dollar-exposure string stated to the
    escalated human (ADR-004 §3.9) — the ledger never stores a money value, so this is a rendered
    string, not a number."""

    def __init__(self, reason: str, *, exposure: str = "") -> None:
        super().__init__(reason)
        self.reason = str(reason or "adapter outcome unknown")
        self.exposure = str(exposure)


@dataclass(frozen=True, slots=True)
class ReadbackObservation:
    """STRUCTURED EXECUTION EVIDENCE returned by an adapter's verification readback. The adapter
    reports what it saw; it NEVER decides VERIFIED/FAILED (AC-ADPT-015).

    `health_signal` is the POSITIVE control (AC-ADPT-012): False means the read channel itself
    could not be confirmed healthy — a logged-out page that "loads fine" is `health_signal=False`,
    never a verified failure. `observed_fingerprint` is the material-facts fingerprint the boundary
    compares to the approval; None means the target could not be read at all."""

    health_signal: bool
    observed_fingerprint: str | None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class AttemptResult:
    """What an adapter returns from a completed attempt: it TOUCHED the world and returned. The
    presence of this object is `ATTEMPTED`, not `VERIFIED` — an HTTP 200 or a returned value is a
    transmission fact, never a business-completion fact (AC-ADPT-006). Verification is separate."""

    external_ref: str = ""
    detail: str = ""


# ---------------------------------------------------------- the adapter operation contract


@dataclass(frozen=True, slots=True)
class AdapterOperation:
    """One declared adapter operation. Makes the operation class and verification requirements
    EXPLICIT (AC-ADPT-000/004) without implementing the P8 policy runtime.

    `perform` touches the world and returns an AttemptResult; it must accept an ExecutionCapability
    as its first argument and validate it (a boundary, not a brain — it receives a scoped
    capability and returns an external result). `readback` performs the verification read and
    returns a ReadbackObservation; it is a READ and takes no capability. Both are supplied by the
    adapter; the boundary orchestrates them and decides the outcome.
    """

    op_id: str
    adapter: str                                  # the adapter index id, e.g. "A4" (registry.md)
    operation_class: OperationClass
    verification_mode: VerificationMode
    perform: Callable[["ExecutionCapability", ClaimParams], AttemptResult] | None = None
    readback: Callable[[ClaimParams], ReadbackObservation] | None = None

    def __post_init__(self) -> None:
        if not str(self.op_id or "").strip():
            raise BoundaryError("an adapter operation has a non-empty op_id")
        if not isinstance(self.operation_class, OperationClass):
            raise BoundaryError(f"op {self.op_id!r}: operation_class must be an OperationClass")
        if not isinstance(self.verification_mode, VerificationMode):
            raise BoundaryError(f"op {self.op_id!r}: verification_mode must be a VerificationMode")
        if self.operation_class is OperationClass.CONSEQUENTIAL_EFFECT and self.perform is None:
            raise BoundaryError(
                f"op {self.op_id!r} is a CONSEQUENTIAL_EFFECT but declares no `perform`: an effect "
                f"operation must name the adapter action the boundary invokes"
            )
        if self.operation_class is not OperationClass.CONSEQUENTIAL_EFFECT and self.perform is not None:
            raise BoundaryError(
                f"op {self.op_id!r} is a read class but declares a `perform`: only a "
                f"CONSEQUENTIAL_EFFECT touches the world (AC-ADPT-002)"
            )

    @property
    def is_effect(self) -> bool:
        return self.operation_class is OperationClass.CONSEQUENTIAL_EFFECT


class AdapterOperationRegistry:
    """op_id -> AdapterOperation, total by construction and bijective with the frozen contracts
    (AC-ADPT-000). It refuses, at construction, an UNVERIFIABLE operation offered as autonomous —
    an operation with no positive control may never run without a human (AC-ADPT-007). This is a
    structural declaration, NOT the P8 policy runtime: it says which operations EXIST and how each
    is verified, and it makes an unverifiable-yet-autonomous registration fail to start."""

    def __init__(
        self,
        operations: dict[str, AdapterOperation],
        *,
        autonomous_op_ids: frozenset[str] = frozenset(),
    ) -> None:
        validated: dict[str, AdapterOperation] = {}
        for op_id, op in operations.items():
            if not isinstance(op, AdapterOperation):
                raise BoundaryError(f"registry entry {op_id!r} is not an AdapterOperation")
            if op.op_id != op_id:
                raise BoundaryError(
                    f"registry key {op_id!r} disagrees with op_id {op.op_id!r} — the map is not a "
                    f"bijection"
                )
            validated[op_id] = op
        for op_id in autonomous_op_ids:
            op = validated.get(op_id)
            if op is None:
                raise BoundaryError(f"autonomous op {op_id!r} is not registered")
            if op.verification_mode is VerificationMode.UNVERIFIABLE:
                raise BoundaryError(
                    f"op {op_id!r} is UNVERIFIABLE and may not be registered for autonomous "
                    f"execution: an operation with no positive control fails to start "
                    f"autonomously (AC-ADPT-007)"
                )
        self._operations = validated
        self._autonomous = frozenset(autonomous_op_ids)

    def get(self, op_id: str) -> AdapterOperation:
        op = self._operations.get(op_id)
        if op is None:
            raise BoundaryError(f"no adapter operation {op_id!r} is registered")
        return op

    def op_ids(self) -> frozenset[str]:
        return frozenset(self._operations)

    def is_autonomous(self, op_id: str) -> bool:
        return op_id in self._autonomous


# ---------------------------------------------------------- the single-use execution capability

# The genuine-instance registry: the ONLY way a capability passes `consume_capability` is to have
# been placed here by `_mint_capability`, which runs only after a successful claim CAS. A forged
# object.__new__ shell, a pickle round-trip, a copy and a subclass impostor are all absent from it —
# the exact structure `CheckpointPassed` uses, for the same reason.
_GENUINE_CAPABILITIES: "WeakSet[ExecutionCapability]" = WeakSet()
_CAPABILITY_TOKEN = object()


class ExecutionCapability:
    """The single-use capability to touch the world once, for ONE claimed grant. NO PUBLIC
    CONSTRUCTOR (ADR-004 §4.1 analogue): only `_mint_capability` constructs one, only after a
    grant is CLAIMED. Single-use: `consume` spends it, and a second use is refused. Cannot be
    pickled, copied or subclassed — a capability that can be duplicated is a licence to act twice.
    """

    __slots__ = ("tenant", "grant_id", "commit_key", "op_id", "_consumed", "__weakref__")

    def __init__(self, _token: object = None, *, tenant: str = "", grant_id: str = "",
                 commit_key: str = "", op_id: str = "") -> None:
        if _token is not _CAPABILITY_TOKEN:
            raise BoundaryError(
                "ExecutionCapability has no public constructor: it is produced only by the effect "
                "boundary, only after a grant is claimed. An adapter cannot construct its own "
                "authority (ADR-004 §2.6)."
            )
        self.tenant = tenant
        self.grant_id = grant_id
        self.commit_key = commit_key
        self.op_id = op_id
        self._consumed = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise BoundaryError("ExecutionCapability is final: a subclass is a forgery vector")

    def __reduce__(self) -> Any:
        raise BoundaryError("an ExecutionCapability cannot be pickled: authority does not serialize")

    def __copy__(self) -> Any:
        raise BoundaryError("an ExecutionCapability cannot be copied: it is single-use")

    def __deepcopy__(self, memo: Any) -> Any:
        raise BoundaryError("an ExecutionCapability cannot be copied: it is single-use")


def _mint_capability(*, tenant: str, grant_id: str, commit_key: str, op_id: str) -> ExecutionCapability:
    cap = ExecutionCapability(
        _CAPABILITY_TOKEN, tenant=tenant, grant_id=grant_id, commit_key=commit_key, op_id=op_id)
    _GENUINE_CAPABILITIES.add(cap)
    return cap


def consume_capability(cap: ExecutionCapability, *, op_id: str) -> ExecutionCapability:
    """An adapter's first line: prove the capability is genuine and unconsumed, then SPEND it.

    Refuses anything not minted by this process's boundary — a forged shell, a copy, a replay, or
    a capability already spent by a prior call. This is what makes "call the adapter directly, with
    no grant" impossible: there is no capability to pass, and a fabricated one is refused here.

    Raises `OrphanEffectDetected` — an adapter effect reached without genuine authority IS the
    orphan (ADR-004 §4.5). The detective sweep is what engages the brake; this refusal is the
    fail-closed wall that means nothing happened.
    """
    if type(cap) is not ExecutionCapability:
        raise OrphanEffectDetected(
            f"an adapter effect requires an ExecutionCapability; got {type(cap).__name__}. There "
            f"is no other key to this door."
        )
    if cap not in _GENUINE_CAPABILITIES:
        raise OrphanEffectDetected(
            "this ExecutionCapability was not minted by the effect boundary in this process: a "
            "reconstructed, copied or forged capability authorizes nothing"
        )
    if cap.op_id != op_id:
        raise OrphanEffectDetected(
            f"capability minted for op {cap.op_id!r} presented to op {op_id!r}: a capability is "
            f"scoped to its operation (the confused-deputy shape at the effect layer)"
        )
    if cap._consumed:
        raise OrphanEffectDetected(
            "this ExecutionCapability is already consumed: a capability authorizes exactly one "
            "attempt (single-use). A second use is a replay."
        )
    cap._consumed = True
    return cap


# ---------------------------------------------------------- the outcome record


@dataclass(frozen=True, slots=True)
class EffectExecution:
    """The boundary's return: what state the grant reached and why. `claimed` is False when the
    claim CAS refused (the adapter did NOTHING); `state` names the grant's resulting state; the
    remaining fields carry the honest detail."""

    claimed: bool
    grant_id: str
    state: str                                   # CLAIMED-refused cause, or ATTEMPTED/VERIFIED/...
    cause: str
    verification_outcome: VerificationOutcome | None = None
    unknown_reason: UnknownReason | None = None
    external_ref: str = ""
    exposure: str = ""
    failure_proof: str = ""
    touched_world: bool = False


# ---------------------------------------------------------- the effect boundary itself


def execute_effect(
    kernel: CheckpointKernel,
    handle: EffectGrantHandle,
    params: ClaimParams,
    operation: AdapterOperation,
    *,
    now: datetime | None = None,
) -> EffectExecution:
    """THE effect boundary. The complete adapter algorithm (ADR-004 §3.7), continuing the P3 CAS:

        1-5  claim CAS (P3): signature, row load, witness freshness, confusion check, atomic
             GRANTED -> CLAIMED revalidating state/expiry/brake/policy. Zero rows => do NOTHING.
        6    record EffectAttempted BEFORE the call, so an orphan is detectable even if the call
             never returns.
        7    touch the world — through `operation.perform`, the ONE adapter invocation site — with
             a freshly minted single-use ExecutionCapability.
        then the outcome aspect of M3: ATTEMPTED, then VERIFIED / UNKNOWN_OUTCOME (conflicting or
        blind) / FAILED (only on proven non-occurrence).

    A generic, unclassified exception from `operation.perform` — one that is neither
    AdapterPreflightRejected (proof of non-occurrence) nor AdapterOutcomeUnknown — is treated as
    UNKNOWN_OUTCOME, never FAILED (F4): the attempt is already recorded and non-occurrence is
    unproven, so the grant is moved out of CLAIMED before the exception re-raises, keeping the
    possibly-committed effect visible to the detective sweep and the escalated human.

    A retry NEVER re-enters here with the same grant: a claimed grant is single-use, and a re-run
    mints a NEW grant under the SAME commit key (ADR-004 §3.8). `execute_effect` neither loops nor
    retries — it runs one attempt and records what it can prove.
    """
    if not isinstance(operation, AdapterOperation):
        raise BoundaryError("execute_effect requires a declared AdapterOperation")
    if not operation.is_effect:
        raise BoundaryError(
            f"op {operation.op_id!r} is {operation.operation_class.value}, not a CONSEQUENTIAL_"
            f"EFFECT: a read never routes through the grant-and-witness boundary (AC-ADPT-002)"
        )
    if params.tenant.strip().lower() != kernel.store.tenant.strip().lower():
        # A cross-tenant effect attempt is contained and escalated GLOBALLY (AC-ADPT-016, F14):
        # record it, engage the GLOBAL brake, and refuse before any claim.
        _report_cross_tenant(kernel, params)
        raise BoundaryError(
            f"the call names tenant {params.tenant!r}; this boundary is bound to "
            f"{kernel.store.tenant!r}. An adapter never operates under the wrong tenant."
        )

    # ---- steps 1-5: the P3 claim CAS. Neither key alone suffices; the CAS refuses either alone.
    claim = claim_grant_cas(kernel, handle, params, now=now)
    if not claim.claimed:
        # Zero rows updated => the adapter does NOTHING. No attempt, no world touched.
        return EffectExecution(claimed=False, grant_id=claim.grant_id, state="REFUSED",
                               cause=claim.cause)

    grant_id = claim.grant_id
    # ---- step 6: record the attempt BEFORE the call (ADR-004 §3.7). Durable, tenant-scoped.
    record_effect_attempted(kernel, grant_id=grant_id, params=params)

    # ---- step 7: touch the world, once, with a single-use capability minted only now.
    cap = _mint_capability(
        tenant=kernel.store.tenant, grant_id=grant_id,
        commit_key=_grant_effect_key(kernel, grant_id), op_id=operation.op_id)
    try:
        result = operation.perform(cap, params)  # type: ignore[misc]
    except AdapterPreflightRejected as exc:
        # EF-3f: the adapter proved nothing happened. The ONLY path to FAILED.
        _transition_from_claimed(kernel, grant_id, to=FAILED,
                                 payload={"failure_proof": exc.proof}, now=now)
        kernel.observe({"kind": "EffectFailed", "grant_id": grant_id, "proof": exc.proof})
        return EffectExecution(claimed=True, grant_id=grant_id, state=FAILED,
                               cause="PROVEN_NON_OCCURRENCE", failure_proof=exc.proof,
                               touched_world=False)
    except AdapterOutcomeUnknown as exc:
        # EF-3u: timeout | crash | lost response. Cannot prove nothing happened => UNKNOWN_OUTCOME.
        _transition_from_claimed(
            kernel, grant_id, to=UNKNOWN_OUTCOME,
            unknown_reason=UnknownReason.UNKNOWN_OUTCOME,
            payload={"unknown_detail": exc.reason, "exposure": exc.exposure}, now=now)
        kernel.observe({"kind": "OutcomeUnknown", "grant_id": grant_id,
                        "unknown_reason": UnknownReason.UNKNOWN_OUTCOME.value})
        return EffectExecution(claimed=True, grant_id=grant_id, state=UNKNOWN_OUTCOME,
                               cause="OUTCOME_UNKNOWN",
                               unknown_reason=UnknownReason.UNKNOWN_OUTCOME,
                               exposure=exc.exposure, touched_world=True)
    except OrphanEffectDetected:
        # The boundary minted a genuine capability, so this can only mean the preventive layer was
        # itself defeated. Fail closed as a Sev-0 and auto-engage the brake (defense in depth).
        report_orphan_effect(kernel, grant_id=grant_id, params=params,
                             detail="perform rejected a boundary-minted capability")
        raise
    except Exception as exc:  # noqa: BLE001 — F4 / GR-6: any OTHER post-attempt failure is AMBIGUOUS
        # F4. The attempt is already recorded (EffectAttempted, step 6) and the adapter MAY have
        # touched the world before raising a generic, unclassified exception. We have NO positive
        # proof of non-occurrence — only AdapterPreflightRejected carries that proof and it is handled
        # above — so this is UNKNOWN_OUTCOME (EF-3u), NEVER FAILED (AC-ADPT-011/015, ADR-004 §3.9).
        # Moving the grant out of CLAIMED is the whole point: a grant left CLAIMED after an
        # EffectAttempted is invisible to the detective sweep (CLAIMED is a claimed-or-later state),
        # so the possibly-committed effect would never be reconciled. Record the honest ambiguity
        # BEFORE the exception propagates, then re-raise — a generic exception is unexpected and must
        # never be silently swallowed into a normal-looking result, and it is never retried in place.
        exposure = _rendered_exposure(kernel, grant_id)
        try:
            _transition_from_claimed(
                kernel, grant_id, to=UNKNOWN_OUTCOME,
                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,
                payload={"unknown_detail": f"post-attempt adapter exception: "
                                           f"{type(exc).__name__}: {exc}",
                         "exposure": exposure}, now=now)
        except BaseException as record_exc:  # noqa: BLE001 — recording must not mask the real failure
            # The state write itself failed. The EffectAttempted record still stands, so the ambiguity
            # is not lost; surface both, and let the ORIGINAL exception propagate.
            kernel.observe({"kind": "OutcomeUnknownRecordFailed", "grant_id": grant_id,
                            "error": str(record_exc)})
            raise exc
        kernel.observe({"kind": "OutcomeUnknown", "grant_id": grant_id,
                        "unknown_reason": UnknownReason.UNKNOWN_OUTCOME.value,
                        "cause": "POST_ATTEMPT_ADAPTER_EXCEPTION"})
        raise

    # The adapter touched the world and returned => ATTEMPTED (EF-3). attempted_at recorded.
    _transition_from_claimed(kernel, grant_id, to=ATTEMPTED,
                             payload={"external_ref": result.external_ref}, now=now)
    kernel.observe({"kind": "EffectExecuted", "grant_id": grant_id})

    # ---- verify+record (EF-4/4c/4u): ONE transaction, the adapter returns evidence, we decide.
    return _verify_and_record(kernel, grant_id, operation, params, result, now=now)


def _verify_and_record(
    kernel: CheckpointKernel,
    grant_id: str,
    operation: AdapterOperation,
    params: ClaimParams,
    result: AttemptResult,
    *,
    now: datetime | None,
) -> EffectExecution:
    """The verification step. Reads back through the adapter's positive control and matches the
    observed fingerprint to the APPROVED one on the grant row. The adapter returns structured
    evidence; the BOUNDARY decides — and never downgrades UNKNOWN_OUTCOME to FAILED (AC-ADPT-015).
    """
    approved_fingerprint = _grant_field(kernel, grant_id, "material_facts_fingerprint")
    exposure = _rendered_exposure(kernel, grant_id)

    observation: ReadbackObservation
    if operation.readback is None:
        # An effect with no readback is UNVERIFIABLE at attempt time: blind, never a success.
        observation = ReadbackObservation(health_signal=False, observed_fingerprint=None,
                                          detail="no readback declared")
    else:
        try:
            observation = operation.readback(params)
        except Exception as exc:  # noqa: BLE001 — a failed readback is blind, never a failure
            observation = ReadbackObservation(
                health_signal=False, observed_fingerprint=None,
                detail=f"readback raised: {exc}")
    if not isinstance(observation, ReadbackObservation):
        observation = ReadbackObservation(health_signal=False, observed_fingerprint=None,
                                          detail="adapter returned a non-observation")

    if not observation.health_signal:
        # EF-4u: no POSITIVE health signal. A page that "loads fine" while logged out is blind,
        # not a verified failure (AC-ADPT-012). The effect may have happened => UNKNOWN_OUTCOME.
        _transition_from_attempted(
            kernel, grant_id, to=UNKNOWN_OUTCOME,
            verification_outcome=VerificationOutcome.OBSERVATION_UNAVAILABLE,
            unknown_reason=UnknownReason.OBSERVATION_UNAVAILABLE,
            payload={"exposure": exposure, "readback_detail": observation.detail}, now=now)
        kernel.observe({"kind": "VerificationUnavailable", "grant_id": grant_id})
        return EffectExecution(
            claimed=True, grant_id=grant_id, state=UNKNOWN_OUTCOME, cause="BLIND_READBACK",
            verification_outcome=VerificationOutcome.OBSERVATION_UNAVAILABLE,
            unknown_reason=UnknownReason.OBSERVATION_UNAVAILABLE, exposure=exposure,
            external_ref=result.external_ref, touched_world=True)

    if observation.observed_fingerprint != approved_fingerprint:
        # EF-4c: healthy channel, but the world contradicts the approval. Urgent human-owned.
        _transition_from_attempted(
            kernel, grant_id, to=UNKNOWN_OUTCOME,
            verification_outcome=VerificationOutcome.OBSERVATION_CONFLICTING,
            unknown_reason=UnknownReason.OBSERVATION_CONFLICTING,
            payload={"exposure": exposure, "observed_fingerprint": observation.observed_fingerprint,
                     "approved_fingerprint": approved_fingerprint}, now=now)
        kernel.observe({"kind": "VerificationConflict", "grant_id": grant_id})
        return EffectExecution(
            claimed=True, grant_id=grant_id, state=UNKNOWN_OUTCOME, cause="OBSERVATION_CONFLICTING",
            verification_outcome=VerificationOutcome.OBSERVATION_CONFLICTING,
            unknown_reason=UnknownReason.OBSERVATION_CONFLICTING, exposure=exposure,
            external_ref=result.external_ref, touched_world=True)

    # EF-4: healthy positive-control readback matching the approved fingerprint => VERIFIED_SUCCESS.
    _transition_from_attempted(
        kernel, grant_id, to=VERIFIED,
        verification_outcome=VerificationOutcome.VERIFIED_SUCCESS,
        payload={"external_ref": result.external_ref, "health_signal": True}, now=now)
    kernel.observe({"kind": "EffectVerified", "grant_id": grant_id})
    return EffectExecution(
        claimed=True, grant_id=grant_id, state=VERIFIED, cause="VERIFIED_SUCCESS",
        verification_outcome=VerificationOutcome.VERIFIED_SUCCESS,
        external_ref=result.external_ref, touched_world=True)


# ---------------------------------------------------------- the typed EP-1 invoice write (dark)

# THE ONE effect-capable adapter import in this module. `effect_boundary` is the containment
# boundary, so this edge is exempt from the violation gate (import_probe.CONTAINMENT_BOUNDARY); it is
# the ONLY non-adapter module permitted to hold an effect-capable adapter. It is lazy, so the boundary
# module still imports no adapter at module-load time, and the AST import gate detects it regardless
# (it walks every import node). This is "actuator ownership moved into effect_boundary": the write
# adapter has exactly one importer, and it is the door.


def _default_invoice_writer():
    """The default bounded invoice writer — the reserved effect-capable adapter. Ships DARK: with no
    sandbox runner wired it performs no real write (SandboxOnlyWriteRefused -> proven non-occurrence).
    """
    from .browser_use_write import SandboxInvoiceWriteAdapter  # the ONE boundary->adapter edge (P4)

    return SandboxInvoiceWriteAdapter()


def _op_exposure(op: InvoiceWriteOperation) -> str:
    """A money-free exposure string for a typed invoice operation, stated to the escalated human when
    an outcome is unknown. Memory and logs never store a money value (CLAUDE.md §10): this says an
    amount was approved, never what it was."""
    return (f"operation={op.operation_class.value} target={op.target_integration}:{op.load_id} "
            f"amount_approved={'yes' if op.approved_amount else 'no'}")


def _params_from_operation(op: InvoiceWriteOperation) -> ClaimParams:
    """Derive the adapter's OWN claim parameters from the typed operation's canonical effect. They
    match the grant row minted from the SAME LogicalEffect, so the confusion check passes for a
    genuine operation and fails closed for a substituted one."""
    effect = op.logical_effect()
    return ClaimParams(
        tenant=effect.tenant, action_class=effect.action_class,
        target_system=effect.target_system, target_resource_id=effect.target_resource_id,
        target_operation=effect.target_operation)


def build_invoice_write_operation(op: InvoiceWriteOperation, *, writer=None) -> AdapterOperation:
    """Map a validated typed `InvoiceWriteOperation` onto a bounded `AdapterOperation`.

    The caller supplies DATA (the typed operation); this binds the adapter's bounded write/readback.
    `perform` consumes the single-use capability FIRST, then calls the bounded writer with the typed
    data — never a caller-authored task. The writer returns plain evidence; the boundary translates
    it into the canonical outcome types and decides VERIFIED/UNKNOWN/FAILED. A dark refusal (no real
    write) is a PROVEN non-occurrence (AdapterPreflightRejected), never a laundered success.
    """
    if not isinstance(op, InvoiceWriteOperation):
        raise BoundaryError("build_invoice_write_operation requires an InvoiceWriteOperation")
    the_writer = writer if writer is not None else _default_invoice_writer()
    op_id = op.capability_id

    def perform(cap: ExecutionCapability, params: ClaimParams) -> AttemptResult:
        consume_capability(cap, op_id=op_id)                       # prove authority or raise
        try:
            result = the_writer.write(op)
        except AdapterPreflightRejected:
            raise
        except AdapterOutcomeUnknown:
            raise
        except Exception as exc:  # noqa: BLE001
            # A dark refusal (SandboxOnlyWriteRefused) is a PROVABLE non-occurrence: nothing was
            # written -> the ONE path to FAILED. ANY OTHER exception from a browser-driven write that
            # has already begun cannot prove non-occurrence: the submit may have landed. That is the
            # canonical lost-acknowledgement ambiguity (a successful external write followed by a lost
            # ack), so it becomes UNKNOWN_OUTCOME (never FAILED, never a blind retry) — classified HERE
            # by the adapter that knows its own actuation, rather than falling through to
            # execute_effect's F4 backstop as an unclassified surprise. We convert to FAILED only the
            # refusal we can PROVE means nothing happened.
            if type(exc).__name__ == "SandboxOnlyWriteRefused":
                raise AdapterPreflightRejected(
                    f"dark invoice write performed nothing: {exc}") from exc
            raise AdapterOutcomeUnknown(
                f"invoice write raised after the attempt began; outcome unknowable "
                f"({type(exc).__name__}: {exc})",
                exposure=_op_exposure(op)) from exc
        outcome = str(getattr(result, "outcome", "")).upper()
        if outcome == "PREFLIGHT_REJECTED":
            raise AdapterPreflightRejected(str(getattr(result, "proof", "")) or "non-occurrence proven")
        if outcome == "OUTCOME_UNKNOWN":
            raise AdapterOutcomeUnknown(str(getattr(result, "detail", "") or "outcome unknown"),
                                        exposure=str(getattr(result, "exposure", "")))
        if outcome != "ATTEMPTED":
            raise BoundaryError(f"bounded writer returned an unrecognized outcome {outcome!r}")
        return AttemptResult(external_ref=str(getattr(result, "external_ref", "") or ""),
                             detail=str(getattr(result, "detail", "") or ""))

    def readback(params: ClaimParams) -> ReadbackObservation:
        rb = the_writer.readback(op)
        return ReadbackObservation(
            health_signal=bool(getattr(rb, "health_signal", False)),
            observed_fingerprint=getattr(rb, "observed_fingerprint", None),
            detail=str(getattr(rb, "detail", "") or ""))

    return AdapterOperation(
        op_id=op_id, adapter="A4",
        operation_class=OperationClass.CONSEQUENTIAL_EFFECT,
        verification_mode=VerificationMode.READBACK_VERIFIABLE,
        perform=perform, readback=readback)


def execute_invoice_write(
    kernel: CheckpointKernel,
    handle: EffectGrantHandle,
    op: InvoiceWriteOperation,
    *,
    writer=None,
    now: datetime | None = None,
) -> EffectExecution:
    """THE governed EP-1 write route (dark). It is the boundary's typed entry point: given a claimable
    grant handle and a validated typed operation, it derives the adapter's own claim parameters from
    the operation's canonical effect, builds the bounded operation, and runs the full adapter
    algorithm through `execute_effect` (claim CAS -> attempt -> readback -> outcome).

    DARKNESS. A non-sandbox operation is refused BEFORE any claim: no grant is claimed and nothing is
    attempted, so no real external write can occur. There is deliberately NO production caller of this
    function — like the detective sweep, it is built and proven now so the governed route is real,
    while the live supervised write is enabled and validated at P12.
    """
    if not isinstance(op, InvoiceWriteOperation):
        raise BoundaryError("execute_invoice_write requires an InvoiceWriteOperation")
    if not op.sandbox:
        # Fail closed before any claim. The capability is dark: a real target is refused here, so a
        # real effect cannot be reached even by a caller holding a valid grant.
        kernel.store.add_security_event(
            "InvoiceWriteRefusedNotSandbox", actor="effect-boundary",
            payload={"tenant": op.tenant, "work_item_id": op.work_item_id,
                     "commit_key": op.commit_key(), "capability_id": op.capability_id})
        raise BoundaryError(
            "the invoice write capability is DARK: a non-sandbox operation is refused before any "
            "claim. Live supervised external writes are enabled at P12, not here.")
    operation = build_invoice_write_operation(op, writer=writer)
    return execute_effect(kernel, handle, _params_from_operation(op), operation, now=now)


# ---------------------------------------------------------- the grant-outcome transitions


def _transition_from_claimed(
    kernel: CheckpointKernel,
    grant_id: str,
    *,
    to: str,
    unknown_reason: UnknownReason | None = None,
    payload: dict[str, Any] | None = None,
    now: datetime | None,
) -> None:
    """CLAIMED -> {ATTEMPTED, FAILED, UNKNOWN_OUTCOME} (EF-3 / EF-3f / EF-3u), atomically, guarded
    on the from-state. Zero rows updated means the grant was not CLAIMED — an illegal transition
    attempt, refused rather than silently applied."""
    _write_transition(kernel, grant_id, from_state="CLAIMED", to=to,
                      unknown_reason=unknown_reason, payload=payload, now=now)


def _transition_from_attempted(
    kernel: CheckpointKernel,
    grant_id: str,
    *,
    to: str,
    verification_outcome: VerificationOutcome,
    unknown_reason: UnknownReason | None = None,
    payload: dict[str, Any] | None = None,
    now: datetime | None,
) -> None:
    """ATTEMPTED -> {VERIFIED, UNKNOWN_OUTCOME} (EF-4 / EF-4c / EF-4u). verify+record is ONE
    transaction (ADR-004 §7: this window does not exist)."""
    _write_transition(kernel, grant_id, from_state=ATTEMPTED, to=to,
                      verification_outcome=verification_outcome, unknown_reason=unknown_reason,
                      payload=payload, now=now)


def _write_transition(
    kernel: CheckpointKernel,
    grant_id: str,
    *,
    from_state: str,
    to: str,
    verification_outcome: VerificationOutcome | None = None,
    unknown_reason: UnknownReason | None = None,
    payload: dict[str, Any] | None = None,
    now: datetime | None,
) -> None:
    when = _iso(now or kernel.now())
    conn = kernel.store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT payload_json FROM effect_grants WHERE tenant = ? AND grant_id = ? AND state = ?",
            (kernel.store.tenant, grant_id, from_state),
        ).fetchone()
        if row is None:
            conn.rollback()
            raise BoundaryError(
                f"illegal M3 transition {from_state} -> {to} for grant {grant_id}: the grant is "
                f"not in {from_state}. Terminal states never move (M3 §15)."
            )
        envelope = _merge_outcome_envelope(row["payload_json"], to, when, payload or {})
        conn.execute(
            "UPDATE effect_grants SET state = ?, verification_outcome = COALESCE(?, "
            "verification_outcome), unknown_reason = COALESCE(?, unknown_reason), payload_json = ? "
            "WHERE tenant = ? AND grant_id = ? AND state = ?",
            (to, verification_outcome.value if verification_outcome else None,
             unknown_reason.value if unknown_reason else None, envelope,
             kernel.store.tenant, grant_id, from_state),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _merge_outcome_envelope(payload_json: str, state: str, when: str, extra: dict[str, Any]) -> str:
    """The outcome envelope in payload_json: an append-only per-state log of {state, at, ...}. No
    migration is needed for attempted_at/verified_at/exposure/proof — they live here, and the
    prior states' entries are never rewritten (an audit trail that rewrites itself is not
    evidence)."""
    current: dict[str, Any]
    try:
        parsed = json.loads(payload_json) if payload_json else {}
    except (TypeError, ValueError):
        parsed = {}
    current = parsed if isinstance(parsed, dict) else {"minted_by_raw": str(parsed)}
    existing = current.get("outcome_log")
    log: list[Any] = existing if isinstance(existing, list) else []
    log.append({"state": state, "at": when, **{k: v for k, v in extra.items() if v not in (None, "")}})
    current["outcome_log"] = log
    return json.dumps(current, sort_keys=True)


# ---------------------------------------------------------- EF-5: resolving UNKNOWN_OUTCOME


def resolve_unknown_outcome(
    kernel: CheckpointKernel,
    grant_id: str,
    *,
    to: str,
    decision_ref: str,
    established_by: str,
    now: datetime | None = None,
) -> bool:
    """EF-5: UNKNOWN_OUTCOME -> {VERIFIED, FAILED}, and ONLY by a human establishing reality or a
    deterministic later observation carrying our commit key (GR-14 / V7). Never by a timer, never
    automatically (EF-5x is illegal).

    `decision_ref` and `established_by` are mandatory: an unknown outcome that resolves without a
    named human decision or a proof reference is exactly the silent auto-resolution ADR-004 §3.9
    forbids.
    """
    if to not in (VERIFIED, FAILED):
        raise BoundaryError(f"UNKNOWN_OUTCOME resolves only to VERIFIED or FAILED, not {to!r}")
    if not str(decision_ref or "").strip() or not str(established_by or "").strip():
        raise BoundaryError(
            "resolving UNKNOWN_OUTCOME records WHO established reality and the decision reference: "
            "an unknown outcome never auto-resolves (GR-14)"
        )
    when = _iso(now or kernel.now())
    conn = kernel.store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT payload_json FROM effect_grants WHERE tenant = ? AND grant_id = ? "
            "AND state = 'UNKNOWN_OUTCOME'",
            (kernel.store.tenant, grant_id),
        ).fetchone()
        if row is None:
            conn.rollback()
            return False
        envelope = _merge_outcome_envelope(
            row["payload_json"], to, when,
            {"reality_decision_ref": decision_ref, "established_by": established_by})
        conn.execute(
            "UPDATE effect_grants SET state = ?, payload_json = ? "
            "WHERE tenant = ? AND grant_id = ? AND state = 'UNKNOWN_OUTCOME'",
            (to, envelope, kernel.store.tenant, grant_id),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    kernel.observe({"kind": "RealityEstablished", "grant_id": grant_id, "outcome": to,
                    "decision_ref": decision_ref})
    return True


# ---------------------------------------------------------- orphan-effect detection (ADR-004 §4.5)


def record_effect_attempted(
    kernel: CheckpointKernel, *, grant_id: str, params: ClaimParams,
) -> None:
    """Durably record that an adapter is ABOUT to touch the world (ADR-004 §3.7 step 6). Written
    before the call through the existing tenant-scoped security-event table — NOT a P5 outbox — so
    an orphan is detectable even if the call never returns."""
    kernel.store.add_security_event(
        "EffectAttempted", actor="effect-boundary",
        payload={"grant_id": grant_id, "tenant": params.tenant,
                 "action_class": params.action_class, "target_system": params.target_system,
                 "target_resource_id": params.target_resource_id,
                 "target_operation": params.target_operation})
    kernel.observe({"kind": "EffectAttempted", "grant_id": grant_id, "tenant": params.tenant,
                    "target": params.target_resource_id})


def report_orphan_effect(
    kernel: CheckpointKernel, *, grant_id: str, params: ClaimParams, detail: str,
) -> None:
    """A Sev-0 orphan: an adapter effect with no matching claimed grant. Records the violation and
    AUTO-ENGAGES the brake for that tenant + action class (ADR-004 §4.5, M3 §38) — the preventive
    layers have failed and the system is acting outside its own boundary. Fail closed; leave enough
    evidence for investigation."""
    # The canonical F14 security event is `OrphanAdapterInvocation` (events/registry.md).
    kernel.store.add_security_event(
        "OrphanAdapterInvocation", actor="effect-boundary",
        payload={"grant_id": grant_id, "tenant": params.tenant,
                 "action_class": params.action_class, "target_system": params.target_system,
                 "target_resource_id": params.target_resource_id,
                 "target_operation": params.target_operation, "severity": "SEV0", "detail": detail})
    try:
        kernel.brakes.engage(
            tenant=kernel.store.tenant, action_class=params.action_class,
            actor="orphan-effect-detector", actor_kind=DETECTOR,
            reason=f"Sev-0 orphan adapter effect for grant {grant_id}: {detail}")
    except Exception as exc:  # noqa: BLE001 — the record must survive even if the brake write fails
        kernel.observe({"kind": "OrphanBrakeFailed", "grant_id": grant_id, "error": str(exc)})
    kernel.observe({"kind": "Sev0", "event_type": "OrphanAdapterInvocation", "grant_id": grant_id,
                    "detail": detail})


def _report_cross_tenant(kernel: CheckpointKernel, params: ClaimParams) -> None:
    """A cross-tenant effect attempt: record `CrossTenantAccessAttempted` and engage the GLOBAL
    brake (events/registry.md F14 maps cross-tenant to a GLOBAL-scope brake, AC-ADPT-016). Recorded
    against the boundary's own tenant — the context under which the breach was caught."""
    kernel.store.add_security_event(
        "CrossTenantAccessAttempted", actor="effect-boundary",
        payload={"boundary_tenant": kernel.store.tenant, "attempted_tenant": params.tenant,
                 "action_class": params.action_class,
                 "target_resource_id": params.target_resource_id, "severity": "SEV0"})
    try:
        kernel.brakes.engage(
            tenant=None, actor="cross-tenant-detector", actor_kind=DETECTOR,
            reason=f"Sev-0 cross-tenant effect attempt: boundary {kernel.store.tenant!r} handed "
                   f"tenant {params.tenant!r} params")
    except Exception as exc:  # noqa: BLE001 — the record must survive even if the brake write fails
        kernel.observe({"kind": "CrossTenantBrakeFailed", "error": str(exc)})
    kernel.observe({"kind": "Sev0", "event_type": "CrossTenantAccessAttempted",
                    "boundary_tenant": kernel.store.tenant, "attempted_tenant": params.tenant})


@dataclass(frozen=True, slots=True)
class OrphanFinding:
    grant_id: str
    action_class: str
    target_resource_id: str


def detect_orphan_effect_attempts(kernel: CheckpointKernel) -> list[OrphanFinding]:
    """The detective backstop (ADR-004 §4.5): reconcile every recorded `EffectAttempted` against
    the ledger and assert each has a matching claimed-or-later grant. Any EffectAttempted whose
    grant is absent, or is not in a claimed-or-later state, is an ORPHAN — a Sev-0 that auto-engages
    the brake. Returns the orphans found (empty on a healthy ledger).

    This is proven NOT vacuous by injecting a synthetic orphan EffectAttempted with no grant and
    asserting the detector finds it, records the Sev-0, and engages the brake — the happy path
    never produces one, so the injection is the only honest proof the detector works.
    """
    store = kernel.store
    attempts = store.conn.execute(
        "SELECT id, payload_json FROM security_events "
        "WHERE tenant = ? AND event_type = 'EffectAttempted'",
        (store.tenant,),
    ).fetchall()
    orphans: list[OrphanFinding] = []
    for row in attempts:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError):
            continue
        grant_id = payload.get("grant_id", "")
        grant = store.conn.execute(
            "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (store.tenant, grant_id),
        ).fetchone()
        if grant is not None and grant["state"] in CLAIMED_OR_LATER:
            continue
        params = ClaimParams(
            tenant=payload.get("tenant", store.tenant),
            action_class=payload.get("action_class", ""),
            target_system=payload.get("target_system", ""),
            target_resource_id=payload.get("target_resource_id", ""),
            target_operation=payload.get("target_operation", ""))
        report_orphan_effect(
            kernel, grant_id=grant_id, params=params,
            detail=f"EffectAttempted with no claimed grant (grant state: "
                   f"{grant['state'] if grant else 'ABSENT'})")
        orphans.append(OrphanFinding(grant_id=grant_id, action_class=params.action_class,
                                    target_resource_id=params.target_resource_id))
    return orphans


@dataclass(frozen=True, slots=True)
class DetectiveSweepResult:
    """One authorized detective-loop cycle's findings, for one tenant. `orphans` are Sev-0 — the
    brake was auto-engaged for each during the sweep; `unknown_outcomes` are grant ids still in
    UNKNOWN_OUTCOME awaiting a human decision. Both must stay visible to the operator surface."""

    tenant: str
    orphans: tuple[OrphanFinding, ...]
    unknown_outcomes: tuple[str, ...]


def pending_unknown_outcomes(kernel: CheckpointKernel) -> list[str]:
    """Every grant still in UNKNOWN_OUTCOME for this tenant — the human-owned queue an unknown
    outcome sits in until a person, or a later deterministic proof carrying our commit key,
    establishes reality (GR-14). It never auto-resolves, so the detective loop keeps surfacing it."""
    rows = kernel.store.conn.execute(
        "SELECT grant_id FROM effect_grants WHERE tenant = ? AND state = 'UNKNOWN_OUTCOME' "
        "ORDER BY grant_id",
        (kernel.store.tenant,),
    ).fetchall()
    return [row["grant_id"] for row in rows]


def run_detective_sweep(kernel: CheckpointKernel) -> DetectiveSweepResult:
    """THE authorized detective loop's per-cycle reconciliation (ADR-004 §4.5). An authorized runtime
    invokes this on a schedule, once per tenant per cycle. It is the RUNTIME HOME of the orphan
    detector: `detect_orphan_effect_attempts` is the mechanism, this is the loop that runs it and
    pairs it with the unknown-outcome queue.

    One tenant-scoped pass:
      * reconcile every recorded EffectAttempted against the ledger — an EffectAttempted with no
        claimed-or-later grant is an ORPHAN, a Sev-0 that auto-engages the brake for that tenant +
        action class (the preventive layers failed; the system is acting outside its own boundary);
      * surface every UNKNOWN_OUTCOME grant still awaiting a human decision (GR-14).

    This is a READ plus a brake reconciliation. It calls NO adapter and produces NO external effect,
    so it is structurally inert under replay (ADR-004 rule 11 / the replay-cannot-call-adapters
    invariant) and safe to run continuously. The scheduler/daemon that ticks it lives in the
    production runtime (P11); this is the unit it ticks, built and proven now so the wiring is real.
    """
    orphans = detect_orphan_effect_attempts(kernel)
    unknowns = pending_unknown_outcomes(kernel)
    kernel.observe({"kind": "DetectiveSweep", "tenant": kernel.store.tenant,
                    "orphans": len(orphans), "unknown_outcomes": len(unknowns)})
    return DetectiveSweepResult(tenant=kernel.store.tenant, orphans=tuple(orphans),
                                unknown_outcomes=tuple(unknowns))


# ---------------------------------------------------------- internals


def _grant_effect_key(kernel: CheckpointKernel, grant_id: str) -> str:
    """Read the effect's Commit Key already stored on the grant row. This is a READ, not a
    derivation: the canonical (and only) derivation lives in commit_key.py, and P4 never recomputes
    it - it reads back what P3 minted so the outcome envelope can name the effect it belongs to."""
    return _grant_field(kernel, grant_id, "commit_key")


def _grant_field(kernel: CheckpointKernel, grant_id: str, column: str) -> str:
    row = kernel.store.conn.execute(
        f"SELECT {column} FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (kernel.store.tenant, grant_id),
    ).fetchone()
    return "" if row is None or row[column] is None else str(row[column])


def _rendered_exposure(kernel: CheckpointKernel, grant_id: str) -> str:
    """The dollar exposure stated to a human, rendered as a string. The ledger never stores a money
    value in memory or logs; this reads the approved_amount already on the row and renders it."""
    amount = _grant_field(kernel, grant_id, "approved_amount")
    action = _grant_field(kernel, grant_id, "action_class")
    target = _grant_field(kernel, grant_id, "target_resource_id")
    return f"action={action} target={target} approved_amount={amount or 'unstated'}"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise BoundaryError("the boundary clock must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat()
