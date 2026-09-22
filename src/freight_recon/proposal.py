"""U8.6 — `CommandIntent` → Proposal: the canonical INERT structured proposal boundary.

### THE ONE IDEA. Natural-language or channel interpretation (a `CommandIntent`) is an *input DTO*.
It may FEED the construction of a proposal; it may never BE authority. This module is the single
structured boundary a consequential OPERATE request crosses on its way to the canonical pipeline:
free-form interpretation on one side, an inert `ProposedIntent` on the other, and beyond it the ONE
existing M2 entry (`PipelineMachine.propose` / `IntentProposed`) — never a second command object,
never a second reservation, never a second effect identity.

`CommandIntent` itself must never be — and a `ProposedIntent` is never — execution authority,
approval authority, canonical business truth, a gate decision, a Work Item completion, a Checkpoint
Witness, an Effect Grant, or an adapter command. `02-pipeline-instance.machine.md` §40: *"agents
emit inert proposals only."* GR-7 / C-6: a model's one output is an inert `ProposedIntent`, which is
DATA; turning that data into an attempt is a deterministic act the model may not take.

### INERT MEANS INERT (the property the whole module exists to hold).
Constructing, storing, rendering, signing, serializing, deserializing or redelivering a
`ProposedIntent` creates **zero** approval, **zero** witness, **zero** effect grant, **zero** claim
and **zero** external call. Nothing here mints a gate, evaluates a policy, resolves a Conflict,
closes an Exception, satisfies an Expectation, releases a Brake or reinterprets a Rule. Authority is
minted only by the checkpoint kernel, only inside M2's PL-8/PL-9 co-commits, only on a *mature*
proposal that entered `PipelineMachine.propose`. This module imports no kernel entry point, imports
no adapter, and constructs no `GateEntry`/`GateRegistry` (`test_phase0_null_gate.py` asserts by AST
that only `checkpoint.py` mints a gate).

### WHAT A PROPOSAL NAMES, AND WHAT IT REFUSES TO INVENT.
A proposal names or deterministically derives: the registered `action_class`, the target system,
the target resource, the target operation, the accountable Work Item and owner *where required*, the
material proposed facts *with provenance*, and — through `logical_effect()` — the same commit-key
identity the canonical pipeline already uses (ADR-009: the amount is a material fact, NEVER part of
the identity). Unknown or ambiguous material fields stay unknown: a model may not invent a target,
an amount or a counterparty to make a proposal executable, and a proposal that cannot derive a full
`LogicalEffect` FAILS CLOSED at the M2 boundary rather than guessing one.

### ONE COMMIT KEY AUTHORITY, ONE OCCURRENCE AUTHORITY (P1, restored at the CI #52 correction).
This module defines no Commit Key derivation of its own: the key of a proposal's effect is
`proposal.logical_effect().key()`, i.e. the canonical `commit_key.LogicalEffect.key()`. And a proposal
holds NO occurrence discriminator: `logical_effect()` obtains it from `commit_key.occurrence_key_for`
and nowhere else, so no interpretation param, model output, Slack token, wire form or
`material_params` entry can vary it between retries. U8.6 first shipped a free-form
`occurrence_key: str` field here — the exact escape hatch P1 closed, reopened.

### PROVENANCE IS CARRIED, NEVER PROMOTED.
A `MODEL_INFERRED` material fact is carried (so it is auditable and correctable) but is NEVER
readable by consequential gate evaluation and can NEVER be promoted to a gate-readable class by
proposal construction — the rule is the P7 provenance core's, reused, not re-decided here.

### SHIPS DARK where it is consequential.
The construction and serialization surface is used in production (a Slack proposal is a *surface
over* a proposal). The one consequential seam — proposal → M2 — lives in `pipeline_instance.py`
(`open_pipeline_for_proposal`) precisely so this module never imports M2 and M2 keeps its
zero-production-importer dark posture. Nothing in production calls that seam.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# ### PROVENANCE COMES FROM THE KERNEL, NOT THE P7 SURFACE. `provenance.py` is a P7 analysis module
# that SHIPS DARK (no production importer), and this module is production (a Slack proposal is a
# surface over a Proposal). So the provenance authority reused here is the KERNEL's — the same one
# `provenance.py` itself mirrors: `checkpoint.ProvenanceClass` is the one class enum, and
# `checkpoint.GateReadOfInferredFact` is the one gate-read refusal. The single forbidden class below
# mirrors the kernel's `ProvenancedFact.value` rule (AC-SAFE-015), it does not re-decide it.
from .checkpoint import GateReadOfInferredFact, ProvenanceClass
from .commit_key import CanonicalOccurrence, LogicalEffect, UnidentifiableEffect, occurrence_key_for
from .fingerprint import Money, MoneyMustNotFloat
from .product_policy import ACTION_CLASS_POPULATION

if TYPE_CHECKING:  # the interpretation DTO — imported lazily at runtime to keep this module's
    from .slack_delegate import CommandIntent  # import closure free of the Slack/LLM surface.

# AC-SAFE-015 / GR-8: the ONE class a consequential gate may not read — a guess. Mirrors the kernel's
# `ProvenancedFact.value` rule exactly (proven consistent with it by the P8 proposal tests).
_GATE_FORBIDDEN: frozenset[ProvenanceClass] = frozenset({ProvenanceClass.MODEL_INFERRED})

# The shape `commit_key.document_digest` produces: a SHA-256 content digest. A file_document
# occurrence derives from the actual document's digest, so nothing else may pose as one.
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# ### THE WIRE SCHEMA IS CLOSED AND VERSIONED. prop_v1 (never on main) carried a free-form
# `occurrence_key`; a v1 form is refused, not reinterpreted. Every key below maps to a constructor
# field, and there is deliberately no key through which a form could declare its own identity.
_WIRE_VERSION = "prop_v2"
_WIRE_KEYS = frozenset({
    "v", "tenant", "action_class", "target_system", "target_resource_id", "target_operation",
    "document_digest", "target_status", "work_item_id", "accountable_owner", "facts",
    "material_params", "summary", "source",
})


class ProposalError(RuntimeError):
    """A structural misuse of the proposal boundary. Fail closed; never degrade into a guess."""


class UnregisteredActionClass(ProposalError):
    """The proposed `action_class` is not one the repository has registered (ADR-010 / U8.1).

    A proposal may only name an action class in the DISCOVERED population — the same set the
    occurrence rules and the product policy classify. An unregistered class is refused rather than
    invented into existence, so inbound content can never conjure a new kind of effect.
    """


class AmbiguousProposal(ProposalError):
    """A material field the proposal needs to be an authenticated command is unknown or ambiguous.

    Refused, not guessed: UNKNOWN asks for clarification, it does not fabricate a target, an amount
    or a counterparty to make the proposal executable.
    """


class UnauthenticatedProposal(ProposalError):
    """Untrusted or unauthenticated content tried to become an authenticated command by being made
    into a proposal.

    Untrusted email, document or inbound content may be *evidence* or *proposed data*, but it cannot
    become an authenticated human command through proposal construction (ADR-019 §5, the injection
    boundary; ADR-003). Authentication alone still does not create effect authority — it only lets a
    request be *proposed* as a command; the effect still runs through policy, validation, checkpoint,
    brake, grant and claim.
    """


class OwnerlessProposal(ProposalError):
    """A proposal mature enough to become an attempt names no accountable Work Item / owner context.

    Rule 13 / §5: every open operational obligation has one accountable human owner. Raised at the
    canonical M2 boundary, where the owner is resolved from the Work Item.
    """


def _as_provenance(value: object) -> ProvenanceClass:
    """Coerce a `ProvenanceClass` or one of the six canonical strings to a `ProvenanceClass`, and
    refuse anything else — there is no seventh class. A tampered wire form naming a non-canonical
    provenance is refused here."""
    if isinstance(value, ProvenanceClass):
        return value
    try:
        return ProvenanceClass(value)
    except (ValueError, KeyError) as exc:
        raise ProposalError(
            f"{value!r} is not one of the canonical provenance classes {[c.value for c in ProvenanceClass]}"
        ) from exc


# --------------------------------------------------------------------------- a proposed material fact

@dataclass(frozen=True)
class ProposedFact:
    """One material fact PROPOSED for an effect, with the provenance of HOW it was obtained.

    Inert. A fact's value is a canonical string (money is `Money(amount_minor, currency).canonical()`
    — canonical minor units, never a float). A `MODEL_INFERRED` fact is carried but QUARANTINED: it
    is never readable by a consequential gate (`read_for_gate` refuses it structurally, at any
    confidence), which mirrors the kernel's `ProvenancedFact.value` rule exactly.
    """

    field: str
    value: str
    provenance: ProvenanceClass

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", _as_provenance(self.provenance))
        if not str(self.field or "").strip():
            raise ProposalError("a proposed material fact must name a field")
        # Money and every other material value is a canonical string, never a float. This is the
        # same refusal the fingerprint's Money makes, stated at the proposal's own boundary so a
        # float can never enter a proposal even before a Money is constructed.
        if isinstance(self.value, (float, bool)):
            raise MoneyMustNotFloat(
                f"a proposed material fact value must be a canonical string, not {type(self.value).__name__}"
                f" ({self.field!r}={self.value!r}); serialize money as Money(amount_minor, currency).canonical()."
            )
        object.__setattr__(self, "value", str(self.value))

    @property
    def gate_readable(self) -> bool:
        """Whether a consequential gate MAY read this fact. A `MODEL_INFERRED` fact may not."""
        return self.provenance not in _GATE_FORBIDDEN

    def read_for_gate(self) -> str:
        """Read the value for a consequential gate, or REFUSE. `MODEL_INFERRED` raises, at any
        confidence — there is no confidence (AC-SAFE-015). Same refusal as the kernel's
        `ProvenancedFact.value`, raised through the kernel's own exception."""
        if not self.gate_readable:
            raise GateReadOfInferredFact(
                f"a {self.provenance.value} value may not be read by a consequential gate — at any "
                f"confidence. There is no confidence (AC-SAFE-015)."
            )
        return self.value

    def to_wire(self) -> dict:
        return {"field": self.field, "value": self.value, "provenance": self.provenance.value}

    @classmethod
    def from_wire(cls, data: Mapping) -> "ProposedFact":
        return cls(field=str(data["field"]), value=str(data["value"]),
                   provenance=_as_provenance(data["provenance"]))

    @staticmethod
    def money_from_amount(amount: str | int, *, currency: str = "USD") -> Money:
        """Parse a decimal amount STRING (e.g. "2700.00", "2,700.00") or an integer number of minor
        units into a canonical `Money`, REFUSING a float. Money crosses this boundary as an exact
        decimal string or a minor-unit int — never as a binary float (P1 malformed-input), and never
        with sub-cent precision. A model-chosen number is still refused at the gate by provenance;
        this only refuses a *malformed* amount."""
        from decimal import Decimal, InvalidOperation

        if isinstance(amount, bool) or isinstance(amount, float):
            raise MoneyMustNotFloat(
                f"a money amount is an exact decimal string or a minor-unit int, not "
                f"{type(amount).__name__} ({amount!r}); a binary float is refused."
            )
        try:
            minor = Decimal(str(amount).strip().replace(",", "")) * 100
        except InvalidOperation as exc:
            raise MoneyMustNotFloat(f"not a decimal money amount: {amount!r}") from exc
        if minor != minor.to_integral_value():
            raise MoneyMustNotFloat(
                f"{amount!r} has sub-cent precision; a {currency} amount is whole minor units."
            )
        return Money(amount_minor=int(minor), currency=currency)

    @classmethod
    def money(cls, field: str, money: Money, *,
              provenance: ProvenanceClass = ProvenanceClass.MODEL_EXTRACTED) -> "ProposedFact":
        """A money material fact from a canonical `Money` (minor units; floats already refused by
        `Money` construction). The provenance states HOW the amount was obtained; a model READING an
        amount off an artifact is `MODEL_EXTRACTED` — evidence, never a chosen number. It is never
        `MODEL_INFERRED`-promoted: whatever class the caller states is carried, and a `MODEL_INFERRED`
        amount stays unreadable to a gate."""
        if not isinstance(money, Money):
            raise MoneyMustNotFloat(
                "a money material fact requires a canonical Money(amount_minor, currency); "
                "a float or bare string is refused (P1 malformed-input)."
            )
        return cls(field=field, value=money.canonical(), provenance=provenance)


# ------------------------------------------------------------------------------- the inert proposal

@dataclass(frozen=True)
class ProposedIntent:
    """The canonical INERT structured proposal. Data, not authority (see the module docstring).

    The identity fields (`tenant`, `action_class`, `target_system`, `target_resource_id`,
    `target_operation`) are five of the six that make a `LogicalEffect`, and the amount is nowhere
    among them. Any of them may be `""` when it is genuinely unknown: an immature proposal is legal
    data, it simply cannot enter M2 until its identity is complete (`logical_effect()` fails closed).

    ### THE SIXTH — WHICH LEGITIMATE REPETITION — IS DELIBERATELY NOT A FIELD. A proposal cannot carry,
    accept or deserialize an occurrence discriminator. It carries only the typed INPUTS the canonical
    rule reads, and `logical_effect()` hands them to `occurrence_key_for`:
      * SINGLE classes — nothing; the occurrence is "" and a retry is the same effect;
      * `document_digest` — the SHA-256 content digest of the document being filed
        (DERIVED_DOCUMENT_DIGEST); anything that is not a digest is refused;
      * `target_status` — the status the operation sets (DERIVED_TARGET_STATUS), read from the same
        `status_value` the canonical router reads;
      * a resolved `CanonicalOccurrence` passed to `logical_effect()` by a trusted resolver — never
        stored on, serialized with or deserialized into a proposal (CANONICAL_OCCURRENCE_REQUIRED).
        Without one, derivation fails closed exactly as `occurrence_key_for` does.

    `material_params` carries the ORIGINAL (un-normalised) values a surface renders and a legacy
    bridge reconstructs — display data with no authority. `facts` carries the provenance-tagged
    material facts (the money among them). `source` is the provenance of the proposal ITSELF: a
    proposal read off an artifact by a model is `MODEL_EXTRACTED` data, never `OWNER_ASSERTED`.
    """

    tenant: str
    action_class: str
    target_system: str = ""
    target_resource_id: str = ""
    target_operation: str = ""
    document_digest: str | None = None
    target_status: str | None = None
    work_item_id: str | None = None
    accountable_owner: str | None = None
    facts: tuple[ProposedFact, ...] = ()
    material_params: Mapping[str, str] = field(default_factory=dict)
    summary: str = ""
    source: ProvenanceClass = ProvenanceClass.MODEL_EXTRACTED

    def __post_init__(self) -> None:
        # ### THE TENANT IS NEVER INFERRED, AND A DRAFT MAY NOT YET CARRY ONE. A rendering surface
        # (a Slack button) builds a tenant-less draft; the tenant is bound from the authenticated
        # store context when the proposal MATURES into an attempt, never guessed from content
        # (CLAUDE.md §3). A tenant-less proposal is legal data but immature: `logical_effect()`
        # fails closed on the empty tenant, so it can never become an effect without one.
        # ### THE ACTION CLASS IS ALWAYS REGISTERED. A ProposedIntent cannot exist naming an
        # unregistered action class — construction and deserialization alike go through this check,
        # so there is no path (not even a tampered wire form) to a proposal for an effect kind the
        # repository never registered.
        if self.action_class not in ACTION_CLASS_POPULATION:
            raise UnregisteredActionClass(
                f"{self.action_class!r} is not a registered action class "
                f"{sorted(ACTION_CLASS_POPULATION)}. A proposal may not invent a new kind of effect."
            )
        object.__setattr__(self, "source", _as_provenance(self.source))
        object.__setattr__(self, "facts", tuple(self.facts))
        for f in self.facts:
            if not isinstance(f, ProposedFact):
                raise ProposalError("each material fact must be a ProposedFact")
        object.__setattr__(self, "material_params",
                           {str(k): str(v) for k, v in dict(self.material_params or {}).items()})
        digest = str(self.document_digest or "").strip().lower() or None
        if digest is not None and not _SHA256_HEX.fullmatch(digest):
            raise ProposalError(
                f"document_digest {self.document_digest!r} is not a SHA-256 content digest. A "
                f"file_document occurrence derives ONLY from the actual document's digest "
                f"(commit_key.document_digest); a free-form string may not stand in for one."
            )
        object.__setattr__(self, "document_digest", digest)
        object.__setattr__(self, "target_status", str(self.target_status or "").strip() or None)

    @property
    def is_mature(self) -> bool:
        """Can this proposal, ON ITS OWN DATA, derive a full `LogicalEffect` — i.e. is it ready to enter
        M2 as an attempt? Answered by the one derivation, never a parallel field check, so it cannot
        disagree with the seam: a missing target, a file_document with no digest, an update_status with
        no status, and every CANONICAL_OCCURRENCE_REQUIRED class (whose occurrence only a resolver can
        supply) are all immature. No occurrence is invented to make a proposal mature."""
        try:
            self.logical_effect()
        except UnidentifiableEffect:
            return False
        return True

    def logical_effect(self, *, resolved: CanonicalOccurrence | None = None) -> LogicalEffect:
        """The canonical `LogicalEffect`, derived — never supplied and never containing the amount
        (ADR-009, CLAUDE.md rule 8). Its Commit Key is `.key()`, the ONE derivation (commit_key.py);
        this module deliberately has no commit-key function of its own.

        The occurrence is whatever `occurrence_key_for` returns for this action class, from the typed
        inputs this proposal carries. `resolved` is the only way a CANONICAL_OCCURRENCE_REQUIRED class
        gets an occurrence: a `CanonicalOccurrence` from a resolver that proved it, passed in here and
        never stored. A raw string, a dict or a look-alike object is refused — occurrence identity does
        not enter from untyped data.

        Raises `UnidentifiableEffect` when identity cannot be determined — an unknown target, a missing
        digest/status, an unresolved canonical occurrence. That is the fail-closed direction: an
        ambiguous proposal must be clarified, not forced into an identity."""
        if resolved is not None and not isinstance(resolved, CanonicalOccurrence):
            raise ProposalError(
                f"a canonical occurrence must be a resolved CanonicalOccurrence, not "
                f"{type(resolved).__name__}. Occurrence identity never enters from a raw string or an "
                f"untyped object (P1)."
            )
        occurrence = occurrence_key_for(
            self.action_class, resolved=resolved,
            document_digest=self.document_digest, target_status=self.target_status,
        )
        effect = LogicalEffect(
            tenant=self.tenant, action_class=self.action_class, target_system=self.target_system,
            target_resource_id=self.target_resource_id, target_operation=self.target_operation,
            occurrence_key=occurrence,
        )
        effect.key()  # validate eagerly: an empty required field raises UnidentifiableEffect here,
        return effect  # so an immature proposal fails closed AT this seam, not deep inside propose.

    def gate_readable_facts(self) -> tuple[ProposedFact, ...]:
        """The material facts a consequential gate MAY read — `MODEL_INFERRED` excluded. A
        consequential consumer reads these, never the raw fact list, so a guess can never gate."""
        return tuple(f for f in self.facts if f.gate_readable)

    def fact(self, field_name: str) -> ProposedFact | None:
        for f in self.facts:
            if f.field == field_name:
                return f
        return None

    # --- serialization: a round trip preserves DATA + provenance and grants no authority ----------
    # It carries the typed occurrence INPUTS, never an occurrence: identity is re-derived through
    # `occurrence_key_for` on the far side, not read back from the wire.

    def to_wire(self) -> dict:
        return {
            "v": _WIRE_VERSION,
            "tenant": self.tenant,
            "action_class": self.action_class,
            "target_system": self.target_system,
            "target_resource_id": self.target_resource_id,
            "target_operation": self.target_operation,
            "document_digest": self.document_digest,
            "target_status": self.target_status,
            "work_item_id": self.work_item_id,
            "accountable_owner": self.accountable_owner,
            "facts": [f.to_wire() for f in self.facts],
            "material_params": dict(self.material_params),
            "summary": self.summary,
            "source": self.source.value,
        }

    @classmethod
    def from_wire(cls, data: Mapping) -> "ProposedIntent":
        """Reconstruct and RE-VALIDATE. Deserialization is a validating boundary: a wire form naming
        an unregistered action class or a non-canonical provenance is refused, so a redelivered or
        tampered payload cannot smuggle in a proposal the construction path would have refused.
        Signing/serializing/deserializing grants no authority — this only rebuilds the data.

        ### A WIRE FORM MAY NOT DECLARE ITS OWN IDENTITY. The schema is closed: a key construction has
        no field for — an `occurrence_key` (the P1 escape hatch), a `commit_key`, a "resolved"
        occurrence — is refused rather than silently dropped, so a tampered or stale form is detected,
        not half-accepted. A form of any other version is refused too."""
        if not isinstance(data, Mapping):
            raise ProposalError("a proposal wire form is an object")
        unknown = sorted(set(map(str, data)) - _WIRE_KEYS)
        if unknown:
            raise ProposalError(
                f"a proposal wire form carried {unknown}, which no proposal field accepts. A wire form "
                f"may not declare its own identity: the occurrence is derived by "
                f"commit_key.occurrence_key_for, never read from a payload (P1)."
            )
        if data.get("v") != _WIRE_VERSION:
            raise ProposalError(
                f"proposal wire version {data.get('v')!r} is not {_WIRE_VERSION!r}; refusing to "
                f"reinterpret it (prop_v1 carried a free-form occurrence string)."
            )
        return cls(
            tenant=str(data.get("tenant") or ""),
            action_class=str(data.get("action_class") or ""),
            target_system=str(data.get("target_system") or ""),
            target_resource_id=str(data.get("target_resource_id") or ""),
            target_operation=str(data.get("target_operation") or ""),
            document_digest=(str(data["document_digest"]) if data.get("document_digest") else None),
            target_status=(str(data["target_status"]) if data.get("target_status") else None),
            work_item_id=(str(data["work_item_id"]) if data.get("work_item_id") else None),
            accountable_owner=(str(data["accountable_owner"]) if data.get("accountable_owner") else None),
            facts=tuple(ProposedFact.from_wire(f) for f in (data.get("facts") or [])),
            material_params=dict(data.get("material_params") or {}),
            summary=str(data.get("summary") or ""),
            source=_as_provenance(data.get("source") or ProvenanceClass.MODEL_EXTRACTED),
        )

    def to_command_intent(self) -> "CommandIntent":
        """A NON-AUTHORITATIVE `CommandIntent` projection, for rendering and for a legacy bridge
        whose signature predates proposals. The params are the ORIGINAL material values plus the
        registered `action_class`; the effect identity a consequential consumer trusts is
        `logical_effect()`, derived through the canonical authorities — not these free-form params."""
        from .slack_delegate import CommandIntent, CommandKind

        params = dict(self.material_params)
        params["action_class"] = self.action_class
        return CommandIntent(kind=CommandKind.OPERATE, summary=self.summary, params=params)


# ------------------------------------------------------------------------------- construction

def build_proposed_intent(
    *,
    tenant: str,
    action_class: str,
    target_system: str = "",
    target_resource_id: str = "",
    target_operation: str = "",
    document_digest: str | None = None,
    target_status: str | None = None,
    work_item_id: str | None = None,
    accountable_owner: str | None = None,
    facts: tuple[ProposedFact, ...] = (),
    material_params: Mapping[str, str] | None = None,
    summary: str = "",
    source: ProvenanceClass = ProvenanceClass.MODEL_EXTRACTED,
) -> ProposedIntent:
    """Build an inert `ProposedIntent`. The registration, provenance and digest invariants are enforced
    by `ProposedIntent` itself, so there is one place they hold. Grants zero authority. There is no
    occurrence parameter: the occurrence is derived by `logical_effect()`, never supplied."""
    return ProposedIntent(
        tenant=tenant, action_class=action_class, target_system=target_system,
        target_resource_id=target_resource_id, target_operation=target_operation,
        document_digest=document_digest, target_status=target_status, work_item_id=work_item_id,
        accountable_owner=accountable_owner, facts=tuple(facts),
        material_params=dict(material_params or {}), summary=summary, source=source,
    )


# The material-param keys a load reference / counterparty may arrive under — the same set the legacy
# router reads, kept here so the two derive the SAME identity from the SAME request.
_LOAD_REF_KEYS = ("load_ref", "load_id", "pro", "invoice_number")
_PARTY_KEYS = ("customer", "carrier", "party")


def _first(params: Mapping, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if params.get(k):
            return str(params[k])
    return None


def proposed_intent_from_command_intent(
    intent: "CommandIntent",
    *,
    tenant: str,
    authenticated: bool,
    target_system: str = "",
    work_item_id: str | None = None,
    accountable_owner: str | None = None,
    approved_money: Money | None = None,
    amount_provenance: ProvenanceClass = ProvenanceClass.MODEL_EXTRACTED,
    document_digest: str | None = None,
    target_status: str | None = None,
    source: ProvenanceClass = ProvenanceClass.MODEL_EXTRACTED,
) -> ProposedIntent:
    """Turn an AUTHENTICATED owner OPERATE `CommandIntent` (interpretation input) into an inert
    `ProposedIntent`.

    Refuses, in order:
      * an un-authenticated request — untrusted/inbound content may be proposed DATA (build it with
        `build_proposed_intent` and model provenance), but it cannot become an authenticated command
        through this boundary (`UnauthenticatedProposal`);
      * inbound content that tried to DECLARE its own provenance (R-P1: a counterparty asserting
        `OWNER_ASSERTED` is a fraud signal, never authority);
      * a non-OPERATE intent — QUERY/CONTROL/UNKNOWN do not propose effects;
      * a missing / unregistered action class (`UnregisteredActionClass`).

    Derives the target BEST-EFFORT from the request's own values: when a load reference and a
    counterparty are present, `target_resource_id` is derived exactly as the canonical pipeline does;
    when they are not, it stays `""` and the proposal is legal but immature. A model may NOT invent
    it to make the proposal executable.

    No occurrence is derived or accepted here. The proposal carries only the typed inputs the
    canonical rule reads — `document_digest` from the trusted caller (never from `params`) and the
    status the operation sets — and `logical_effect()` turns them into the occurrence through
    `occurrence_key_for`. A `params["occurrence_key"]` is display data that reaches no identity.
    """
    from .slack_delegate import CommandKind

    if not authenticated:
        raise UnauthenticatedProposal(
            "refusing to construct an authenticated command from unauthenticated content. Untrusted "
            "email/document/inbound content may be proposed data or evidence — never a command "
            "(ADR-019 §5). Only an authenticated owner request crosses this boundary."
        )
    params = dict(intent.params or {})
    # R-P1: inbound content may DESCRIBE a value, never DECLARE its provenance. The runtime assigns
    # provenance from HOW a value was obtained; a payload carrying `provenance_class`/`provenance` is
    # a counterparty trying to grant itself authority, and is refused.
    for forbidden in ("provenance_class", "provenance"):
        if forbidden in params:
            raise ProposalError(
                f"inbound content carried {forbidden!r}={params[forbidden]!r}: content is DATA and "
                f"cannot choose its own provenance (R-P1). A counterparty asserting OWNER_ASSERTED is "
                f"a fraud signal, never authority (ADR-003)."
            )
    if intent.kind != CommandKind.OPERATE:
        raise ProposalError(
            f"a proposal is constructed only from an OPERATE intent; got {intent.kind.value}. "
            f"QUERY answers, CONTROL is governed by its own authority, UNKNOWN asks for clarification."
        )
    action_class = params.get("action_class")
    if not action_class:
        raise AmbiguousProposal(
            "the request names no action class, so what kind of effect it proposes is unknown. "
            "Refusing rather than guessing."
        )
    action_class = str(action_class)
    if action_class not in ACTION_CLASS_POPULATION:
        raise UnregisteredActionClass(
            f"{action_class!r} is not a registered action class {sorted(ACTION_CLASS_POPULATION)}."
        )

    load_ref = _first(params, _LOAD_REF_KEYS)
    party = _first(params, _PARTY_KEYS)
    target_resource_id = ""
    if load_ref and party:
        # Normalise each component BEFORE joining, exactly as the canonical pipeline does, so two
        # readings of one effect converge no matter how the parser spaced or cased them.
        target_resource_id = f"{str(load_ref).strip().lower()}|{str(party).strip().lower()}"

    facts: list[ProposedFact] = []
    if approved_money is not None:
        facts.append(ProposedFact.money("approved_amount", approved_money, provenance=amount_provenance))

    return build_proposed_intent(
        tenant=tenant, action_class=action_class, target_system=target_system,
        target_resource_id=target_resource_id,
        target_operation=action_class if target_resource_id else "",
        document_digest=document_digest,
        # The status an update_status SETS — the same `status_value` the canonical router reads, so
        # the two derive one identity from one request. Only DERIVED_TARGET_STATUS reads it.
        target_status=target_status or params.get("status_value"),
        work_item_id=work_item_id,
        accountable_owner=accountable_owner, facts=tuple(facts),
        material_params=params, summary=str(intent.summary or ""), source=source,
    )
