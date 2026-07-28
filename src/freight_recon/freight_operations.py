"""The TYPED FREIGHT OPERATION CONTRACT (P4 adapter containment, EP-1 write-half, R-07 scope).

WHY THIS MODULE EXISTS. EP-1's live write is the Slack-approved carrier-invoice action. The
containment checkpoint's first instinct was to place a generic autonomous-browser factory behind
`effect_boundary`. That is REJECTED here, by construction. `browser_use_write.NativeBrowserUseRunner`
runs an ARBITRARY natural-language task; a caller that can hand it a task decides what happens to the
page. Routing THAT through the boundary contains nothing — it just moves the arbitrary actuation one
import away.

So the first real `AdapterOperation` is a NARROWLY TYPED freight operation. `InvoiceWriteOperation`
carries only the IDENTITY and DATA the authorized action needs. It has:

  * NO field for a natural-language task, a selector, a URL, JavaScript, an adapter method name, a
    caller-chosen operation name, or a browser instruction. There is nowhere to put executable
    behaviour, so a caller cannot supply any.
  * a FIXED `operation_class` drawn from a closed enum (not a free string the caller invents).
  * `approved_fields`: a mapping whose KEYS are an exact allowlist (`APPROVED_FIELD_KEYS`) and whose
    values are the human-approved data — nothing else may travel as an "approved field".

This module is PURE DATA. It imports no adapter and no effect machinery, so it is importable by the
callback layer, the governed-approval layer, the pipeline and the effect boundary alike without
creating any adapter-import edge. The adapter maps this typed operation to a bounded implementation;
this module is the shape of what may be asked, and the shape IS the containment.

DARKNESS. Every operation carries `sandbox`. A real (non-sandbox) target is refused downstream: the
capability ships dark, so no real external write is performed here or in the phase that lands this.
Enabling live supervised writes is P12, not P4.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from .commit_key import LogicalEffect, occurrence_key_for

# The intent/payload-hash version. Bump only if the canonicalisation below changes, so a stored hash
# from an older approval can be told apart from a new one rather than silently compared across shapes.
INTENT_HASH_VERSION = "ih_v1"


class FreightOperationError(ValueError):
    """A typed freight operation could not be constructed or is internally inconsistent. Fail
    closed: a malformed operation authorizes nothing."""


class FreightOperationClass(str, Enum):
    """The closed set of freight operation classes a typed operation may name. This is NOT a
    caller-chosen string: an operation whose class is not one of these cannot be constructed, so a
    caller cannot smuggle an unrecognised or arbitrary action through the typed contract.

    Each maps to the canonical commit-key `action_class` (commit_key.OCCURRENCE_RULES), so the
    Commit Key derivation is the frozen one and never a per-operation reinvention. EP-1 is
    RAISE_INVOICE; RECORD_PAYABLE is carried because the same bounded shape covers the AP mirror,
    but nothing routes it yet.
    """

    RAISE_INVOICE = "raise_invoice"
    RECORD_PAYABLE = "record_payable"

    @property
    def action_class(self) -> str:
        return self.value


#: The EXACT set of keys an `approved_fields` mapping may carry. A key outside this set is refused at
#: construction — "arbitrary fields or values" is precisely what the typed contract must not accept.
#: These are the human-approved data of a carrier-invoice action; none of them is executable.
APPROVED_FIELD_KEYS: frozenset[str] = frozenset(
    {"customer", "carrier", "amount", "load_ref", "invoice_ref"}
)


@dataclass(frozen=True, slots=True)
class InvoiceWriteOperation:
    """One narrowly-typed, bounded freight write operation — the EP-1 carrier-invoice action.

    IT CARRIES IDENTITY AND DATA, NEVER BEHAVIOUR. Every field below is a reference or an approved
    value; there is no field into which a caller could place a task, a selector, a URL, JavaScript,
    an adapter method, or a browser instruction. The adapter that performs it renders the bounded
    implementation itself from these fields.
    """

    # -- WHO / WHERE the accountable work lives (identity references; P6 owns the entities) --------
    tenant: str
    work_item_id: str
    pipeline_instance_id: str

    # -- WHAT external subject is being acted on ---------------------------------------------------
    load_id: str
    invoice_ref: str
    target_integration: str          # the external system holding the truth, e.g. "truckingoffice"
    target_account: str              # the account/workspace within that system

    # -- WHICH operation, and the exact approved data --------------------------------------------
    operation_class: FreightOperationClass
    approved_fields: dict[str, str]  # keys restricted to APPROVED_FIELD_KEYS; values are data

    # -- the bindings a governed approval and the checkpoint revalidate --------------------------
    approval_id: str
    approval_revision: int
    idempotency_key: str
    capability_id: str               # the AdapterOperation op_id the boundary invokes, e.g. "A4.raise_invoice"

    # -- expected external preconditions and verification expectations ---------------------------
    expected_preconditions: tuple[str, ...] = ()   # e.g. ("pod_present", "not_yet_invoiced")
    verification_mode: str = "READBACK_VERIFIABLE"

    # -- DARKNESS: a real (non-sandbox) target is refused downstream ------------------------------
    sandbox: bool = True
    base_url: str = ""               # the mock/sandbox TMS base URL; a real host is refused

    def __post_init__(self) -> None:
        for name in ("tenant", "work_item_id", "pipeline_instance_id", "load_id", "invoice_ref",
                     "target_integration", "target_account", "approval_id", "idempotency_key",
                     "capability_id"):
            if not str(getattr(self, name) or "").strip():
                raise FreightOperationError(
                    f"InvoiceWriteOperation.{name} is required — an operation missing an identity "
                    f"or binding field authorizes nothing (fail closed)")
        if not isinstance(self.operation_class, FreightOperationClass):
            raise FreightOperationError(
                f"operation_class must be a FreightOperationClass, not {self.operation_class!r} — a "
                f"caller may not invent an operation name")
        if not isinstance(self.approved_fields, dict):
            raise FreightOperationError("approved_fields must be a mapping of approved data")
        stray = set(self.approved_fields) - APPROVED_FIELD_KEYS
        if stray:
            raise FreightOperationError(
                f"approved_fields carries key(s) outside the allowlist {sorted(APPROVED_FIELD_KEYS)}: "
                f"{sorted(stray)} — arbitrary fields are not admissible")
        if int(self.approval_revision) < 0:
            raise FreightOperationError("approval_revision must be a non-negative integer")

    # -- derivations --------------------------------------------------------------------------------

    def logical_effect(self) -> LogicalEffect:
        """The canonical `LogicalEffect` for this operation — the identity of the EFFECT, never its
        content. The amount is NOT here (it is an approved field / material fact), exactly as
        commit_key.py requires. `raise_invoice`/`record_payable` are SINGLE-occurrence, so the
        occurrence key is empty; `occurrence_key_for` enforces that rather than this module guessing.
        """
        occurrence = occurrence_key_for(self.operation_class.action_class)
        return LogicalEffect(
            tenant=self.tenant,
            action_class=self.operation_class.action_class,
            target_system=self.target_integration,
            target_resource_id=self.load_id,
            target_operation=self.operation_class.action_class,
            occurrence_key=occurrence,
        )

    def effect_key(self) -> str:
        """The effect's Commit Key. This is NOT a second derivation: it DELEGATES to the canonical
        `LogicalEffect.key()` (commit_key.py), which is the one and only Commit Key algorithm. It is
        deliberately NOT named `commit_key` so the phase-1 canonical-derivation guard stays exact —
        a `*commit_key*` definition outside commit_key.py is presumed a reimplementation, and this
        accessor is not one."""
        return self.logical_effect().key()

    def payload_hash(self) -> str:
        """The INTENT/PAYLOAD HASH the governed approval binds to. A deterministic digest over the
        identity references and the exact approved values. Any change to the invoice, amount, load,
        tenant, target system, operation class or an approved field changes this hash — so a
        previous approval cannot silently authorize a changed effect.

        This is DELIBERATELY independent of the checkpoint's material-facts fingerprint: this hash
        binds what the HUMAN approved (the proposal), and the checkpoint's step-2 fingerprint binds
        what the LIVE external world still says. Two independent drift barriers, not one.
        """
        canonical = {
            "v": INTENT_HASH_VERSION,
            "tenant": _norm(self.tenant),
            "work_item_id": _norm(self.work_item_id),
            "load_id": _norm(self.load_id),
            "invoice_ref": _norm(self.invoice_ref),
            "target_integration": _norm(self.target_integration),
            "target_account": _norm(self.target_account),
            "operation_class": self.operation_class.value,
            "approved_fields": {k: str(self.approved_fields[k]) for k in sorted(self.approved_fields)},
            "revision": int(self.approval_revision),
        }
        blob = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"{INTENT_HASH_VERSION}:" + hashlib.sha256(blob).hexdigest()

    @property
    def approved_amount(self) -> str:
        """The approved money value as a string, or "" if this class carries none. Never a float,
        never stored in memory/logs (commit_key/effect-boundary discipline)."""
        return str(self.approved_fields.get("amount", "") or "")


def _norm(value: object) -> str:
    return str(value or "").strip().lower()
