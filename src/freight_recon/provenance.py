"""P7 — the provenance-safety core: the six canonical classes as ONE authority (AC-2) and the three
rules that make `provenance_class` load-bearing rather than decorative — R-P1 (runtime assignment),
R-P2 (no laundering) and R-P3 (`OWNER_ASSERTED` is never machine-recomputed) — plus the AC-4 /
AC-SAFE-015 rule that a `MODEL_INFERRED` fact may never be read by a consequential gate.

### ONE AUTHORITY, NOT A SECOND. The six classes are the KERNEL's `ProvenanceClass`
(`checkpoint.py`), reused here — this module DEFINES no second enum and MINTS no gate. The kernel's
`ProvenancedFact.value` is the enforcing gate accessor (it raises `GateReadOfInferredFact` on
`MODEL_INFERRED`); this module states the same rule as a predicate and is proven CONSISTENT with the
kernel by `test_phase7_provenance.py`. M5's and M6's per-migration provenance vocabularies are proven
to be exactly the same six. Two answers to "how do we know this?" is the defect a single authority
exists to prevent.

WHAT EACH RULE MEANS, IN FREIGHT TERMS

  * R-P1 (ADR-002 sec 2.3.1) — a value's provenance is assigned BY THE RUNTIME, from HOW it was
    obtained, at the moment of creation. A model never chooses it; inbound content never carries it;
    no API untrusted data reaches may set it. *"The rate confirmation says GBP 2,850"* is
    `MODEL_EXTRACTED` because a model READ it off a retained artifact — a fact about how we got it,
    not a label the artifact supplied.

  * R-P2 (ADR-002 sec 2.3.1) — provenance may be WEAKENED, never silently STRENGTHENED. A
    `MODEL_INFERRED` guess can never become `LINKER_INFERRED` — or anything stronger — by being
    copied, cached, re-observed, reconciled, serialized or crossed over a process boundary. The ONLY
    strengthening route is a NEW authenticated human act, which creates a new `OWNER_ASSERTED` claim
    that supersedes the old one and retains it.

  * R-P3 (ADR-002 sec 2.3.1, the L-A defect) — machine recomputation may NEVER overwrite an
    `OWNER_ASSERTED` value. The attempt fails closed and preserves the owner's value; a disagreement
    is a Conflict, never a silent overwrite.

  * AC-4 / AC-SAFE-015 (ADR-002 sec 2.3) — a `MODEL_INFERRED` fact may NEVER gate a consequential
    action, under any confidence score. There is no confidence: the gate-read refuses structurally.

SHIPS DARK. Nothing in production imports this module; it mints no gate and emits no canonical event
(the F14 `ProvenanceStrengtheningAttempted` audit-emission is a separable, registered concern; this
layer carries the REFUSAL, which is the safety). Only `scripts/probe_phase7_provenance.py` and the
Phase-7 tests reach it.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import dataclass

# ### THE ONE CLASS AUTHORITY AND THE ONE GATE-READ EXCEPTION — the kernel's, reused.
from .checkpoint import GateReadOfInferredFact, ProvenanceClass

# AC-2: the six, DERIVED from the kernel enum rather than re-listed — so there cannot be a second,
# drifting definition. A count match with different members must fail; the test asserts exact set
# equality against the six authoritative identifiers.
PROVENANCE_CLASSES: tuple[ProvenanceClass, ...] = tuple(ProvenanceClass)
PROVENANCE_CLASS_VALUES: frozenset[str] = frozenset(pc.value for pc in ProvenanceClass)

# The trust hierarchy, read directly out of ADR-002 sec 2.3's table (the "may it gate a consequential
# action?" and "may a machine recompute it?" columns) — NOT an invented freight rule. It is used ONLY
# to decide what counts as STRENGTHENING for R-P2. It authorizes nothing: like confidence, rank never
# gates.
_TRUST_RANK: dict[ProvenanceClass, int] = {
    ProvenanceClass.MODEL_INFERRED: 0,   # a guess — "may it gate? NEVER". The floor.
    ProvenanceClass.MODEL_EXTRACTED: 1,  # a checkable reading — may EVIDENCE a field, never CHOOSE one.
    ProvenanceClass.LINKER_INFERRED: 2,  # a deterministic registered rule — recomputable, may gate.
    ProvenanceClass.RECONCILED: 2,       # >=2 sources under a rule — carries its inputs, may gate.
    ProvenanceClass.SYSTEM_IMPORTED: 2,  # an external system of record — re-importable, may gate.
    ProvenanceClass.OWNER_ASSERTED: 3,   # an authenticated human — "may a machine recompute? NEVER". The ceiling.
}

# AC-4 / AC-SAFE-015: the classes a consequential gate MUST NOT read. Exactly one — a guess.
_GATE_FORBIDDEN: frozenset[ProvenanceClass] = frozenset({ProvenanceClass.MODEL_INFERRED})

# The six paths a value may travel through and STILL keep its provenance (R-P2). Named so the
# anti-laundering sweep is a proven, non-empty population rather than an ad-hoc check.
DERIVATION_PATHS: tuple[str, ...] = (
    "copy", "cache", "re_observe", "reconcile", "serialize", "process_boundary",
)


class Acquisition(enum.Enum):
    """HOW a value was obtained — the ONLY input to runtime provenance assignment (R-P1). The runtime
    knows how it got a value; a model never chooses this, and it is never read from inbound content."""

    EXTERNAL_SYSTEM_OF_RECORD = "external_system_of_record"
    AUTHENTICATED_HUMAN_ACT = "authenticated_human_act"
    DETERMINISTIC_RULE = "deterministic_rule"
    MODEL_READ_FROM_ARTIFACT = "model_read_from_artifact"
    MODEL_GUESS = "model_guess"
    RECONCILIATION_OF_SOURCES = "reconciliation_of_sources"


# The R-P1 assignment map, straight from ADR-002 sec 2.3's "Meaning" column. This is the whole of
# "assigned from how the value was actually obtained".
_BY_ACQUISITION: dict[Acquisition, ProvenanceClass] = {
    Acquisition.EXTERNAL_SYSTEM_OF_RECORD: ProvenanceClass.SYSTEM_IMPORTED,
    Acquisition.AUTHENTICATED_HUMAN_ACT: ProvenanceClass.OWNER_ASSERTED,
    Acquisition.DETERMINISTIC_RULE: ProvenanceClass.LINKER_INFERRED,
    Acquisition.MODEL_READ_FROM_ARTIFACT: ProvenanceClass.MODEL_EXTRACTED,
    Acquisition.MODEL_GUESS: ProvenanceClass.MODEL_INFERRED,
    Acquisition.RECONCILIATION_OF_SOURCES: ProvenanceClass.RECONCILED,
}


class ProvenanceError(RuntimeError):
    """A structural provenance misuse. Fail closed."""


class ProvenanceFromContent(ProvenanceError):
    """Inbound content tried to carry or choose its own `provenance_class` (R-P1). A field describing
    trust that untrusted input can set is worse than no field at all."""


class ProvenanceLaundering(ProvenanceError):
    """A value's provenance was being STRENGTHENED by a mechanical route (R-P2) — a guess acquiring
    the authority of a fact by moving through layers. The most adversarially-tested rule in the system."""


class OwnerAssertedRecompute(ProvenanceError):
    """A machine tried to recompute or overwrite an `OWNER_ASSERTED` value (R-P3, the L-A defect).
    Illegal: it persists nothing and the owner's value is preserved byte-identical."""


def as_class(value: object) -> ProvenanceClass:
    """Coerce a `ProvenanceClass` or one of the six canonical strings to a `ProvenanceClass`, and
    refuse anything else — a seventh class does not exist (AC-2). M5/M6 carry provenance as strings,
    so this is the single coercion point that keeps them speaking the one vocabulary."""
    if isinstance(value, ProvenanceClass):
        return value
    if isinstance(value, str) and value in PROVENANCE_CLASS_VALUES:
        return ProvenanceClass(value)
    raise ProvenanceError(
        f"{value!r} is not one of the six canonical provenance classes "
        f"{sorted(PROVENANCE_CLASS_VALUES)}: there is no seventh (AC-2, C-7)."
    )


# ------------------------------------------------------------------- R-P1: runtime assignment


def assign_at_runtime(acquisition: object) -> ProvenanceClass:
    """R-P1: the provenance class is a function of HOW the value was obtained — nothing else. A model
    cannot pass a class here; it can only be an `Acquisition`, and the runtime supplies that. Accepts
    `object` and validates: this is the boundary where a caller-chosen class string is refused."""
    if not isinstance(acquisition, Acquisition):
        raise ProvenanceError(
            "provenance is assigned from a runtime Acquisition, never from a caller-chosen class "
            "(R-P1). A model or inbound payload cannot reach this function with a class string."
        )
    return _BY_ACQUISITION[acquisition]


def reject_content_supplied_provenance(inbound: object) -> None:
    """R-P1: inbound content may DESCRIBE a value, never DECLARE its provenance. A payload, document
    or event carrying a `provenance_class` (or `provenance`) key is refused — the runtime assigns it."""
    if isinstance(inbound, Mapping):
        for forbidden in ("provenance_class", "provenance"):
            if forbidden in inbound:
                raise ProvenanceFromContent(
                    f"inbound content carried {forbidden!r}={inbound[forbidden]!r}: content is DATA "
                    f"and cannot choose its own provenance (R-P1, M-13). The runtime assigns it from "
                    f"how the value was obtained; a counterparty asserting OWNER_ASSERTED is a fraud "
                    f"signal, never authority (ADR-003)."
                )


# ------------------------------------------------------------------- AC-4 / AC-SAFE-015: gate reads


def may_gate_consequential_action(provenance_class: object) -> bool:
    """AC-4: whether a fact of this class may be READ by a consequential gate. `MODEL_INFERRED` may
    not — under any confidence. Every other class may (subject to the checkpoint's own live
    revalidation and money fence). This mirrors the kernel's `ProvenancedFact.value` rule and is
    asserted consistent with it."""
    return as_class(provenance_class) not in _GATE_FORBIDDEN


def read_for_consequential_gate(provenance_class: object, value: object) -> object:
    """AC-4 / AC-SAFE-015: read a value for a consequential gate, or REFUSE structurally. There is no
    confidence parameter, so no confidence can rescue a guess: a `MODEL_INFERRED` fact raises
    `GateReadOfInferredFact` (the kernel's exception) at any confidence, ever."""
    if not may_gate_consequential_action(provenance_class):
        raise GateReadOfInferredFact(
            f"a {as_class(provenance_class).value} value may not be read by a consequential gate — at "
            f"any confidence. There is no confidence (AC-SAFE-015, ADR-002 sec 2.3)."
        )
    return value


# ------------------------------------------------------------------- R-P2: no provenance laundering


def is_stronger(new: object, old: object) -> bool:
    """True when `new` is MORE trusted than `old` — i.e. reassigning to it would STRENGTHEN provenance."""
    return _TRUST_RANK[as_class(new)] > _TRUST_RANK[as_class(old)]


def carry(source: object) -> ProvenanceClass:
    """A mechanically derived value CARRIES its source's provenance; it never gains trust. This is the
    whole of R-P2 for a derivation: a function that returns a stronger class than its input is the
    laundering defect."""
    return as_class(source)


def derive_through(source: object, path: str) -> ProvenanceClass:
    """R-P2: a value travelling any of the six paths keeps its provenance. A `MODEL_INFERRED` source
    emerges `MODEL_INFERRED` through copy, cache, re-observation, reconciliation, serialization and a
    process boundary alike."""
    if path not in DERIVATION_PATHS:
        raise ProvenanceError(f"unknown derivation path {path!r}; the six are {DERIVATION_PATHS}")
    return carry(source)


# The registered F14 audit/security contract for a refused strengthening (events/registry.md sec F14).
# Its EMISSION half was scoped to P7; the REFUSAL below is the safety, and this is its audit trail.
# A NAME already in the frozen 105-event registry — this mints no new contract.
F14_PROVENANCE_STRENGTHENING = "ProvenanceStrengtheningAttempted"


def provenance_strengthening_event(old: object, new: object) -> dict:
    """The registered F14 `ProvenanceStrengtheningAttempted` record for a refused laundering attempt.
    A dict, not a minted contract — the caller's security-event sink routes it (log + alert)."""
    return {
        "event": F14_PROVENANCE_STRENGTHENING,
        "family": "F14",
        "from_class": as_class(old).value,
        "to_class": as_class(new).value,
    }


def reassign(old: object, new: object, *, authenticated_human_act: bool = False,
             on_strengthening_attempt: "Callable[[dict], None] | None" = None) -> ProvenanceClass:
    """R-P2: return the reassigned provenance class, or REFUSE. Weakening (to an equal or lower-trust
    class) is always allowed. STRENGTHENING is refused as laundering — the ONE exception is a new
    authenticated human act, which creates an `OWNER_ASSERTED` claim (superseding and retaining the
    old). No mechanical route ever strengthens, and no human act produces a machine class.

    When a strengthening is refused, the registered F14 `ProvenanceStrengtheningAttempted` event is
    handed to `on_strengthening_attempt` if one is supplied — the audit trail of the refusal, emitted
    through the caller's security-event sink (this module mints no gate and opens no transport)."""
    old_c, new_c = as_class(old), as_class(new)
    if not is_stronger(new_c, old_c):
        return new_c  # weakening or unchanged — provenance may always be weakened
    if authenticated_human_act and new_c is ProvenanceClass.OWNER_ASSERTED:
        return new_c  # the sole strengthening route: a NEW human assertion
    if on_strengthening_attempt is not None:
        on_strengthening_attempt(provenance_strengthening_event(old_c, new_c))
    raise ProvenanceLaundering(
        f"refusing to strengthen provenance {old_c.value} -> {new_c.value}: the only strengthening "
        f"route is a new authenticated human act creating an OWNER_ASSERTED claim (R-P2). A guess "
        f"never becomes a fact by moving through a layer, at any confidence."
    )


# ------------------------------------------------------------------- R-P3: OWNER_ASSERTED protection


@dataclass(frozen=True)
class ProvenanceRecord:
    """A value and how it came to be believed — the unit R-P3 protects. Frozen: a recompute produces
    a NEW record or fails; it never mutates an existing one in place."""

    value: object
    provenance_class: ProvenanceClass

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance_class", as_class(self.provenance_class))


def machine_recompute(record: ProvenanceRecord, *, new_value: object, new_class: object) -> ProvenanceRecord:
    """R-P3: apply a machine-derived recompute. If the current record is `OWNER_ASSERTED`, this is an
    ILLEGAL transition: it raises, persists nothing, and the owner's value is preserved byte-identical.
    A machine may never overwrite what a human asserted — not on a better model, not on a better
    linker, not on a later cycle. A disagreement is a Conflict, not a silent overwrite."""
    new_c = as_class(new_class)
    if new_c is ProvenanceClass.OWNER_ASSERTED:
        raise OwnerAssertedRecompute(
            "a machine recompute may not assert OWNER_ASSERTED — only an authenticated human act can "
            "(use human_reassert). A machine claiming an owner's authority is the laundering R-P2 forbids."
        )
    if record.provenance_class is ProvenanceClass.OWNER_ASSERTED:
        raise OwnerAssertedRecompute(
            f"machine recompute ({new_c.value}) may NEVER overwrite an OWNER_ASSERTED value (R-P3, the "
            f"L-A defect): the owner's value {record.value!r} is preserved. If the machine disagrees, "
            f"raise a Conflict — Neyma never silently picks a winner."
        )
    return ProvenanceRecord(value=new_value, provenance_class=new_c)


def human_reassert(record: object, *, new_value: object) -> ProvenanceRecord:
    """The ONE legal overwrite of any prior provenance: a new authenticated human act, which creates a
    fresh `OWNER_ASSERTED` record that supersedes the old one. The caller is responsible for retaining
    the superseded record (supersession never deletes)."""
    if not isinstance(record, ProvenanceRecord):
        raise ProvenanceError("human_reassert supersedes an existing ProvenanceRecord")
    return ProvenanceRecord(value=new_value, provenance_class=ProvenanceClass.OWNER_ASSERTED)
