"""P9 — External Entity Mapping (domain entity #38): one canonical Neyma entity, many outside names.

A Brokerage Load is known to the TMS as `LD-48219`, to the customer as `PO-7731`, to the carrier as
`PRO-99812` and to the paperwork as `BOL-55120`. Each of those is a row here pointing at ONE opaque
Neyma id. None of them IS the identity, and none is trusted outside the brokerage and the outside
system it came from.

### THE LOOKUP IS EXACT OR IT IS NOT AN ANSWER. `resolve` matches the full
`(tenant, external_system, external_id_kind, external_id)` tuple and nothing looser. It returns one of
four statuses and never chooses between candidates:

    EXACT          exactly one ACTIVE mapping                  -> a deterministic bind is possible
    AMBIGUOUS      more than one ACTIVE mapping                -> a human decides; nothing is bound
    RETIRED_ONLY   only SUPERSEDED/CORRECTED mappings          -> a weak candidate, never a bind
    UNMAPPED       nothing                                     -> the reference is unknown HERE

`UNMAPPED` is "this tenant has no such reference". It is never "let me look in another tenant": the
store is bound to one tenant at construction and has no method that takes another.

### MODEL-ASSISTED CORRELATION NEVER REACHES THIS TABLE. When exact resolution finds nothing, intake
may ask a model for CANDIDATE loads (`interpretation.py`). A candidate is never written here — `record`
refuses model provenance — and can never confirm a binding: the linker routes a model inference to
AMBIGUOUS at any stated support, and a human decides.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..event_envelope import format_instant
from ..migrations.phase9_external_entity_mappings import (
    P9XM_ALLOWED_PROVENANCE,
    P9XM_RETIRED_STATES,
)
from ..tenant import require_tenant
from .foundation import stable_id

EXACT = "EXACT"
AMBIGUOUS = "AMBIGUOUS"
RETIRED_ONLY = "RETIRED_ONLY"
UNMAPPED = "UNMAPPED"


class MappingError(RuntimeError):
    """The mapping store will not do what was asked. Fail closed; nothing is persisted."""


@dataclass(frozen=True)
class ExternalReference:
    """An outside name as a record carried it. `system` is None when the record did not say which
    system's numbering it is using — "load 48219" in a text message — and an unqualified reference
    can never resolve exactly, because an id is trusted only within a system."""

    system: str | None
    kind: str
    value: str

    @property
    def qualified(self) -> bool:
        return bool(self.system and str(self.system).strip())

    def label(self) -> str:
        return f"{self.system or '?'}:{self.kind}={self.value}"


@dataclass(frozen=True)
class Mapping:
    tenant: str
    mapping_id: str
    neyma_entity_type: str
    neyma_entity_id: str
    external_system: str
    external_id_kind: str
    external_id: str
    provenance_class: str
    state: str
    source_observation_id: str
    decision_ref: str | None
    decision_human_id: str | None
    replaces_mapping_id: str | None
    retired_reason: str | None
    created_at: str
    retired_at: str | None

    @property
    def entity_ref(self) -> str:
        return f"{self.neyma_entity_type}:{self.neyma_entity_id}"

    @property
    def reference(self) -> ExternalReference:
        return ExternalReference(self.external_system, self.external_id_kind, self.external_id)


@dataclass(frozen=True)
class Resolution:
    reference: ExternalReference
    status: str
    active: tuple[Mapping, ...] = ()
    retired: tuple[Mapping, ...] = ()

    @property
    def entity_refs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(m.entity_ref for m in self.active))


def _row_to_mapping(row: Any) -> Mapping:
    return Mapping(
        tenant=row["tenant"], mapping_id=row["mapping_id"],
        neyma_entity_type=row["neyma_entity_type"], neyma_entity_id=row["neyma_entity_id"],
        external_system=row["external_system"], external_id_kind=row["external_id_kind"],
        external_id=row["external_id"], provenance_class=row["provenance_class"],
        state=row["state"], source_observation_id=row["source_observation_id"],
        decision_ref=row["decision_ref"], decision_human_id=row["decision_human_id"],
        replaces_mapping_id=row["replaces_mapping_id"], retired_reason=row["retired_reason"],
        created_at=row["created_at"], retired_at=row["retired_at"])


class ExternalEntityMappings:
    """The mapping store for ONE tenant. Bound at construction: there is no per-call tenant argument,
    so a cross-tenant lookup cannot be spelled [C-1, CD-19]."""

    def __init__(self, conn: sqlite3.Connection, *, tenant: str,
                 clock: Callable[[], datetime]) -> None:
        self._conn = conn
        self._tenant = require_tenant(tenant, context="ExternalEntityMappings")
        self._clock = clock

    @property
    def tenant(self) -> str:
        return self._tenant

    # ------------------------------------------------------------------ reads

    def resolve(self, reference: ExternalReference, *, entity_type: str | None = None) -> Resolution:
        """The exact, tenant-scoped lookup. An unqualified reference is UNMAPPED by construction: it
        names no system, and an id is trusted only within one."""
        if not reference.qualified:
            return Resolution(reference=reference, status=UNMAPPED)
        sql = ("SELECT * FROM external_entity_mappings WHERE tenant = ? AND external_system = ? "
               "AND external_id_kind = ? AND external_id = ?")
        params: list[Any] = [self._tenant, reference.system, reference.kind, reference.value]
        if entity_type is not None:
            sql += " AND neyma_entity_type = ?"
            params.append(entity_type)
        rows = [_row_to_mapping(r) for r in self._conn.execute(
            sql + " ORDER BY created_at, mapping_id", params).fetchall()]
        active = tuple(m for m in rows if m.state == "ACTIVE")
        retired = tuple(m for m in rows if m.state in P9XM_RETIRED_STATES)
        distinct = tuple(dict.fromkeys(m.entity_ref for m in active))
        if len(distinct) == 1:
            status = EXACT
        elif len(distinct) > 1:
            status = AMBIGUOUS
        elif retired:
            status = RETIRED_ONLY
        else:
            status = UNMAPPED
        return Resolution(reference=reference, status=status, active=active, retired=retired)

    def get(self, mapping_id: str) -> Mapping | None:
        row = self._conn.execute(
            "SELECT * FROM external_entity_mappings WHERE tenant = ? AND mapping_id = ?",
            (self._tenant, mapping_id)).fetchone()
        return _row_to_mapping(row) if row is not None else None

    def for_entity(self, entity_type: str, entity_id: str) -> list[Mapping]:
        """Every outside name one entity carries or ever carried — retired rows included, because the
        history is the point."""
        return [_row_to_mapping(r) for r in self._conn.execute(
            "SELECT * FROM external_entity_mappings WHERE tenant = ? AND neyma_entity_type = ? "
            "AND neyma_entity_id = ? ORDER BY created_at, mapping_id",
            (self._tenant, entity_type, entity_id)).fetchall()]

    def all(self) -> list[Mapping]:
        return [_row_to_mapping(r) for r in self._conn.execute(
            "SELECT * FROM external_entity_mappings WHERE tenant = ? ORDER BY created_at, mapping_id",
            (self._tenant,)).fetchall()]

    def entity_exists(self, entity_type: str, entity_id: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM external_entity_mappings WHERE tenant = ? AND neyma_entity_type = ? "
            "AND neyma_entity_id = ?", (self._tenant, entity_type, entity_id)).fetchone() is not None

    # ------------------------------------------------------------------ writes

    def record(self, *, entity_type: str, entity_id: str, reference: ExternalReference,
               provenance_class: str, source_observation_id: str,
               decision_ref: str | None = None, decision_human_id: str | None = None,
               replaces_mapping_id: str | None = None) -> tuple[Mapping, bool]:
        """Record that `reference` names `(entity_type, entity_id)` in this tenant. Idempotent on an
        identical ACTIVE binding: returns `(mapping, created)`.

        It does NOT refuse a reference that already names a different entity. That is ambiguity, and
        ambiguity is recorded so a later lookup can fail closed on it — refusing the second row would
        silently make the first one the winner."""
        if not reference.qualified:
            raise MappingError(
                f"reference {reference.label()} names no external system: an id is trusted only "
                f"within (tenant, system, kind), so an unqualified reference cannot be a mapping.")
        if provenance_class not in P9XM_ALLOWED_PROVENANCE:
            raise MappingError(
                f"a mapping may not carry provenance {provenance_class!r}: only "
                f"{list(P9XM_ALLOWED_PROVENANCE)} are deterministic or human acts. A model-originated "
                f"correlation is a CANDIDATE, never a row an exact lookup can return.")
        existing = self._conn.execute(
            "SELECT * FROM external_entity_mappings WHERE tenant = ? AND external_system = ? "
            "AND external_id_kind = ? AND external_id = ? AND neyma_entity_type = ? "
            "AND neyma_entity_id = ? AND state = 'ACTIVE'",
            (self._tenant, reference.system, reference.kind, reference.value, entity_type,
             entity_id)).fetchone()
        if existing is not None:
            return _row_to_mapping(existing), False
        generation = self._conn.execute(
            "SELECT COUNT(*) FROM external_entity_mappings WHERE tenant = ? AND external_system = ? "
            "AND external_id_kind = ? AND external_id = ? AND neyma_entity_type = ? "
            "AND neyma_entity_id = ?",
            (self._tenant, reference.system, reference.kind, reference.value, entity_type,
             entity_id)).fetchone()[0]
        mapping_id = stable_id("xmap", self._tenant, reference.system, reference.kind,
                               reference.value, entity_type, entity_id, generation)
        now = format_instant(self._clock())
        try:
            self._conn.execute(
                "INSERT INTO external_entity_mappings (tenant, mapping_id, neyma_entity_type, "
                "neyma_entity_id, external_system, external_id_kind, external_id, provenance_class, "
                "state, source_observation_id, decision_ref, decision_human_id, "
                "replaces_mapping_id, retired_reason, created_at, retired_at) "
                "VALUES (?,?,?,?,?,?,?,?, 'ACTIVE', ?,?,?,?, NULL, ?, NULL)",
                (self._tenant, mapping_id, entity_type, entity_id, reference.system,
                 reference.kind, reference.value, provenance_class, source_observation_id,
                 decision_ref, decision_human_id, replaces_mapping_id, now))
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise MappingError(f"the mapping was refused by the database: {exc}") from exc
        created = self.get(mapping_id)
        assert created is not None
        return created, True

    def _retire(self, mapping_id: str, *, state: str, reason: str) -> Mapping:
        if state not in P9XM_RETIRED_STATES:
            raise MappingError(f"{state!r} is not a retired state {list(P9XM_RETIRED_STATES)}")
        current = self.get(mapping_id)
        if current is None:
            raise MappingError(
                f"no mapping {mapping_id!r} for tenant {self._tenant!r}. This store does not look "
                f"outside its tenant to find out whether it exists elsewhere [C-1].")
        if current.state != "ACTIVE":
            raise MappingError(
                f"mapping {mapping_id!r} is already {current.state}: a retired mapping is history "
                f"and is not retired again.")
        now = format_instant(self._clock())
        cursor = self._conn.execute(
            "UPDATE external_entity_mappings SET state = ?, retired_at = ?, retired_reason = ? "
            "WHERE tenant = ? AND mapping_id = ? AND state = 'ACTIVE'",
            (state, now, reason, self._tenant, mapping_id))
        if cursor.rowcount != 1:
            self._conn.rollback()
            raise MappingError(f"retiring {mapping_id!r} matched {cursor.rowcount} rows")
        self._conn.commit()
        retired = self.get(mapping_id)
        assert retired is not None
        return retired

    def supersede(self, mapping_id: str, *, new_reference: ExternalReference,
                  provenance_class: str, source_observation_id: str, reason: str) -> Mapping:
        """The outside system RENUMBERED: the old name was true when made and no longer is. The old
        row is retained as SUPERSEDED and the new row names it."""
        old = self._retire(mapping_id, state="SUPERSEDED", reason=reason)
        new, _ = self.record(
            entity_type=old.neyma_entity_type, entity_id=old.neyma_entity_id,
            reference=new_reference, provenance_class=provenance_class,
            source_observation_id=source_observation_id, replaces_mapping_id=old.mapping_id)
        return new

    def correct(self, mapping_id: str, *, new_reference: ExternalReference | None,
                new_entity_type: str | None = None, new_entity_id: str | None = None,
                decision_ref: str, decision_human_id: str, source_observation_id: str,
                reason: str) -> Mapping | None:
        """A human declares a mapping WRONG. The wrong row is retained as CORRECTED. The replacement —
        the right reference for the same entity, or the same reference for the right entity — is a
        new OWNER_ASSERTED row naming the one it corrects. With no replacement, the wrong mapping is
        simply withdrawn."""
        if not str(decision_ref or "").strip() or not str(decision_human_id or "").strip():
            raise MappingError(
                "a correction is a human decision: it carries a decision_ref and the human who made "
                "it. A correction nobody can be pointed at is an edit.")
        old = self._retire(mapping_id, state="CORRECTED", reason=reason)
        if new_reference is None and new_entity_id is None:
            return None
        new, _ = self.record(
            entity_type=new_entity_type or old.neyma_entity_type,
            entity_id=new_entity_id or old.neyma_entity_id,
            reference=new_reference or old.reference, provenance_class="OWNER_ASSERTED",
            source_observation_id=source_observation_id, decision_ref=decision_ref,
            decision_human_id=decision_human_id, replaces_mapping_id=old.mapping_id)
        return new
