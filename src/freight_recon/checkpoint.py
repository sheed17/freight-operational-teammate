"""The safety kernel: the seven-step atomic checkpoint, the Checkpoint Witness, grant mint and
the claim CAS (Implementation Phase 3).

THE TWO-KEY RULE (ADR-004 §2.2). An Effect Grant is NECESSARY but NOT SUFFICIENT. The grant
answers "may this attempt exist?" — authority. The Checkpoint Witness answers "is the world still
what we approved?" — freshness. The adapter (P4) will require both; the claim CAS here already
refuses either alone.

THE SEVEN CHECKS (ADR-004 §2.4, constitutional) run as ONE atomic checkpoint — not seven
independent checks separated by asynchronous work — in fixed canonical order (SD-7), inside ONE
database transaction that also inserts the witness and mints the grant (entity 05 §15, M-40):

    1 approval validity          (ADR-005)
    2 material-facts fingerprint (ADR-005; drift voids)
    3 projected-state freshness  (ADR-001 C4; live, never a cache)
    4 native-state validity      (ADR-002; unretracted, unsuperseded, not conflicting)
    5 entity-version concurrency (ADR-009; the SD-3 pin set, derived — never caller-chosen)
    6 policy evaluation          (ADR-010; the gate decision is never null)
    7 human-brake admission      (ADR-011; read in the same transaction)

All seven pass => a `CheckpointPassed` exists => a grant may be minted. Any one fails => the
transaction rolls back => NO witness row, NO grant row, NO authorization capability whatsoever.
There is no partial authorization state (the universal oracle of the 105-case matrix).

WHAT THIS MODULE IS NOT. Not the adapter boundary (P4 routes adapters through `claim_grant_cas`
and turns on the import gate; the six live-write paths are untouched here and R-07 stays OPEN).
Not the event system (P5; the observer hook below is process-local observability, not an outbox).
Not the Pipeline Instance (P6), the Approval machine (P6/P8) or the policy runtime (P8): approvals
and policy arrive as typed, validated INPUTS, and the registry here is the deterministic gate
lookup those phases will feed. P3 ships dark — nothing routes production traffic through it until
P4 does.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable
from weakref import WeakSet

from .brake import BrakeStore, BrakeStoreUnreachable
from .commit_key import LogicalEffect
from .fingerprint import (
    FINGERPRINT_VERSION,
    DriftedField,
    FingerprintError,
    canonical_payload,
    drift_diff,
)
from .migrations.phase2_tenant_first import FORBIDDEN_ACTORS
from .workflow import WorkflowStore

# The claim CAS transition, named. The ONLY grant-state transition this module performs against a
# claimable capability: GRANTED -> CLAIMED, atomically, single-use, revalidating expiry, brake and
# policy inside the UPDATE itself (ADR-004 §3.5; machine M3 EF-2).
GRANTED_TO_CLAIMED: tuple[str, str] = ("GRANTED", "CLAIMED")

# Canonical step order and names (SD-7): the FIRST failing step is the one reported, always.
CHECKPOINT_STEPS: tuple[str, ...] = (
    "approval_validity",
    "material_facts_fingerprint",
    "projected_state_freshness",
    "native_state_validity",
    "entity_version_concurrency",
    "policy_evaluation",
    "brake_admission",
)


class GateDecision(str, Enum):
    """The four canonical gate decisions (ADR-010 §3.1, amendment A3). Exactly one per action
    class, never null, no default-by-accident: an unregistered class resolves to the workflow
    default below, which is HUMAN_APPROVAL_REQUIRED and never autonomous (ADR-010 §8 layer 7)."""

    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    AUTONOMOUS_WITHIN_CAPS = "AUTONOMOUS_WITHIN_CAPS"
    PERMANENT_HUMAN_ASSERTION_REQUIRED = "PERMANENT_HUMAN_ASSERTION_REQUIRED"
    FORBIDDEN = "FORBIDDEN"


_HUMAN_GATES = frozenset({
    GateDecision.HUMAN_APPROVAL_REQUIRED,
    GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
})


class ProvenanceClass(str, Enum):
    """C-7: the six canonical provenance classes. There is no seventh."""

    SYSTEM_IMPORTED = "SYSTEM_IMPORTED"
    OWNER_ASSERTED = "OWNER_ASSERTED"
    LINKER_INFERRED = "LINKER_INFERRED"
    MODEL_EXTRACTED = "MODEL_EXTRACTED"
    MODEL_INFERRED = "MODEL_INFERRED"
    RECONCILED = "RECONCILED"


class EvidenceCondition(str, Enum):
    """ADR-002 C5. `absent` and `unknown` are different conditions; neither is `consistent`."""

    ABSENT = "absent"
    UNKNOWN = "unknown"
    CONSISTENT = "consistent"
    CONFLICTING = "conflicting"
    STALE = "stale"


class CheckpointError(RuntimeError):
    """A structural misuse of the kernel (not a checkpoint refusal). Fail closed."""


class GateReadOfInferredFact(CheckpointError):
    """A consequential gate tried to READ a MODEL_INFERRED value (AC-SAFE-015). At any
    confidence — there is no confidence; the type does not carry one."""


class SourceUnreadable(RuntimeError):
    """An authoritative source could not be read. `unknown` is not `no drift` (ADR-005 §3.12):
    the checkpoint refuses, it never proceeds on the value it failed to fetch."""


class NotALiveReader(TypeError):
    """Something other than an AuthoritativeSourceReader was offered to a consequential read.
    A cache is structurally impossible here (AC-CKPT-3-stale): this is a construction failure,
    not a runtime pass."""


@dataclass(frozen=True, slots=True)
class ProvenancedFact:
    """One material fact with its provenance and evidence condition — and NO confidence field.

    `value` is the GATING accessor: it raises on MODEL_INFERRED, which is what "a consequential
    gate cannot read a guess" means mechanically. `fingerprint_value` exists because provenance
    is INSIDE the fingerprint (ADR-005 §3.3): serialization must see the value to detect that a
    guess is standing where a fact used to — serialization is detection, not gating; step 4
    refuses the fact set before any gate evaluates it.

    `entity_ref` names the canonical entity this fact depends on, feeding the SD-3 pin set.
    """

    field: str
    provenance: ProvenanceClass
    evidence_condition: EvidenceCondition
    entity_ref: str | None = None
    _value: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, ProvenanceClass):
            raise CheckpointError(f"fact {self.field!r}: provenance must be a ProvenanceClass")
        if not isinstance(self.evidence_condition, EvidenceCondition):
            raise CheckpointError(f"fact {self.field!r}: evidence_condition must be an EvidenceCondition")

    @property
    def value(self) -> Any:
        if self.provenance is ProvenanceClass.MODEL_INFERRED:
            raise GateReadOfInferredFact(
                f"material fact {self.field!r} is MODEL_INFERRED and may not be read by a "
                f"consequential gate — at any confidence. There is no confidence."
            )
        return self._value

    @property
    def fingerprint_value(self) -> Any:
        return self._value


class AuthoritativeSourceReader:
    """A live read of an authoritative source (ADR-001 C4). The ONLY reader type the checkpoint
    accepts: the money read cannot be offered a cache because there is no parameter a cache fits
    into — `CheckpointInputs` refuses anything that is not exactly this type, and this type is
    final, so a `CachedReader(AuthoritativeSourceReader)` cannot exist either.
    """

    __slots__ = ("_read", "source")

    def __init__(self, read: Callable[[], Any], *, source: str) -> None:
        if not callable(read):
            raise NotALiveReader("an AuthoritativeSourceReader wraps a zero-argument live read")
        if not str(source or "").strip():
            raise NotALiveReader("a live reader names its authoritative source")
        self._read = read
        self.source = str(source)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise NotALiveReader(
            "AuthoritativeSourceReader is final: a subclass could reintroduce the cache this "
            "type exists to make unspeakable"
        )

    def read(self) -> Any:
        try:
            return self._read()
        except SourceUnreadable:
            raise
        except Exception as exc:  # noqa: BLE001 — every reader failure is the same refusal
            raise SourceUnreadable(f"authoritative source {self.source!r} unreadable: {exc}") from exc


@dataclass(frozen=True, slots=True)
class Caps:
    """Deterministic caps for AUTONOMOUS_WITHIN_CAPS at P3 depth: a per-day count and a hard
    money ceiling in integer minor units. Richer cap vocabularies are the policy runtime (P8)."""

    max_per_day: int | None = None
    max_amount_minor: int | None = None
    amount_field: str = "amount"


@dataclass(frozen=True, slots=True)
class GateEntry:
    gate: GateDecision
    caps: Caps | None = None
    required_authority: str | None = None
    # Entities a gate precondition depends on (SD-3 clause 3): their versions are pinned and
    # revalidated at step 5 even though no material fact names them.
    precondition_entities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.gate, GateDecision):
            raise CheckpointError(
                f"a gate decision must be one of the four canonical members, got {self.gate!r}. "
                f"A null or invented gate is an unasserted gate (F-20)."
            )


class GateRegistry:
    """action_class -> GateEntry, total by construction.

    F-20: an action class with no gate decision CANNOT BE REGISTERED — construction raises, which
    is this kernel's "the system fails to start". A class absent from the registry resolves to
    the workflow default: HUMAN_APPROVAL_REQUIRED (ADR-010 §8 layer 7 — the fallback is never
    autonomous), so forgetting to classify a class can only ever cost a human tap, never a gate.
    """

    _DEFAULT = GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED)

    def __init__(self, entries: dict[str, GateEntry], *, policy_version: str) -> None:
        if not str(policy_version or "").strip():
            raise CheckpointError("a gate registry carries a policy_version; blank is not a version")
        validated: dict[str, GateEntry] = {}
        for action_class, entry in entries.items():
            name = str(action_class or "").strip().lower()
            if not name:
                raise CheckpointError("an action class name must be non-empty")
            if not isinstance(entry, GateEntry):
                raise CheckpointError(
                    f"action class {name!r} registered without a GateEntry ({entry!r}): a gate "
                    f"expressible as an absence is not a gate (F-20). The system fails to start."
                )
            validated[name] = entry
        self._entries = validated
        self.policy_version = str(policy_version)

    def gate_for(self, action_class: str) -> GateEntry:
        return self._entries.get(str(action_class or "").strip().lower(), self._DEFAULT)


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """A human authorisation, as the checkpoint consumes it (ADR-005). At P3 this is a typed
    INPUT — the durable Approval machine is P6/P8 work; nothing here creates one.

    `canonical_payload` is the full fp_v1 bytes rendered to the approver — retained because a
    hash can prove drift but never say what (ADR-005 §3.5).
    """

    approval_id: str
    tenant: str
    actor_id: str
    actor_kind: str                      # "HUMAN" is the only kind that can approve (ADR-003)
    authority: str
    state: str                           # GRANTED | REVOKED | EXPIRED | CONSUMED | VOID_*
    fingerprint: str
    canonical_payload: bytes
    fingerprint_version: str
    entity_versions: dict[str, int]
    policy_version: str
    granted_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class NativeClaim:
    """One native claim a material fact rests on (ADR-002): must be unretracted, unsuperseded and
    not conflicting at checkpoint step 4."""

    claim_id: str
    status: str                          # ACTIVE | RETRACTED | SUPERSEDED
    conflicting: bool
    provenance: ProvenanceClass


@dataclass(frozen=True, slots=True)
class CheckpointRequest:
    """The intent being checkpointed: WHO, on WHAT, WHICH effect. The commit key comes from the
    canonical LogicalEffect — there is no free-form key parameter to vary between retries."""

    effect: LogicalEffect
    actor: str
    accountable_owner: str
    target_entity_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.effect, LogicalEffect):
            raise CheckpointError("a CheckpointRequest identifies its effect with a LogicalEffect")
        if not str(self.actor or "").strip():
            raise CheckpointError("a checkpoint records WHO acted; an empty actor is not an actor")
        owner = str(self.accountable_owner or "").strip()
        if not owner or owner.lower() in FORBIDDEN_ACTORS:
            raise CheckpointError(
                f"accountable_owner must name a human; {self.accountable_owner!r} names nobody "
                f"(I1: every consequential action has one accountable human owner)"
            )
        if not str(self.target_entity_ref or "").strip():
            raise CheckpointError("the target entity reference is required (SD-3 clause 2)")


class CheckpointInputs:
    """The typed inputs of one checkpoint run. Reader slots accept EXACTLY
    AuthoritativeSourceReader — a projection cache, a dict of remembered values, or any other
    stand-in fails HERE, at construction, before a single check runs (AC-CKPT-3-stale)."""

    __slots__ = (
        "approval", "material_facts_reader", "projection_assertion", "projected_state_reader",
        "native_claims", "entity_version_reader", "proposed_entity_versions", "runs_today",
    )

    def __init__(
        self,
        *,
        material_facts_reader: AuthoritativeSourceReader,
        projection_assertion: dict[str, Any],
        projected_state_reader: AuthoritativeSourceReader,
        entity_version_reader: AuthoritativeSourceReader,
        native_claims: tuple[NativeClaim, ...] = (),
        approval: ApprovalRecord | None = None,
        proposed_entity_versions: dict[str, int] | None = None,
        runs_today: int = 0,
    ) -> None:
        for name, reader in (
            ("material_facts_reader", material_facts_reader),
            ("projected_state_reader", projected_state_reader),
            ("entity_version_reader", entity_version_reader),
        ):
            if type(reader) is not AuthoritativeSourceReader:
                raise NotALiveReader(
                    f"{name} must be an AuthoritativeSourceReader performing a LIVE read of the "
                    f"authoritative source; got {type(reader).__name__}. A consequential "
                    f"freshness read is structurally forbidden a cache (ADR-001 C4)."
                )
        if approval is not None and not isinstance(approval, ApprovalRecord):
            raise CheckpointError("approval must be an ApprovalRecord or None")
        for claim in native_claims:
            if not isinstance(claim, NativeClaim):
                raise CheckpointError(f"native claim {claim!r} is not a NativeClaim")
        self.approval = approval
        self.material_facts_reader = material_facts_reader
        self.projection_assertion = dict(projection_assertion)
        self.projected_state_reader = projected_state_reader
        self.entity_version_reader = entity_version_reader
        self.native_claims = tuple(native_claims)
        self.proposed_entity_versions = dict(proposed_entity_versions or {})
        self.runs_today = int(runs_today)


# ------------------------------------------------------------------ the witness

# The genuine-instance registry: the ONLY way an object passes mint_grant's identity check is to
# have been placed here by the checkpoint's own success path. object.__new__ forgeries, pickle
# round-trips, copies and subclass impostors are all absent from this set.
_GENUINE_PASSES: "WeakSet[CheckpointPassed]" = WeakSet()
_FACTORY_TOKEN = object()


class CheckpointPassed:
    """Proof that the seven checks passed moments ago, in THIS process, for ONE effect.

    NO PUBLIC CONSTRUCTOR (entity 05 §21): only the checkpoint function constructs one, only on
    success. Single-use: consumed by the mint it authorizes. Cannot be pickled, copied, or
    subclassed — a witness that can be duplicated is a witness that can be replayed.
    """

    __slots__ = ("checkpoint_id", "tenant", "commit_key", "_consumed", "__weakref__")

    def __init__(self, _token: object = None, *, checkpoint_id: str = "", tenant: str = "",
                 commit_key: str = "") -> None:
        if _token is not _FACTORY_TOKEN:
            raise CheckpointError(
                "CheckpointPassed has no public constructor: it is produced only by the "
                "checkpoint function, only when all seven checks pass (M-47, M-65)"
            )
        self.checkpoint_id = checkpoint_id
        self.tenant = tenant
        self.commit_key = commit_key
        self._consumed = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise CheckpointError("CheckpointPassed is final: a subclass is a forgery vector")

    def __reduce__(self) -> Any:
        raise CheckpointError("a CheckpointPassed cannot be pickled: freshness does not serialize")

    def __copy__(self) -> Any:
        raise CheckpointError("a CheckpointPassed cannot be copied: it is single-use")

    def __deepcopy__(self, memo: Any) -> Any:
        raise CheckpointError("a CheckpointPassed cannot be copied: it is single-use")


def _mint_checkpoint_passed(*, checkpoint_id: str, tenant: str, commit_key: str) -> CheckpointPassed:
    passed = CheckpointPassed(
        _FACTORY_TOKEN, checkpoint_id=checkpoint_id, tenant=tenant, commit_key=commit_key
    )
    _GENUINE_PASSES.add(passed)
    return passed


@dataclass(frozen=True, slots=True)
class CheckpointWitness:
    """The durable witness record, exactly as inserted (entity 05 point 10). Immutable — the
    table refuses UPDATE and DELETE by trigger, this type by frozen dataclass."""

    tenant: str
    checkpoint_id: str
    grant_id: str
    actor: str
    accountable_owner: str
    action_class: str
    target_system: str
    target_resource_id: str
    target_operation: str
    commit_key: str
    material_facts_fingerprint: str
    entity_versions: dict[str, int]
    approval_id: str | None
    approval_fingerprint: str | None
    policy_version: str
    gate_decision: GateDecision
    autonomy_state: str
    brake_version: str
    projected_observations_used: tuple[str, ...]
    native_claims_used: tuple[str, ...]
    created_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class EffectGrantHandle:
    """The opaque, signed handle (ADR-004 §3.3). Neither property is the security control: the
    ledger is the authority, the handle is a pointer. The raw token is never stored — only its
    digest lands on the grant row."""

    tenant: str
    grant_id: str
    token: str
    signature: str


@dataclass(frozen=True, slots=True)
class ClaimParams:
    """The adapter's OWN call parameters, revalidated against the grant row (the confusion
    check, ADR-004 §3.7 step 4). Any mismatch is a Sev-0 security event, not an error."""

    tenant: str
    action_class: str
    target_system: str
    target_resource_id: str
    target_operation: str


@dataclass(frozen=True, slots=True)
class CheckpointRefused:
    """Outcome (b): NO authorization capability whatsoever. The FIRST failing step is named
    (SD-7), the reason is machine-readable, and the drift diff — when step 2 refused — names
    every changed field with old and new values (ADR-005 §3.13). `sev0`, when set, names the
    security event this refusal additionally is (a refusal and an attack are different facts)."""

    step: int
    step_name: str
    reason: str
    detail: str
    drift: tuple[DriftedField, ...] = ()
    sev0: str | None = None
    authorized: bool = False


@dataclass(frozen=True, slots=True)
class CheckpointAuthorized:
    """Outcome (a): ONE immutable witness row and ONE grant row, minted in the checkpoint's own
    transaction. The handle claims it later; the witness's freshness bounds how much later."""

    witness: CheckpointWitness
    handle: EffectGrantHandle
    authorized: bool = True


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    claimed: bool
    cause: str
    grant_id: str
    transition: tuple[str, str] | None = None


class CheckpointKernel:
    """The kernel binds one tenant-bound WorkflowStore, one brake store on the same connection,
    one gate registry, and one clock. Everything consequential happens on the store's own
    SQLite connection so the seven reads, the witness insert and the mint share one transaction.
    """

    def __init__(
        self,
        store: WorkflowStore,
        gate_registry: GateRegistry,
        *,
        clock: Callable[[], datetime] | None = None,
        witness_window: timedelta = timedelta(seconds=60),
        grant_ttl: timedelta = timedelta(seconds=60),
        observer: Callable[[dict[str, Any]], None] | None = None,
        handle_key: bytes | None = None,
    ) -> None:
        if not isinstance(store, WorkflowStore):
            raise CheckpointError("the kernel requires a tenant-bound WorkflowStore")
        if not isinstance(gate_registry, GateRegistry):
            raise CheckpointError(
                "the kernel requires a GateRegistry: without one, no action class has a gate "
                "decision, and a gate expressible as an absence is not a gate (F-20)"
            )
        if witness_window <= timedelta(0) or grant_ttl <= timedelta(0):
            raise CheckpointError("witness_window and grant_ttl must be positive")
        if witness_window > grant_ttl:
            raise CheckpointError(
                "the witness freshness window may not exceed the grant TTL (entity 05 §45): a "
                "witness outliving its grant would vouch for a capability that no longer exists"
            )
        self.store = store
        self.brakes = BrakeStore(store.conn)
        self.gates = gate_registry
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.witness_window = witness_window
        self.grant_ttl = grant_ttl
        self._observer = observer or (lambda event: None)
        # In-memory per-kernel HMAC key: the signature is a cheap early-rejection filter, never
        # the control (ADR-004 §3.3). A restart loses it, unclaimed grants expire, nothing
        # happened — the fail-closed direction. No durable credential exists before P4/P11.
        self._handle_key = handle_key or os.urandom(32)

    def now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise CheckpointError("the kernel clock must be timezone-aware UTC")
        return value.astimezone(timezone.utc)

    def observe(self, event: dict[str, Any]) -> None:
        try:
            self._observer(dict(event))
        except Exception:  # noqa: BLE001 — observability must never alter control flow
            pass

    def sign(self, token: str) -> str:
        return hmac.new(self._handle_key, token.encode("utf-8"), hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ the checkpoint itself


def _tenant_mismatch_refusal(
    kernel: CheckpointKernel, request: CheckpointRequest,
) -> CheckpointRefused | None:
    """[C-1] at the kernel's front door. One text, both entry points."""
    if request.effect.tenant.strip().lower() == kernel.store.tenant.strip().lower():
        return None
    return CheckpointRefused(
        step=1, step_name=CHECKPOINT_STEPS[0], reason="TENANT_MISMATCH",
        detail=f"the effect names tenant {request.effect.tenant!r}; this kernel is bound to "
               f"{kernel.store.tenant!r}. A checkpoint never crosses a tenant.",
    )


def run_checkpoint_locked(
    kernel: CheckpointKernel,
    request: CheckpointRequest,
    inputs: CheckpointInputs,
    *,
    now: datetime | None = None,
) -> CheckpointAuthorized | CheckpointRefused:
    """The seven checks, the witness insert and the grant mint — INSIDE THE CALLER'S TRANSACTION.

    ### WHY THIS ENTRY POINT EXISTS, AND WHAT IT DOES NOT CHANGE.
    `02-pipeline-instance.machine.md` §4 requires that PL-8 co-commit *"the Checkpoint Witness
    insert + the grant mint (M3) in ONE transaction"* **with the pipeline's own `CHECKPOINT →
    GRANTED` state change and the `CheckpointPassed` it emits**. `run_checkpoint` owns its
    transaction, so a caller that also has a row to write in that same commit cannot use it — and
    the alternative, a machine that re-implements the seven checks, is the second effect-authority
    system CLAUDE.md rule 17 forbids.

    So this is an EXTRACTION, not a new kernel: `run_checkpoint` is now a thin transaction wrapper
    over this exact body, and there is one text of the seven steps, one witness insert and one mint.
    Nothing here is weaker than what `run_checkpoint` did — the step order, the short-circuit, the
    SD-3 pin set, the `CheckpointPassed` mint and the fail-closed direction are `_seven_steps_locked`
    and are untouched.

    ### THE ONE THING THIS OWES ITS CALLER: a refusal returned from here is NOT yet recorded.
    `_record_refusal` writes a `security_events` row, and that row must survive the caller's
    rollback — so it cannot be written inside the transaction that is about to be abandoned. The
    caller rolls back FIRST and then calls `record_checkpoint_refusal`. That is the same ordering
    `run_checkpoint` has always used; it is now the caller's to perform because the transaction is.

    Requires a transaction to be open; never opens, commits or rolls back one.
    """
    if not isinstance(request, CheckpointRequest) or not isinstance(inputs, CheckpointInputs):
        raise CheckpointError("run_checkpoint takes a CheckpointRequest and CheckpointInputs")
    mismatch = _tenant_mismatch_refusal(kernel, request)
    if mismatch is not None:
        return mismatch
    when = now or kernel.now()
    try:
        outcome = _seven_steps_locked(
            kernel, request, inputs, request.effect.key(), when)
    except sqlite3.IntegrityError as exc:
        # The Layer-2 live-hold index refused the mint: another attempt already holds this logical
        # effect. SQLite's default ABORT backs out only the offending STATEMENT and leaves the
        # transaction active, so returning here is safe — the caller still decides the commit.
        return CheckpointRefused(
            step=0, step_name="mint", reason="COMMIT_KEY_HELD",
            detail=f"the ledger already holds a live-or-committed row for this logical effect: "
                   f"{exc}. Exactly one competitor wins (AC-SAFE-014); this attempt is not it.",
        )
    if isinstance(outcome, CheckpointRefused):
        return outcome
    witness, handle = outcome
    return CheckpointAuthorized(witness=witness, handle=handle)


def record_checkpoint_refusal(
    kernel: CheckpointKernel, request: CheckpointRequest, refused: CheckpointRefused,
) -> None:
    """Record a refusal returned by `run_checkpoint_locked`, AFTER the caller has rolled back.

    Public because the locked entry point makes the caller responsible for the ordering that
    `run_checkpoint` performs internally. Same function, same payload, same SD-7 named step.
    """
    _record_refusal(kernel, request, refused)


def run_checkpoint(
    kernel: CheckpointKernel,
    request: CheckpointRequest,
    inputs: CheckpointInputs,
) -> CheckpointAuthorized | CheckpointRefused:
    """THE seven-step atomic checkpoint. One transaction: seven reads, witness insert, grant mint.

    Refusal path: the transaction rolls back (nothing to persist), the refusal is recorded as a
    security event AFTER rollback (so the record survives), the observer is notified, and the
    caller receives outcome (b) with the first failing step named.

    The body is `run_checkpoint_locked`; this owns the transaction around it. A caller that needs
    its OWN write in the checkpoint's commit — machine M2's PL-8 — uses the locked form directly.
    """
    if not isinstance(request, CheckpointRequest) or not isinstance(inputs, CheckpointInputs):
        raise CheckpointError("run_checkpoint takes a CheckpointRequest and CheckpointInputs")
    # The tenant check stays OUTSIDE the transaction, exactly where it has always been: a
    # cross-tenant request must not take the write lock even briefly.
    mismatch = _tenant_mismatch_refusal(kernel, request)
    if mismatch is not None:
        _record_refusal(kernel, request, mismatch)
        return mismatch

    conn = kernel.store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        outcome = run_checkpoint_locked(kernel, request, inputs)
        if isinstance(outcome, CheckpointRefused):
            conn.rollback()
            _record_refusal(kernel, request, outcome)
            return outcome
        conn.commit()
    except BaseException:
        conn.rollback()
        raise

    witness = outcome.witness
    kernel.observe({
        "kind": "CheckpointPassed", "tenant": witness.tenant, "checkpoint_id": witness.checkpoint_id,
        "grant_id": witness.grant_id, "commit_key": witness.commit_key,
    })
    return outcome


# The pinned name for the constitutional mechanism: ADR-004 §2.4 calls it the seven-step atomic
# pre-effect checkpoint, and the registry pins the symbol. One function, two canonical names.
seven_step_checkpoint = run_checkpoint


def _step_passed(kernel: CheckpointKernel, step: int, **detail: Any) -> None:
    """Emit the outcome of a step that PASSED (F-F, and the unit's own observability contract:
    'every checkpoint step outcome, every refusal with the refusing step named').

    The refusal side is emitted by `_record_refusal`, which names the failing step. Together the
    two make the full ladder observable: an observer of a refused checkpoint sees PASS for every
    step before the failing one and REFUSED for that one, so 'which check stopped this, and how
    far did it get' is answerable from the event stream alone rather than from a log line.

    Emission goes through `kernel.observe`, which swallows observer exceptions — observability may
    describe control flow and may never alter it.
    """
    kernel.observe({
        "kind": "CheckpointStep", "step": step, "step_name": CHECKPOINT_STEPS[step - 1],
        "outcome": "PASS", **detail,
    })


def _seven_steps_locked(
    kernel: CheckpointKernel,
    request: CheckpointRequest,
    inputs: CheckpointInputs,
    commit_key_value: str,
    now: datetime,
) -> CheckpointRefused | tuple[CheckpointWitness, EffectGrantHandle]:
    """Steps 1-7 in canonical order, short-circuiting on the first failure (SD-7), followed by
    the witness insert and the grant mint — all under the caller's open transaction.

    ### THE ORDER IS THE CONTRACT, NOT AN IMPLEMENTATION DETAIL (F-D). When several checks would
    fail at once, the EARLIEST canonical step must be the one reported. It decides what the
    operator is told, and the steps are ordered from "the authorization was never valid" to "the
    world moved" to "a human has stopped us": reporting BRAKE_ENGAGED for a request that also has
    no valid approval would send someone to release a brake in order to run something that was
    never authorized. Short-circuiting on the first failure is what makes that true, and
    `test_phase3_step_order.py` proves it against multi-fault inputs.
    """
    effect = request.effect
    gate_entry = kernel.gates.gate_for(effect.action_class)
    approval = inputs.approval

    # ---- STEP 1 — approval validity (present, unexpired, unrevoked, correct authority) -------
    approval_required = gate_entry.gate in _HUMAN_GATES
    if approval_required and approval is None:
        return _step_refusal(1, "MISSING_APPROVAL",
                             f"gate {gate_entry.gate.value} requires a human approval and none was bound")
    if approval is not None:
        if str(approval.actor_kind).upper() != "HUMAN":
            return _step_refusal(
                1, "NONHUMAN_APPROVAL",
                f"approval {approval.approval_id} was granted by actor_kind="
                f"{approval.actor_kind!r}. Only an authenticated human inside the trust boundary "
                f"can create an approval (ADR-003, permanent). Sev-0.",
                sev0="NonHumanApprovalPresented",
            )
        if approval.tenant.strip().lower() != kernel.store.tenant.strip().lower():
            return _step_refusal(
                1, "WRONG_TENANT_APPROVAL",
                f"approval {approval.approval_id} belongs to tenant {approval.tenant!r}",
                sev0="CrossTenantApprovalPresented",
            )
        if approval.state != "GRANTED":
            return _step_refusal(1, f"APPROVAL_{approval.state}",
                                 f"approval {approval.approval_id} is {approval.state}, not GRANTED")
        if now >= _as_utc(approval.expires_at):
            return _step_refusal(1, "APPROVAL_EXPIRED",
                                 "an approval that has expired is not a weaker approval; it is not an approval")
        if gate_entry.required_authority and approval.authority != gate_entry.required_authority:
            return _step_refusal(
                1, "WRONG_AUTHORITY",
                f"gate requires authority {gate_entry.required_authority!r}; approval carries "
                f"{approval.authority!r}")

    _step_passed(kernel, 1, approval_id=(approval.approval_id if approval else None),
                 gate=gate_entry.gate.value, approval_required=approval_required)

    # ---- STEP 2 — material-facts fingerprint (live re-read; drift voids) ---------------------
    try:
        live_facts = inputs.material_facts_reader.read()
    except SourceUnreadable as exc:
        return _step_refusal(2, "SOURCE_UNREADABLE",
                             f"{exc}. A re-read that fails is not 'no drift': we do not execute "
                             f"against a source we could not read.")
    if not isinstance(live_facts, dict) or not all(
        isinstance(f, ProvenancedFact) for f in live_facts.values()
    ):
        return _step_refusal(2, "MALFORMED_FACTS",
                             "the live material-facts read must return {field: ProvenancedFact}")
    try:
        fingerprint_version = approval.fingerprint_version if approval else FINGERPRINT_VERSION
        current_payload = canonical_payload(
            material_fact_set(
                effect=effect,
                commit_key=commit_key_value,
                business_facts=live_facts,
                # The versions THE DECISION READ (row 12): live revalidation of them is step 5's
                # job, so the recompute pins the decision's own versions on both sides.
                entity_versions=(approval.entity_versions if approval
                                 else inputs.proposed_entity_versions),
                policy_version=kernel.gates.policy_version,
            ),
            version=fingerprint_version,
        )
    except FingerprintError as exc:
        return _step_refusal(2, "UNFINGERPRINTABLE_FACTS", str(exc))
    current_fingerprint = hashlib.sha256(current_payload).hexdigest()
    approval_fingerprint: str | None = None
    if approval is not None:
        approval_fingerprint = approval.fingerprint
        if current_fingerprint != approval.fingerprint:
            drift = tuple(drift_diff(approval.canonical_payload, current_payload))
            names = ", ".join(
                f"{d.field}: {d.approved!r} -> {d.current!r}" for d in drift) or "(undiffable)"
            return _step_refusal(
                2, "VOID_ON_DRIFT",
                f"the facts the human approved are no longer the facts. Changed: {names}. "
                f"Nothing has been sent; this is a new question, not an error.",
                drift=drift,
            )

    _step_passed(kernel, 2, material_facts_fingerprint=current_fingerprint,
                 fingerprint_version=fingerprint_version, drift=False)

    # ---- STEP 3 — projected-state freshness (live, never a cache) ----------------------------
    try:
        live_projection = inputs.projected_state_reader.read()
    except SourceUnreadable as exc:
        return _step_refusal(3, "PROJECTION_SOURCE_UNREADABLE",
                             f"{exc}. 'Could not check freshness' is a refusal, never a pass.")
    if not isinstance(live_projection, dict):
        return _step_refusal(3, "MALFORMED_PROJECTION",
                             "the projected-state live read must return a mapping")
    stale = {
        k: (inputs.projection_assertion.get(k), live_projection.get(k))
        for k in set(inputs.projection_assertion) | set(live_projection)
        if inputs.projection_assertion.get(k) != live_projection.get(k)
    }
    if stale:
        return _step_refusal(
            3, "PROJECTED_STATE_STALE",
            "the projection this proposal was built on no longer matches the authoritative "
            f"source: {sorted(stale)}")

    _step_passed(kernel, 3, projected_observations=sorted(inputs.projection_assertion))

    # ---- STEP 4 — native-state validity (unretracted, unsuperseded, not conflicting) ---------
    for claim in inputs.native_claims:
        if claim.status != "ACTIVE":
            return _step_refusal(4, f"CLAIM_{claim.status}",
                                 f"native claim {claim.claim_id} is {claim.status}")
        if claim.conflicting:
            return _step_refusal(4, "CLAIM_CONFLICTING",
                                 f"native claim {claim.claim_id} is in open conflict; a "
                                 f"conflicting field blocks (ADR-002 C6)")
    for name, fact in sorted(live_facts.items()):
        if fact.provenance is ProvenanceClass.MODEL_INFERRED:
            return _step_refusal(
                4, "MODEL_INFERRED_MATERIAL_FACT",
                f"material fact {name!r} is MODEL_INFERRED: a guess cannot gate a consequential "
                f"action at any confidence (AC-SAFE-015)")
        if fact.evidence_condition is not EvidenceCondition.CONSISTENT:
            return _step_refusal(
                4, "EVIDENCE_NOT_CONSISTENT",
                f"material fact {name!r} has evidence_condition="
                f"{fact.evidence_condition.value!r}; unknown is not consistent (ADR-002 C5)")

    _step_passed(kernel, 4, native_claims=[c.claim_id for c in inputs.native_claims],
                 material_facts=sorted(live_facts))

    # ---- STEP 5 — entity-version concurrency (the SD-3 pin set, derived) ---------------------
    required_entities = _sd3_pin_set(request, live_facts, gate_entry)
    pinned_source = approval.entity_versions if approval else inputs.proposed_entity_versions
    try:
        live_versions = inputs.entity_version_reader.read()
    except SourceUnreadable as exc:
        return _step_refusal(5, "ENTITY_VERSIONS_UNREADABLE", str(exc))
    if not isinstance(live_versions, dict):
        return _step_refusal(5, "MALFORMED_ENTITY_VERSIONS",
                             "the entity-version live read must return a mapping")
    pinned: dict[str, int] = {}
    for entity in sorted(required_entities):
        if entity not in pinned_source:
            return _step_refusal(
                5, "UNPINNED_MATERIAL_ENTITY",
                f"entity {entity!r} is in the SD-3 pin set but the decision pinned no version "
                f"for it. Under-pinning is a specification violation, not an optimization.")
        if entity not in live_versions:
            return _step_refusal(5, "ENTITY_VERSION_UNREADABLE",
                                 f"no live version for pinned entity {entity!r}")
        if int(live_versions[entity]) != int(pinned_source[entity]):
            return _step_refusal(
                5, "ENTITY_VERSION_DRIFT",
                f"entity {entity!r} moved: pinned v{pinned_source[entity]}, live "
                f"v{live_versions[entity]}. The world changed; the checkpoint fails (ADR-009).")
        pinned[entity] = int(pinned_source[entity])

    _step_passed(kernel, 5, entity_versions=dict(sorted(pinned.items())))

    # ---- STEP 6 — policy evaluation (the gate decision is never null) ------------------------
    if gate_entry.gate is GateDecision.FORBIDDEN:
        return _step_refusal(6, "FORBIDDEN_ACTION_CLASS",
                             f"{effect.action_class!r} is FORBIDDEN: no approval unlocks it")
    if approval is not None and approval.policy_version != kernel.gates.policy_version:
        return _step_refusal(
            6, "POLICY_VERSION_DRIFT",
            f"the approval was granted under policy {approval.policy_version!r}; current is "
            f"{kernel.gates.policy_version!r}. You cannot act under a policy that no longer "
            f"exists (ADR-010 §7.4).")
    if gate_entry.gate is GateDecision.AUTONOMOUS_WITHIN_CAPS:
        caps = gate_entry.caps or Caps()
        if caps.max_per_day is not None and inputs.runs_today >= caps.max_per_day:
            return _step_refusal(6, "CAP_EXCEEDED",
                                 f"daily cap {caps.max_per_day} reached ({inputs.runs_today} today)")
        if caps.max_amount_minor is not None:
            amount_fact = live_facts.get(caps.amount_field)
            if amount_fact is None:
                return _step_refusal(
                    6, "CAP_UNEVALUABLE",
                    f"the value cap needs material fact {caps.amount_field!r} and it is absent; "
                    f"an unevaluable cap is a refusal, not a pass")
            amount = amount_fact.value  # the GATING accessor: raises on MODEL_INFERRED
            amount_minor = getattr(amount, "amount_minor", None)
            if amount_minor is None:
                return _step_refusal(6, "CAP_UNEVALUABLE",
                                     f"material fact {caps.amount_field!r} is not Money")
            if int(amount_minor) > caps.max_amount_minor:
                return _step_refusal(
                    6, "CAP_EXCEEDED",
                    f"{amount_minor} minor units exceeds the {caps.max_amount_minor} cap")

    _step_passed(kernel, 6, gate_decision=gate_entry.gate.value,
                 policy_version=kernel.gates.policy_version, runs_today=inputs.runs_today)

    # ---- STEP 7 — human-brake admission (read inside this same transaction) ------------------
    try:
        denied_by = kernel.brakes.admission_denied(
            tenant=kernel.store.tenant, action_class=effect.action_class)
    except BrakeStoreUnreachable as exc:
        return _step_refusal(7, "BRAKE_UNREADABLE",
                             f"{exc}. 'Cannot read the brake' NEVER means 'off'.")
    if denied_by is not None:
        return _step_refusal(
            7, "BRAKE_ENGAGED",
            f"brake {denied_by.brake_id} ({denied_by.scope}) is ACTIVE: engaged by "
            f"{denied_by.actor} ({denied_by.actor_kind}) because {denied_by.engaged_reason!r}")
    try:
        brake_token = kernel.brakes.version_token(tenant=kernel.store.tenant)
        # Read for the record, not for the decision: the admission decision above already stands.
        # Inside the same fail-closed try because an unreadable brake store is a refusal at step 7
        # no matter which of its reads discovered it.
        platform = kernel.brakes.platform_status()
        tenant_actives = [b for b in kernel.brakes.active_report(tenant=kernel.store.tenant)
                          if b.tenant is not None]   # tenant is None => the platform row
    except BrakeStoreUnreachable as exc:
        return _step_refusal(7, "BRAKE_UNREADABLE", str(exc))

    # Step 7 is the only step whose PASS carries the state it read: the brake report IS the
    # incident timeline (16-brake.md point 30), and "which brake was consulted, in what state, at
    # what version" must be answerable for BOTH scope owners — the platform row and this tenant's
    # rows — because `brake_version` is per scope-owner and the claim CAS revalidates the composite.
    _step_passed(
        kernel, 7,
        brake_version=brake_token,
        platform_brake_state=platform.state,
        platform_brake_version=platform.brake_version,
        tenant_active_brakes=[b.brake_id for b in tenant_actives],
    )

    # ---- all seven passed: witness + mint, same transaction ----------------------------------
    passed = _mint_checkpoint_passed(
        checkpoint_id=str(uuid.uuid4()), tenant=kernel.store.tenant, commit_key=commit_key_value)
    return mint_grant(
        kernel,
        witness=passed,
        request=request,
        gate_entry=gate_entry,
        approval=approval,
        material_facts_fingerprint=current_fingerprint,
        approval_fingerprint=approval_fingerprint,
        entity_versions=pinned,
        brake_token=brake_token,
        projected_observations=tuple(sorted(inputs.projection_assertion)),
        native_claims=tuple(c.claim_id for c in inputs.native_claims),
        now=now,
    )


def _sd3_pin_set(
    request: CheckpointRequest,
    live_facts: dict[str, ProvenancedFact],
    gate_entry: GateEntry,
) -> set[str]:
    """SD-3, mechanically: {every entity a material fact references} ∪ {the target} ∪ {every
    gate-precondition entity}. Derived by the kernel — a caller cannot under-pin by omission."""
    required = {f.entity_ref for f in live_facts.values() if f.entity_ref}
    required.add(request.target_entity_ref)
    required.update(gate_entry.precondition_entities)
    return {str(e) for e in required if str(e or "").strip()}


def _fingerprint_facts(live_facts: dict[str, ProvenancedFact]) -> dict[str, Any]:
    """The fingerprint fact set: value + provenance + evidence condition per field (ADR-005 §3.2
    rows 9-10 — the same number believed for a different reason is a different fact)."""
    out: dict[str, Any] = {}
    for name, fact in live_facts.items():
        out[name] = {
            "value": fact.fingerprint_value,
            "provenance": fact.provenance,
            "evidence": fact.evidence_condition,
        }
    return out


def material_fact_set(
    *,
    effect: LogicalEffect,
    commit_key: str,
    business_facts: dict[str, ProvenancedFact],
    entity_versions: dict[str, int],
    policy_version: str,
) -> dict[str, Any]:
    """The COMPLETE material fact set of ADR-005 §3.2, composed one way, everywhere.

    Rows 1-4 (tenant, action class, target, commit key) make scope creep drift (F-22: an approval
    for load 4471 presented for 4472 recomputes differently). Rows 9-10 travel inside each fact.
    Row 11 (policy_version) makes a policy change void in-flight approvals at step 2 with a diff
    that names the policy (ADR-005 §3.11). Row 12 pins the versions THE DECISION READ — step 5
    revalidates them against the live world, so version drift is step 5's finding, not a payload
    disagreement. Row 13 (fingerprint_version) is the hashed envelope itself.

    Approval composition at proposal time and checkpoint recomputation at step 2 MUST both call
    this function: two composition rules would be two fingerprints for one fact set.
    """
    return {
        "effect": {
            "tenant": effect.tenant,
            "action_class": effect.action_class,
            "target_system": effect.target_system,
            "target_resource_id": effect.target_resource_id,
            "target_operation": effect.target_operation,
            "commit_key": commit_key,
        },
        "facts": _fingerprint_facts(business_facts),
        # As a sorted collection, not a mapping: an EMPTY pin set is then a stated fact
        # ("entity_versions=[]") rather than an unserializable nothing — and an unpinned
        # decision must reach step 5's UNPINNED_MATERIAL_ENTITY refusal, not die at
        # composition wearing a serializer error.
        "entity_versions": [f"{k}:{int(v)}" for k, v in sorted(entity_versions.items())],
        "policy_version": str(policy_version),
    }


def mint_checkpoint_witness(
    kernel: CheckpointKernel,
    *,
    witness: CheckpointPassed,
    row: dict[str, Any],
) -> CheckpointWitness:
    """Insert the immutable witness row for a genuine, unconsumed CheckpointPassed.

    Refuses anything not minted by this process's checkpoint function: an object.__new__ shell,
    a pickle round-trip, a copy, or a subclass impostor. Called only from mint_grant, inside the
    checkpoint transaction (entity 05 §15: witness insert and grant mint are ONE transaction; no
    asynchronous work in between, M-40) — the pass arrives already consumed BY that mint, which
    is the one consumption this check must not mistake for reuse. A direct call with a fresh
    genuine pass cannot fabricate a floating witness either: the row's tenant-consistent foreign
    key requires the grant row, so a witness without its grant is refused by the database.
    """
    _require_genuine(witness, allow_consumed_by_current_mint=True)
    kernel.store.conn.execute(
        """
        INSERT INTO checkpoint_witnesses (
            tenant, checkpoint_id, grant_id, actor, accountable_owner, action_class,
            target_system, target_resource_id, target_operation, commit_key,
            material_facts_fingerprint, entity_versions_json, approval_id, approval_fingerprint,
            policy_version, gate_decision, autonomy_state, brake_version,
            projected_observations_json, native_claims_json, created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["tenant"], row["checkpoint_id"], row["grant_id"], row["actor"],
            row["accountable_owner"], row["action_class"], row["target_system"],
            row["target_resource_id"], row["target_operation"], row["commit_key"],
            row["material_facts_fingerprint"], json.dumps(row["entity_versions"], sort_keys=True),
            row["approval_id"], row["approval_fingerprint"], row["policy_version"],
            row["gate_decision"], row["autonomy_state"], row["brake_version"],
            json.dumps(sorted(row["projected_observations"])),
            json.dumps(sorted(row["native_claims"])), row["created_at"], row["expires_at"],
        ),
    )
    return CheckpointWitness(
        tenant=row["tenant"], checkpoint_id=row["checkpoint_id"], grant_id=row["grant_id"],
        actor=row["actor"], accountable_owner=row["accountable_owner"],
        action_class=row["action_class"], target_system=row["target_system"],
        target_resource_id=row["target_resource_id"], target_operation=row["target_operation"],
        commit_key=row["commit_key"], material_facts_fingerprint=row["material_facts_fingerprint"],
        entity_versions=dict(row["entity_versions"]), approval_id=row["approval_id"],
        approval_fingerprint=row["approval_fingerprint"], policy_version=row["policy_version"],
        gate_decision=GateDecision(row["gate_decision"]), autonomy_state=row["autonomy_state"],
        brake_version=row["brake_version"],
        projected_observations_used=tuple(sorted(row["projected_observations"])),
        native_claims_used=tuple(sorted(row["native_claims"])),
        created_at=row["created_at"], expires_at=row["expires_at"],
    )


def mint_grant(
    kernel: CheckpointKernel,
    *,
    witness: CheckpointPassed,
    request: CheckpointRequest,
    gate_entry: GateEntry,
    approval: ApprovalRecord | None,
    material_facts_fingerprint: str,
    approval_fingerprint: str | None,
    entity_versions: dict[str, int],
    brake_token: str,
    projected_observations: tuple[str, ...],
    native_claims: tuple[str, ...],
    now: datetime,
) -> tuple[CheckpointWitness, EffectGrantHandle]:
    """EF-1: mint the grant row and its witness in the surrounding checkpoint transaction.

    `witness: CheckpointPassed` is the required, non-forgeable first-class argument (ADR-004
    §3.1): code that has not passed the checkpoint has nothing to pass here. The pass is
    CONSUMED — a second mint from the same pass is refused, preserving witness : grant = 1 : 1.
    """
    _require_genuine(witness)
    witness._consumed = True

    effect = request.effect
    grant_id = str(uuid.uuid4())
    token = os.urandom(32).hex()
    created_at = _iso(now)
    witness_expires = _iso(now + kernel.witness_window)
    grant_expires = _iso(now + kernel.grant_ttl)

    kernel.store.conn.execute(
        """
        INSERT INTO effect_grants (
            tenant, grant_id, commit_key, action_class, target_system, target_resource_id,
            target_operation, state, approved_amount, material_facts_json,
            checkpoint_id, material_facts_fingerprint, entity_versions_json, gate_decision,
            policy_version, brake_version, approval_id, expires_at, handle_digest,
            payload_json, issued_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'GRANTED', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kernel.store.tenant, grant_id, witness.commit_key, effect.action_class,
            effect.target_system, effect.target_resource_id, effect.target_operation,
            json.dumps({"fingerprint": material_facts_fingerprint,
                        "fingerprint_version": approval.fingerprint_version if approval
                        else FINGERPRINT_VERSION}, sort_keys=True),
            witness.checkpoint_id, material_facts_fingerprint,
            json.dumps(entity_versions, sort_keys=True), gate_entry.gate.value,
            kernel.gates.policy_version, brake_token,
            approval.approval_id if approval else None, grant_expires,
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            json.dumps({"minted_by": "checkpoint"}, sort_keys=True), created_at, created_at,
        ),
    )
    witness_record = mint_checkpoint_witness(
        kernel,
        witness=witness,
        row={
            "tenant": kernel.store.tenant, "checkpoint_id": witness.checkpoint_id,
            "grant_id": grant_id, "actor": request.actor,
            "accountable_owner": request.accountable_owner, "action_class": effect.action_class,
            "target_system": effect.target_system,
            "target_resource_id": effect.target_resource_id,
            "target_operation": effect.target_operation, "commit_key": witness.commit_key,
            "material_facts_fingerprint": material_facts_fingerprint,
            "entity_versions": entity_versions,
            "approval_id": approval.approval_id if approval else None,
            "approval_fingerprint": approval_fingerprint,
            "policy_version": kernel.gates.policy_version,
            "gate_decision": gate_entry.gate.value,
            "autonomy_state": gate_entry.gate.value,
            "brake_version": brake_token,
            "projected_observations": projected_observations,
            "native_claims": native_claims,
            "created_at": created_at, "expires_at": witness_expires,
        },
    )
    handle = EffectGrantHandle(
        tenant=kernel.store.tenant, grant_id=grant_id, token=token, signature=kernel.sign(token))
    return witness_record, handle


def _require_genuine(
    witness: CheckpointPassed, *, allow_consumed_by_current_mint: bool = False,
) -> None:
    if type(witness) is not CheckpointPassed:
        raise CheckpointError(
            f"mint requires a CheckpointPassed; got {type(witness).__name__}. There is no other "
            f"key to this door.")
    if witness not in _GENUINE_PASSES:
        raise CheckpointError(
            "this CheckpointPassed was not produced by the checkpoint function in this process: "
            "a reconstructed, copied or forged pass mints nothing (M-47)")
    if witness._consumed and not allow_consumed_by_current_mint:
        raise CheckpointError(
            "this CheckpointPassed is already consumed: a witness authorizes exactly one mint "
            "(witness : grant = 1 : 1)")


# ------------------------------------------------------------------ the claim CAS


def claim_grant_cas(
    kernel: CheckpointKernel,
    handle: EffectGrantHandle,
    params: ClaimParams,
    *,
    now: datetime | None = None,
) -> ClaimOutcome:
    """EF-2: the atomic GRANTED -> CLAIMED compare-and-set — the sole serialization point of the
    effect. Zero rows updated => the caller does NOTHING.

    In order (ADR-004 §3.7, the P3-owned prefix of the adapter algorithm):
      1 verify the handle signature (cheap filter, no DB round-trip on garbage)
      2 load the grant row; a WELL-FORMED handle naming no row is a Sev-0 — someone is minting
      3 validate the witness: exists, 1:1 with this grant, and FRESH (the two-key rule)
      4 the confusion check: the grant revalidated against the caller's OWN parameters; any
        mismatch is a Sev-0 security event, not an error
      5 the CAS itself, revalidating state, expiry, brake token and policy version INSIDE the
        UPDATE's WHERE clause — a brake or policy change between mint and claim matches zero rows

    ### THE WHERE CLAUSE'S SIX PREDICATES, AND WHICH ARE DEFENSE IN DEPTH (finding F-I).
    `grant_id`, `state = 'GRANTED'`, `brake_version` and `policy_version` are each load-bearing on
    their own: remove any one and a case in test_phase3_claim_cas.py goes green on a claim that
    had to be refused. The other two are DEFENSE IN DEPTH, and recording that is the point — an
    undocumented redundant control is one somebody later deletes as dead code:

      * `expires_at > ?` — masked by two earlier controls. The witness-freshness check above
        refuses first, and always can, because `CheckpointKernel.__init__` forbids
        `witness_window > grant_ttl`, so a witness can never outlive its grant; and
        `expire_unclaimed()` flips a lapsed row out of GRANTED, after which `state = 'GRANTED'`
        refuses it. It still fires against clock skew, a shortened TTL and a directly tampered
        row, and `test_the_cas_expires_at_predicate_refuses_a_lapsed_grant_with_a_still_fresh_
        witness` proves it by isolating exactly that state. The MASKING INVARIANT itself is
        guarded by `test_the_masking_invariant_behind_the_expires_at_predicate_is_still_enforced`,
        so the constructor refusal cannot be removed — silently promoting this predicate to
        load-bearing — without a test failing.
      * `tenant = ?` — masked by the row load above (already keyed on `(tenant, grant_id)`) and by
        the confused-deputy comparison of `row["tenant"]` against `params.tenant`. It still fires
        when two tenants hold the same `grant_id`, and its absence would be nearly invisible: this
        claim would refuse on rowcount while the OTHER tenant's grant had already been transitioned
        to CLAIMED underneath it. Proved by
        `test_the_cas_tenant_predicate_protects_another_tenants_identically_named_grant`.

    CLAUDE.md §11 forbids this WHERE clause from ever losing a predicate, so the set is ALSO
    checked structurally, by membership, in `test_the_cas_where_clause_still_carries_all_five_
    predicates` — the only way the removal of a masked predicate is visible at all.
    """
    pending = claim_grant_cas_locked_outside_a_transaction(kernel, handle, params, now=now)
    return flush_claim_records(kernel, pending)


@dataclass(frozen=True, slots=True)
class PendingClaimRecords:
    """A locked claim's decision, plus the records it owes ONCE the caller has settled the commit.

    ### THE RECORDS CANNOT BE WRITTEN INSIDE THE TRANSACTION THAT IS ABOUT TO BE ABANDONED.
    Every refusal path of the claim CAS rolls the transaction back and THEN writes its
    `security_events` row, in that order, because a Sev-0 written inside the rolled-back transaction
    vanishes with it — the exact defect M1's `IllegalTransitionAttempted` path was corrected for.
    When the transaction belongs to the caller, so does that ordering, so the decision and its
    pending records are returned together and `flush_claim_records` is called afterwards.

    `security` is written before `observations`, preserving the interleaving the transactional form
    has always had (`StaleWitnessUsed` is recorded, then `ClaimRefused` is observed).
    """

    outcome: ClaimOutcome
    security: tuple[tuple[str, dict[str, Any]], ...] = ()
    observations: tuple[dict[str, Any], ...] = ()


def flush_claim_records(kernel: CheckpointKernel, pending: PendingClaimRecords) -> ClaimOutcome:
    """Write a locked claim's owed records and hand back its outcome. Call AFTER commit/rollback."""
    for event_type, payload in pending.security:
        _security(kernel, event_type, payload)
    for observation in pending.observations:
        kernel.observe(observation)
    return pending.outcome


def claim_grant_cas_locked(
    kernel: CheckpointKernel,
    handle: EffectGrantHandle,
    params: ClaimParams,
    *,
    now: datetime | None = None,
) -> PendingClaimRecords:
    """EF-2's CAS, INSIDE THE CALLER'S OPEN TRANSACTION. Neither commits nor rolls back.

    ### WHY THIS EXISTS. `02-pipeline-instance.machine.md` §14 PL-9 co-commits *"M3 `CLAIMED` + M4
    `ApprovalConsumed` + `EffectAttempted`"* with the pipeline's own `GRANTED → CLAIMED`, and §30
    states the property that co-commit buys: *"a brake engaged between PL-8 and PL-9 makes the CAS
    match zero rows — the adapter does nothing (**never both, never neither**)."* A machine that
    claimed the grant in one transaction and moved its own row in another could be interrupted
    between them, which is precisely "both" or "neither".

    This is an EXTRACTION of the body `claim_grant_cas` already had. **The WHERE clause is
    untouched and keeps all six predicates** (CLAUDE.md §11 forbids it losing one, and
    `test_the_cas_where_clause_still_carries_all_five_predicates` checks the set structurally).
    Every refusal cause, every Sev-0 and every observation is the same; what moved is who owns the
    transaction and, with it, who writes the records afterwards.

    The caller MUST: commit iff `outcome.claimed`, roll back otherwise, then `flush_claim_records`.
    """
    return _claim_locked(kernel, handle, params, now=now, own_transaction=False)


def claim_grant_cas_locked_outside_a_transaction(
    kernel: CheckpointKernel,
    handle: EffectGrantHandle,
    params: ClaimParams,
    *,
    now: datetime | None = None,
) -> PendingClaimRecords:
    """The transactional form's body: opens and settles its own transaction, defers its records."""
    return _claim_locked(kernel, handle, params, now=now, own_transaction=True)


def _claim_locked(
    kernel: CheckpointKernel,
    handle: EffectGrantHandle,
    params: ClaimParams,
    *,
    now: datetime | None,
    own_transaction: bool,
) -> PendingClaimRecords:
    """ONE text of the claim decision, whichever side of the transaction boundary the caller is on.

    `own_transaction` decides only who calls BEGIN/COMMIT/ROLLBACK. It decides nothing about the
    checks, their order, the WHERE clause or the recorded causes — two copies of this body is how
    one of them quietly stops revalidating the brake.
    """
    when = (now or kernel.now())
    if when.tzinfo is None:
        raise CheckpointError("claim time must be timezone-aware UTC")
    when = when.astimezone(timezone.utc)
    store = kernel.store

    def settle(commit: bool) -> None:
        if not own_transaction:
            return
        conn.commit() if commit else conn.rollback()

    if not hmac.compare_digest(kernel.sign(handle.token), handle.signature):
        return PendingClaimRecords(
            outcome=ClaimOutcome(
                claimed=False, cause="INVALID_HANDLE_SIGNATURE", grant_id=handle.grant_id),
            observations=({"kind": "ClaimRefused", "cause": "INVALID_HANDLE_SIGNATURE",
                           "grant_id": handle.grant_id},),
        )

    conn = store.conn
    if own_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT * FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (store.tenant, handle.grant_id),
        ).fetchone()
        if row is None:
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(
                    claimed=False, cause="NO_SUCH_GRANT", grant_id=handle.grant_id),
                security=(("WellFormedHandleNamesNoRow", {
                    "grant_id": handle.grant_id,
                    "why": "a correctly-signed handle naming no ledger row means someone is minting "
                           "handles outside the checkpoint",
                }),),
            )
        if row["handle_digest"] != hashlib.sha256(handle.token.encode("utf-8")).hexdigest():
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(
                    claimed=False, cause="HANDLE_DIGEST_MISMATCH", grant_id=handle.grant_id),
                security=(("HandleDigestMismatch", {"grant_id": handle.grant_id}),),
            )

        witness_row = conn.execute(
            "SELECT * FROM checkpoint_witnesses WHERE tenant = ? AND checkpoint_id = ?",
            (store.tenant, row["checkpoint_id"]),
        ).fetchone() if row["checkpoint_id"] else None
        if witness_row is None:
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(claimed=False, cause="NO_WITNESS", grant_id=handle.grant_id),
                security=(("GrantWithoutWitness", {
                    "grant_id": handle.grant_id,
                    "why": "a claimable grant must be checkpoint-bound; a grant with no witness is "
                           "not claimable under the two-key rule",
                }),),
            )
        if witness_row["grant_id"] != handle.grant_id:
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(
                    claimed=False, cause="WITNESS_GRANT_MISMATCH", grant_id=handle.grant_id),
                security=(("WitnessGrantMismatch", {"grant_id": handle.grant_id}),),
            )
        if _iso(when) >= witness_row["expires_at"]:
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(
                    claimed=False, cause="STALE_WITNESS", grant_id=handle.grant_id),
                security=(("StaleWitnessUsed", {
                    "grant_id": handle.grant_id, "witness_expired_at": witness_row["expires_at"],
                    "attempted_at": _iso(when),
                }),),
                observations=({"kind": "ClaimRefused", "cause": "STALE_WITNESS",
                               "grant_id": handle.grant_id},),
            )

        mismatches = {
            name: (row[column], got)
            for name, column, got in (
                ("tenant", "tenant", params.tenant),
                ("action_class", "action_class", params.action_class),
                ("target_system", "target_system", params.target_system),
                ("target_resource_id", "target_resource_id", params.target_resource_id),
                ("target_operation", "target_operation", params.target_operation),
            )
            if row[column] != got
        }
        if mismatches:
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(
                    claimed=False, cause="CONFUSED_DEPUTY", grant_id=handle.grant_id),
                security=(("ConfusedDeputyRefused", {
                    "grant_id": handle.grant_id,
                    "mismatches": {k: {"grant": a, "caller": b}
                                   for k, (a, b) in sorted(mismatches.items())},
                    "why": "a grant for one effect was presented alongside parameters for another",
                }),),
            )

        try:
            current_brake_token = kernel.brakes.version_token(tenant=store.tenant)
        except BrakeStoreUnreachable:
            settle(False)
            return PendingClaimRecords(
                outcome=ClaimOutcome(
                    claimed=False, cause="BRAKE_UNREADABLE", grant_id=handle.grant_id),
                observations=({"kind": "ClaimRefused", "cause": "BRAKE_UNREADABLE",
                               "grant_id": handle.grant_id},),
            )
        cur = conn.execute(
            """
            UPDATE effect_grants
               SET state = 'CLAIMED', claimed_at = ?
             WHERE tenant = ? AND grant_id = ? AND state = 'GRANTED'
               AND expires_at > ? AND brake_version = ? AND policy_version = ?
            """,
            (_iso(when), store.tenant, handle.grant_id, _iso(when), current_brake_token,
             kernel.gates.policy_version),
        )
        if cur.rowcount == 1:
            settle(True)
            return PendingClaimRecords(
                outcome=ClaimOutcome(claimed=True, cause="CLAIMED", grant_id=handle.grant_id,
                                     transition=GRANTED_TO_CLAIMED),
                observations=({"kind": "GrantClaimed", "grant_id": handle.grant_id,
                               "tenant": store.tenant, "transition": GRANTED_TO_CLAIMED},),
            )
        # Zero rows: the adapter does nothing. Name the cause honestly from the row we hold —
        # the write lock means it cannot have changed under us within this transaction.
        cause = "ALREADY_" + row["state"] if row["state"] != "GRANTED" else (
            "EXPIRED" if row["expires_at"] <= _iso(when)
            else "BRAKE_CHANGED" if row["brake_version"] != current_brake_token
            else "POLICY_CHANGED" if row["policy_version"] != kernel.gates.policy_version
            else "UNCLAIMABLE")
        settle(False)
        return PendingClaimRecords(
            outcome=ClaimOutcome(claimed=False, cause=cause, grant_id=handle.grant_id),
            observations=({"kind": "ClaimRefused", "cause": cause,
                           "grant_id": handle.grant_id},),
        )
    except BaseException:
        settle(False)
        raise


# ------------------------------------------------------------------ grant lifecycle (unclaimed)


def expire_unclaimed(kernel: CheckpointKernel, *, now: datetime | None = None) -> int:
    """EF-2x: GRANTED past its TTL becomes EXPIRED_UNCLAIMED — nothing happened. Deterministic
    and clock-injected (the acceptance defaults forbid wall-clock sleeps); durable timers arrive
    with P5. NEVER touches CLAIMED: an expiry that could reach a claimed row would convert 'the
    world may have changed' into 'pretend it did not'."""
    when = _iso((now or kernel.now()).astimezone(timezone.utc))
    conn = kernel.store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE effect_grants SET state = 'EXPIRED_UNCLAIMED' "
            "WHERE tenant = ? AND state = 'GRANTED' AND expires_at IS NOT NULL AND expires_at <= ?",
            (kernel.store.tenant, when),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if cur.rowcount:
        kernel.observe({"kind": "GrantExpired", "count": cur.rowcount})
    return cur.rowcount


def revoke_unclaimed(
    kernel: CheckpointKernel, *, grant_id: str, cause: str, actor: str,
) -> bool:
    """EF-2r: GRANTED -> REVOKED (brake engaged, policy changed, approval revoked) — deliberately
    withdrawn is not the same fact as quietly lapsed, so REVOKED is distinct from
    EXPIRED_UNCLAIMED. Revoking an unclaimed grant is always safe: nothing happened. Revoking a
    CLAIMED grant does nothing — the effect may already exist, and pretending otherwise is how an
    unknown outcome gets laundered into a clean ledger."""
    if not str(cause or "").strip() or not str(actor or "").strip():
        raise CheckpointError("a revocation records its cause and its actor")
    conn = kernel.store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE effect_grants SET state = 'REVOKED' "
            "WHERE tenant = ? AND grant_id = ? AND state = 'GRANTED'",
            (kernel.store.tenant, grant_id),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if cur.rowcount == 1:
        kernel.observe({"kind": "GrantRevoked", "grant_id": grant_id, "cause": cause,
                        "actor": actor})
        return True
    return False


# ------------------------------------------------------------------ internals


def _step_refusal(
    step: int, reason: str, detail: str, *, drift: tuple[DriftedField, ...] = (),
    sev0: str | None = None,
) -> CheckpointRefused:
    return CheckpointRefused(
        step=step, step_name=CHECKPOINT_STEPS[step - 1], reason=reason, detail=detail,
        drift=drift, sev0=sev0)


def _record_refusal(
    kernel: CheckpointKernel, request: CheckpointRequest, refused: CheckpointRefused,
) -> None:
    """Durable observability for a refusal, written AFTER the checkpoint transaction rolled back
    so the record survives the rollback. The refusing step is always named (SD-7)."""
    payload = {
        "step": refused.step, "step_name": refused.step_name, "reason": refused.reason,
        "detail": refused.detail, "action_class": request.effect.action_class,
        "target": request.effect.target_resource_id,
        "drift": [
            {"field": d.field, "approved": d.approved, "current": d.current} for d in refused.drift
        ],
    }
    try:
        kernel.store.add_security_event(
            refused.sev0 or "CheckpointRefused", actor=request.actor, payload=payload)
    except Exception:  # noqa: BLE001 — a refusal must reach the caller even if recording fails
        pass
    kernel.observe({"kind": "CheckpointFailed", **payload})


def _refuse(
    kernel: CheckpointKernel, request: CheckpointRequest, *, step: int, reason: str, detail: str,
) -> CheckpointRefused:
    refused = CheckpointRefused(
        step=step, step_name=CHECKPOINT_STEPS[step - 1], reason=reason, detail=detail)
    _record_refusal(kernel, request, refused)
    return refused


def _security(kernel: CheckpointKernel, event_type: str, payload: dict[str, Any]) -> None:
    """A Sev-0 security event, durably recorded outside the rolled-back transaction."""
    try:
        kernel.store.add_security_event(event_type, actor="checkpoint-kernel", payload=payload)
    except Exception:  # noqa: BLE001
        pass
    kernel.observe({"kind": "Sev0", "event_type": event_type, **payload})


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise CheckpointError("timestamps entering the checkpoint must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
