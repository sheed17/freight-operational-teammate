"""The human brake — admission control (ADR-011, machine M13). The ONE brake authority.

THE RULE: the brake is ADMISSION CONTROL, not process termination. It is enforced by refusing to
mint (checkpoint step 7) and refusing to claim (the CAS re-derives the version token) — never by
killing a worker, because a killed worker manufactures the exact thing the architecture fears
most: an UNKNOWN_OUTCOME.

THE RATCHET (the one sentence that governs both this module and autonomy): automation may only
ever move authority in the SAFE direction. Automation may ENGAGE and WIDEN a brake. Automation
may NEVER RELEASE or NARROW one. A detector may never clear its own alarm. A timer may never
release anything — there is no TTL column, so no code path can expire a brake.

TWO STATES — ACTIVE, RELEASED — and no more. "Engaged by human vs automation" is the `actor_kind`
FIELD; "partially released" is a scope change; "pending release" would require a release-approval
workflow, which is forbidden (requiring ceremony to become SAFER is a design error).

VERSIONS. `brake_version` is monotonic per owner: the platform's version lives on the single
`platform_brake` row (SD-12), the tenant's version is MAX over the tenant's brake rows. Every
engage / widen / narrow / release bumps the owner's version, and witnesses/grants bind the
COMPOSITE token of both (M13 §17) — so any brake event between mint and claim changes the token
and the claim CAS matches zero rows. Never both, never neither.

FAIL-CLOSED READ. "Cannot read the brake" NEVER means "off": the reader raises
`BrakeStoreUnreachable`, and both checkpoint step 7 and the claim CAS treat that as a refusal.

EVENTS (M13). Every tenant brake transition co-commits its F13 event into the transactional outbox
(GR-2, C-2): `BrakeEngaged` (BR-1), `BrakeWidened` (BR-2), `BrakeNarrowed` (BR-3), `BrakeReleased`
(BR-4). A non-human release ATTEMPT co-commits the already-registered F14
`UnauthorizedBrakeReleaseAttempted` and refuses. There is no fifth F13 contract and no M13-local
synonym for the F14 one. BR-5 (`TimerFired`) is illegal and produces nothing — there is no method
for it, so no door exists for a scheduler to find.

  ### THE PLATFORM (GLOBAL) BRAKE EMITS NO F13 EVENT — a recorded gap, `M13-AQ-5`. The per-tenant
  event transport (`event_outbox`, `EventEnvelope`, `TransactionalOutbox`) all `require_tenant(...)`,
  which refuses `None` and every sentinel (including "global"). The platform row belongs to no
  tenant (amendment A1), so a platform brake event has no honest tenant partition, and inventing a
  sentinel tenant is exactly the defect A1 forbids. The platform brake's SAFETY mechanism —
  admission denial via the row read in checkpoint step 7 and the claim CAS — is fully intact; its
  incident record is the retained `platform_brake` row and its columns. Emitting a tenantless F13
  event on a per-tenant transport is deferred to whoever resolves M13-AQ-5, not guessed here.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .tenant import require_tenant

# Scope grammar: the whole tenant, one integration (target_system) within it, or one action class
# within it. INTEGRATION lands at P8/U8.3 because `target_system` is a DETERMINISTIC field of the
# canonical LogicalEffect (part of the commit key, revalidated by the claim CAS), so an integration
# brake matches an effect with no guessing. COUNTERPARTY stays unspellable — the effect carries no
# deterministic counterparty identity (that vocabulary arrives at P9) — so the grammar remains
# closed and an unparseable scope can never silently scope to nothing (fail-safe to a wider brake).
# The landed grammar is single-dimension: a brake row names ONE of tenant / integration / action
# class, never a composite, because a composite scope string the closed grammar cannot spell is the
# exact drift the closed grammar exists to prevent.
TENANT_WIDE = "tenant"
INTEGRATION_PREFIX = "integration:"
ACTION_PREFIX = "action:"

HUMAN = "HUMAN"
DETECTOR = "DETECTOR"

_TOKEN_PREFIX = "bv1"

AGGREGATE_TYPE = "brake"
PRODUCER_COMPONENT = "brake"
# The idempotency-identity prefix for the F14 unauthorized-release attempt. A refused release
# advances no brake version, so a retry storm re-derives the same identity and the outbox dedups it.
_F14_IDENTITY_PREFIX = "ubra_v1"


class BrakeError(RuntimeError):
    """An illegal brake operation. The state did not change."""


class BrakeStoreUnreachable(RuntimeError):
    """The brake state could not be read. The caller MUST refuse the effect — this exception is
    the mechanism of 'cannot read the brake never means off'."""


@dataclass(frozen=True)
class BrakeStatus:
    """The operator-visible report of one brake (R17: a hidden brake is a silent degradation)."""

    brake_id: str
    tenant: str | None          # None => the platform brake
    scope: str
    state: str
    actor: str
    actor_kind: str
    engaged_reason: str
    engaged_at: str
    brake_version: int
    signal_count: int = 1


def _scope_for(action_class: str | None = None, *, target_system: str | None = None) -> str:
    """The single-dimension scope string for one brake, at the landed grammar.

    EITHER an integration (target_system) OR an action class OR neither (tenant-wide). The landed
    grammar has no composite scope string, so naming both at once is REFUSED rather than silently
    collapsed to one — an ambiguous scope is precisely the drift the closed grammar prevents. Both
    dimension values are normalised (strip + lower) exactly as the action class already was, so the
    engage side and the admission side derive the same string for the same effect.
    """
    if target_system is not None and action_class is not None:
        raise BrakeError(
            "the landed brake grammar has no composite scope: name an integration OR an action "
            "class, not both (a tenant + action-class + counterparty composite needs the "
            "counterparty vocabulary that has not landed)"
        )
    if target_system is not None:
        text = str(target_system).strip().lower()
        if not text:
            raise BrakeError("an integration brake scope needs a non-empty target_system")
        return f"{INTEGRATION_PREFIX}{text}"
    if action_class is not None:
        text = str(action_class).strip().lower()
        if not text:
            raise BrakeError("an action-class brake scope needs a non-empty action class")
        return f"{ACTION_PREFIX}{text}"
    return TENANT_WIDE


def _scope_breadth_rank(scope: str) -> int:
    """How wide a scope is, for reporting the WIDEST applicable brake first. Tenant-wide (0) is
    broadest; an integration brake (1) stops one system across every action class; an action-class
    brake (2) stops one action class. Any match denies admission regardless of rank — the rank only
    decides which brake the operator report leads with."""
    if scope == TENANT_WIDE:
        return 0
    if scope.startswith(INTEGRATION_PREFIX):
        return 1
    return 2


class BrakeStore:
    """Brake reads and writes over one canonical database connection.

    Deliberately NOT bound to a tenant the way WorkflowStore is: the platform brake belongs to no
    tenant, and a Sev-0 tenant-isolation signal must be able to engage GLOBALLY. Tenant-scoped
    operations validate their tenant argument at the boundary exactly as the store does.
    """

    def __init__(self, conn: sqlite3.Connection,
                 clock: Callable[[], datetime] | None = None) -> None:
        self._conn = conn
        # A datetime clock (for the F13/F14 envelope timestamps, which need the `…Z` instant shape
        # `format_instant` produces). Defaults to real UTC; tests inject a fixed one for determinism.
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------ writes (the ratchet)

    def engage(
        self,
        *,
        tenant: str | None,
        action_class: str | None = None,
        target_system: str | None = None,
        actor: str,
        actor_kind: str,
        reason: str,
    ) -> BrakeStatus:
        """BR-1: any authenticated human INSTANTLY, or an automated Sev-0 detector. One row write.

        Scopes to the whole tenant (neither argument), one integration (`target_system`), or one
        action class — never a composite (`_scope_for` refuses both). NEVER requires the system to
        be healthy. Idempotent on scope: engaging an already-braked scope records nothing new, bumps
        no version, emits no event, and only raises the row's `signal_count` — a flapping detector
        is one ACTIVE brake, not a pile, and it cannot self-release, so flapping opens no window. The
        first engagement co-commits `BrakeEngaged`.
        """
        kind = self._require_actor(actor, actor_kind)
        if not str(reason or "").strip():
            raise BrakeError("a brake engagement records WHY; an empty reason is not a reason")
        if tenant is None:
            if action_class is not None or target_system is not None:
                raise BrakeError(
                    "the platform (GLOBAL) brake stops everything, everywhere; it carries no "
                    "integration or action-class scope. Engage a tenant brake for a narrower scope."
                )
            return self._engage_platform(actor=actor, actor_kind=kind, reason=reason)
        bound = require_tenant(tenant, context="BrakeStore.engage")
        scope = _scope_for(action_class, target_system=target_system)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self._conn.execute(
                "SELECT * FROM brakes WHERE tenant = ? AND scope = ? AND state = 'ACTIVE'",
                (bound, scope),
            ).fetchone()
            if existing is not None:
                # Idempotent re-engagement: raise the signal count, bump NO version, emit NO event.
                self._conn.execute(
                    "UPDATE brakes SET signal_count = signal_count + 1 "
                    "WHERE tenant = ? AND brake_id = ? AND state = 'ACTIVE'",
                    (bound, existing["brake_id"]),
                )
                self._conn.commit()
                return self.status(tenant=bound, brake_id=existing["brake_id"])
            version = self._next_tenant_version_locked(bound)
            brake_id = str(uuid.uuid4())
            now = self._ts()
            self._conn.execute(
                """
                INSERT INTO brakes (
                    tenant, brake_id, scope, state, actor, actor_kind, engaged_reason,
                    engaged_at, brake_version, signal_count
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, 1)
                """,
                (bound, brake_id, scope, actor, kind, reason, now, version),
            )
            self._emit_f13(
                tenant=bound, event_name="BrakeEngaged", transition_id="BR-1",
                aggregate_id=brake_id, aggregate_version=version, actor=actor, actor_kind=kind,
                payload={"scope": scope, "actor": actor, "reason": reason,
                         "brake_version": int(version)},
                consequential=True,
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return BrakeStatus(
            brake_id=brake_id, tenant=bound, scope=scope, state="ACTIVE", actor=actor,
            actor_kind=kind, engaged_reason=reason, engaged_at=now, brake_version=version,
            signal_count=1,
        )

    def widen(self, *, tenant: str, brake_id: str, actor: str, actor_kind: str) -> BrakeStatus:
        """BR-2: widening a brake NARROWS AUTHORITY, so human OR automation may do it.

        "Narrow"/"broaden" refer to AUTHORITY throughout (ADR-011 §5.1): widening the brake's SCOPE
        narrows what Neyma may do, which is the safe direction. At P3's closed scope grammar,
        widening means action-class -> tenant-wide. Co-commits `BrakeWidened`.
        """
        self._require_actor(actor, actor_kind)  # widening narrows authority: both kinds may
        bound = require_tenant(tenant, context="BrakeStore.widen")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._require_active_locked(bound, brake_id)
            if row["scope"] == TENANT_WIDE:
                self._conn.rollback()
                return self._row_status(row)
            version = self._next_tenant_version_locked(bound)
            self._conn.execute(
                "UPDATE brakes SET scope = ?, brake_version = ? "
                "WHERE tenant = ? AND brake_id = ? AND state = 'ACTIVE'",
                (TENANT_WIDE, version, bound, brake_id),
            )
            self._emit_f13(
                tenant=bound, event_name="BrakeWidened", transition_id="BR-2",
                aggregate_id=brake_id, aggregate_version=version, actor=actor, actor_kind=actor_kind,
                payload={"scope": TENANT_WIDE, "brake_version": int(version)},
                consequential=False,
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return self.status(tenant=bound, brake_id=brake_id)

    def narrow(
        self, *, tenant: str, brake_id: str, actor: str, actor_kind: str, to_action_class: str,
        decision_ref: str,
    ) -> BrakeStatus:
        """BR-3: narrowing a brake BROADENS AUTHORITY => an authenticated human ONLY.

        Narrowing the brake's SCOPE broadens what Neyma may do — the unsafe direction — so a
        detector, a model, automation and a timer are each refused. Co-commits `BrakeNarrowed`.
        """
        kind = self._require_actor(actor, actor_kind)
        if kind != HUMAN:
            raise BrakeError(
                "automation may never narrow a brake: narrowing broadens authority, and "
                "automation may only ever move authority in the safe direction (ADR-011 §5.1)"
            )
        if not str(decision_ref or "").strip():
            raise BrakeError("narrowing a brake requires a decision_ref")
        bound = require_tenant(tenant, context="BrakeStore.narrow")
        scope = _scope_for(to_action_class)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._require_active_locked(bound, brake_id)
            version = self._next_tenant_version_locked(bound)
            self._conn.execute(
                "UPDATE brakes SET scope = ?, brake_version = ? "
                "WHERE tenant = ? AND brake_id = ? AND state = 'ACTIVE'",
                (scope, version, bound, brake_id),
            )
            self._emit_f13(
                tenant=bound, event_name="BrakeNarrowed", transition_id="BR-3",
                aggregate_id=brake_id, aggregate_version=version, actor=actor, actor_kind=kind,
                payload={"scope": scope, "brake_version": int(version)},
                consequential=False,
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return self.status(tenant=bound, brake_id=brake_id)

    def release(
        self, *, tenant: str | None, brake_id: str | None = None, actor: str, actor_kind: str,
        decision_ref: str,
    ) -> BrakeStatus:
        """BR-4: an authenticated human ONLY, with a decision_ref. A detector that engaged a brake
        may never release it — nor may any other automation.

        This method enforces the STRUCTURAL release contract the database can state: the actor is a
        human, a `decision_ref` is present, and (for a tenant brake) `released_by` is a recorded
        human of the tenant, enforced by the foreign key into `tenant_humans`. The RICHER release
        evidence of ADR-011 §6 — every in-flight effect accounted for, no unresolved Sev-0, and
        integration health POSITIVELY demonstrated — is read against the ledger by the caller
        (`brake_lifecycle.release_evidence_satisfied`) at P3-proportionate depth BEFORE this is
        called. (This replaces the earlier docstring's reference to a `release_blockers` seam that
        was never built — `M13-AQ-9`; the seam is `brake_lifecycle`, and the structural half is here.)

        A non-human release ATTEMPT co-commits the F14 `UnauthorizedBrakeReleaseAttempted` and
        refuses. Co-commits `BrakeReleased` on success.
        """
        kind = self._require_actor(actor, actor_kind)
        if kind != HUMAN:
            # A detector cannot clear its own alarm. Record the attempt (F14) in its OWN transaction
            # so the security record survives, then refuse. (A platform-brake attempt has no tenant
            # partition for the event — see the module docstring — so it is refused without F14.)
            if tenant is not None and brake_id:
                self.record_unauthorized_release_attempt(
                    tenant=tenant, brake_id=brake_id, actor=actor, attempted_kind=kind)
            raise BrakeError(
                "automation may never release a brake — a detector cannot clear its own alarm "
                "(ADR-011 §6). Release is a human act with a decision_ref."
            )
        if not str(decision_ref or "").strip():
            raise BrakeError("release requires a decision_ref: an unexplained release is not a decision")
        now = self._ts()
        if tenant is None:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._platform_row_locked()
                if row["state"] != "ACTIVE":
                    self._conn.rollback()
                    raise BrakeError("the platform brake is not ACTIVE; nothing to release")
                self._conn.execute(
                    "UPDATE platform_brake SET state = 'RELEASED', brake_version = brake_version + 1, "
                    "released_by = ?, released_by_kind = 'HUMAN', release_decision_ref = ?, "
                    "released_at = ? WHERE id = 1",
                    (actor, decision_ref, now),
                )
                # No F13 emit for the platform brake — tenantless transport, M13-AQ-5 (module doc).
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
            return self.platform_status()
        bound = require_tenant(tenant, context="BrakeStore.release")
        if not brake_id:
            raise BrakeError("releasing a tenant brake names the brake_id being released")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._require_active_locked(bound, brake_id)
            version = self._next_tenant_version_locked(bound)
            self._conn.execute(
                "UPDATE brakes SET state = 'RELEASED', brake_version = ?, released_by = ?, "
                "released_by_kind = 'HUMAN', release_decision_ref = ?, released_at = ? "
                "WHERE tenant = ? AND brake_id = ? AND state = 'ACTIVE'",
                (version, actor, decision_ref, now, bound, brake_id),
            )
            self._emit_f13(
                tenant=bound, event_name="BrakeReleased", transition_id="BR-4",
                aggregate_id=brake_id, aggregate_version=version, actor=actor, actor_kind=kind,
                payload={"released_by": actor, "release_decision_ref": decision_ref,
                         "brake_version": int(version)},
                consequential=True,
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return self.status(tenant=bound, brake_id=brake_id)

    def engage_platform(self, *, actor: str, actor_kind: str, reason: str) -> BrakeStatus:
        """The GLOBAL brake (SD-12): one row, engaged by a human or a Sev-0 detector."""
        kind = self._require_actor(actor, actor_kind)
        if not str(reason or "").strip():
            raise BrakeError("a brake engagement records WHY; an empty reason is not a reason")
        return self._engage_platform(actor=actor, actor_kind=kind, reason=reason)

    def record_unauthorized_release_attempt(
        self, *, tenant: str, brake_id: str, actor: str, attempted_kind: str,
    ) -> None:
        """Co-commit the already-registered F14 `UnauthorizedBrakeReleaseAttempted` for a non-human
        release attempt, in its OWN transaction (so the security record survives the refusal), plus
        a Sev-0 `security_events` row. Idempotent: a refused release advances no version, so a retry
        re-derives the same idempotency identity and the outbox dedups it. There is NO M13-local
        synonym for this contract — it is F14, shared with M11/M12.
        """
        bound = require_tenant(tenant, context="BrakeStore.record_unauthorized_release_attempt")
        conn = self._conn
        own = not conn.in_transaction
        if own:
            conn.execute("BEGIN IMMEDIATE")
        try:
            ob = self._outbox(bound)
            version = max(1, ob.last_emitted_version(AGGREGATE_TYPE, brake_id))
            identity = (f"{_F14_IDENTITY_PREFIX}|{bound}|{AGGREGATE_TYPE}|{brake_id}|{version}"
                        f"|UnauthorizedBrakeReleaseAttempted|{attempted_kind}")
            existing = conn.execute(
                "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
                (bound, identity),
            ).fetchone()
            if existing is None:
                now = self._ts()
                envelope = EventEnvelope(
                    event_id=str(uuid.uuid4()),
                    event_name="UnauthorizedBrakeReleaseAttempted",
                    event_version=CONTRACTS["UnauthorizedBrakeReleaseAttempted"].current_version,
                    occurred_at=now, recorded_at=now, tenant_id=bound,
                    aggregate_type=AGGREGATE_TYPE, aggregate_id=brake_id, aggregate_version=version,
                    previous_aggregate_version=None, causation_id=None, correlation_id=brake_id,
                    producer_component=PRODUCER_COMPONENT, producer_transition_id="BR-4",
                    actor_type=self._f14_actor_type(attempted_kind), actor_id=actor,
                    trace_id=f"trace-{brake_id}",
                    payload={"brake_id": brake_id, "actor_type": attempted_kind},
                    idempotency_identity=identity,
                )
                ob.emit(envelope)
                self._store_security_event(bound, envelope, actor)
            if own:
                conn.commit()
        except BaseException:
            if own and conn.in_transaction:
                conn.rollback()
            raise

    # ------------------------------------------------------------------ reads (fail closed)

    def admission_denied(
        self, *, tenant: str, action_class: str, target_system: str | None = None,
    ) -> BrakeStatus | None:
        """The checkpoint step-7 / claim-CAS read: the ACTIVE brake covering this effect, if any.

        Consults every landed scope that could cover the effect: the platform (GLOBAL) brake, this
        tenant's tenant-wide brake, this tenant's integration (`target_system`) brake, and this
        tenant's action-class brake. The WIDEST match is the one reported (tenant-wide > integration
        > action class) so the operator sees the broadest reason a mint is refused. `target_system`
        is optional so a legacy caller that names only the action class matches only tenant/action
        scopes; the checkpoint passes `effect.target_system`, so an integration brake actually
        denies the matching effect. Any read failure raises BrakeStoreUnreachable: the caller
        refuses — 'cannot read the brake' NEVER means 'off'.
        """
        bound = require_tenant(tenant, context="BrakeStore.admission_denied")
        action_scope = _scope_for(action_class)
        scopes = [TENANT_WIDE, action_scope]
        if target_system is not None:
            scopes.append(_scope_for(target_system=target_system))
        try:
            platform = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
            if platform is None:
                raise BrakeStoreUnreachable(
                    "the platform brake row is absent; refusing — an unreadable brake is not a "
                    "released brake"
                )
            if platform["state"] == "ACTIVE":
                return self._platform_status_row(platform)
            placeholders = ",".join("?" for _ in scopes)
            rows = self._conn.execute(
                f"SELECT * FROM brakes WHERE tenant = ? AND state = 'ACTIVE' "
                f"AND scope IN ({placeholders})",
                (bound, *scopes),
            ).fetchall()
        except sqlite3.Error as exc:
            raise BrakeStoreUnreachable(f"brake state could not be read: {exc}") from exc
        if not rows:
            return None
        return self._row_status(min(rows, key=lambda r: _scope_breadth_rank(r["scope"])))

    def version_token(self, *, tenant: str) -> str:
        """The composite brake-version token bound into witnesses and grants (M13 §17).

        Deterministic serialization of BOTH monotonic versions. Any brake event on either owner
        changes the token, which is exactly what makes the claim CAS refuse after one.
        """
        bound = require_tenant(tenant, context="BrakeStore.version_token")
        try:
            return self._version_token_locked(bound)
        except sqlite3.Error as exc:
            raise BrakeStoreUnreachable(f"brake versions could not be read: {exc}") from exc

    def status(self, *, tenant: str, brake_id: str) -> BrakeStatus:
        bound = require_tenant(tenant, context="BrakeStore.status")
        row = self._conn.execute(
            "SELECT * FROM brakes WHERE tenant = ? AND brake_id = ?", (bound, brake_id)
        ).fetchone()
        if row is None:
            raise BrakeError(f"no brake {brake_id!r} in tenant {bound!r}")
        return self._row_status(row)

    def platform_status(self) -> BrakeStatus:
        # Fail closed like admission_denied and version_token: an unreadable store (the table gone,
        # or any sqlite error) is the canonical BrakeStoreUnreachable, never a raw error the caller
        # might mistake for a readable brake. "Cannot read the brake" NEVER means "off" — and the
        # operator report is a read path too (entity point 36).
        try:
            row = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
        except sqlite3.Error as exc:
            raise BrakeStoreUnreachable(f"the platform brake could not be read: {exc}") from exc
        if row is None:
            raise BrakeStoreUnreachable("the platform brake row is absent")
        return self._platform_status_row(row)

    def active_report(self, *, tenant: str) -> list[BrakeStatus]:
        """Every ACTIVE brake affecting this tenant, platform first (R17: reported unprompted).

        Fail-closed: any read failure raises BrakeStoreUnreachable so the R17 report path cannot
        read an unreadable store as 'no brake'."""
        bound = require_tenant(tenant, context="BrakeStore.active_report")
        out: list[BrakeStatus] = []
        try:
            platform = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
            rows = self._conn.execute(
                "SELECT * FROM brakes WHERE tenant = ? AND state = 'ACTIVE' ORDER BY engaged_at",
                (bound,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise BrakeStoreUnreachable(f"the active-brake report could not be read: {exc}") from exc
        if platform is not None and platform["state"] == "ACTIVE":
            out.append(self._platform_status_row(platform))
        out.extend(self._row_status(r) for r in rows)
        return out

    # ------------------------------------------------------------------ internals

    def _engage_platform(self, *, actor: str, actor_kind: str, reason: str) -> BrakeStatus:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._platform_row_locked()
            if row["state"] == "ACTIVE":
                # Idempotent re-engagement of the GLOBAL brake: raise the signal count, bump no
                # version, emit nothing.
                self._conn.execute(
                    "UPDATE platform_brake SET signal_count = signal_count + 1 WHERE id = 1")
                self._conn.commit()
                return self.platform_status()
            self._conn.execute(
                "UPDATE platform_brake SET state = 'ACTIVE', brake_version = brake_version + 1, "
                "signal_count = 1, actor = ?, actor_kind = ?, engaged_reason = ?, engaged_at = ?, "
                "released_by = NULL, released_by_kind = NULL, release_decision_ref = NULL, "
                "released_at = NULL WHERE id = 1",
                (actor, actor_kind, reason, self._ts()),
            )
            # No F13 emit for the platform brake — tenantless transport, M13-AQ-5 (module docstring).
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return self.platform_status()

    def _platform_row_locked(self) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
        if row is None:
            raise BrakeStoreUnreachable("the platform brake row is absent")
        return row

    def _require_active_locked(self, tenant: str, brake_id: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM brakes WHERE tenant = ? AND brake_id = ?", (tenant, brake_id)
        ).fetchone()
        if row is None:
            raise BrakeError(f"no brake {brake_id!r} in tenant {tenant!r}")
        if row["state"] != "ACTIVE":
            raise BrakeError(f"brake {brake_id!r} is {row['state']}; only ACTIVE brakes transition")
        return row

    def _next_tenant_version_locked(self, tenant: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(brake_version), 0) + 1 AS v FROM brakes WHERE tenant = ?",
            (tenant,),
        ).fetchone()
        return int(row["v"])

    def _version_token_locked(self, tenant: str) -> str:
        platform = self._conn.execute(
            "SELECT brake_version FROM platform_brake WHERE id = 1").fetchone()
        if platform is None:
            raise BrakeStoreUnreachable(
                "the platform brake row is absent; a version token cannot be derived"
            )
        tenant_version = self._conn.execute(
            "SELECT COALESCE(MAX(brake_version), 0) AS v FROM brakes WHERE tenant = ?",
            (tenant,),
        ).fetchone()["v"]
        return f"{_TOKEN_PREFIX}|global:{int(platform['brake_version'])}|tenant:{int(tenant_version)}"

    def _current_policy_version(self, tenant: str) -> str:
        """The tenant's current ACTIVE policy version, as an audit pin for a consequential brake
        event (§5/ER-13: reproduce the regime in force). A pure local read of the policies row —
        NOT a call to the policy evaluation runtime — so it is available with the policy engine and
        the TMS down. Defaults to "0" (no active policy in force), which is honest and non-blank."""
        try:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(policy_version), 0) AS v FROM policies "
                "WHERE tenant = ? AND state = 'ACTIVE'",
                (tenant,),
            ).fetchone()
            return str(int(row["v"])) if row is not None else "0"
        except sqlite3.Error:
            return "0"

    def _outbox(self, tenant: str):
        from .event_outbox import TransactionalOutbox

        return TransactionalOutbox(self._conn, tenant=tenant, clock=self._clock)

    def _emit_f13(
        self, *, tenant: str, event_name: str, transition_id: str, aggregate_id: str,
        aggregate_version: int, actor: str, actor_kind: str, payload: dict[str, Any],
        consequential: bool,
    ) -> None:
        """Co-commit one F13 event inside the caller's OPEN transaction (GR-2). Strict per-aggregate
        on `brake_version`, so `previous_aggregate_version` links to this aggregate's prior event
        (0 for the first). Consequential events (BrakeEngaged/BrakeReleased) pin the regime."""
        ob = self._outbox(tenant)
        now = self._ts()
        previous = ob.last_emitted_version(AGGREGATE_TYPE, aggregate_id, below=int(aggregate_version))
        pins: dict[str, Any] = {}
        if consequential:
            pins = {
                "entity_versions": {"brake": int(aggregate_version)},
                "policy_version": self._current_policy_version(tenant),
                "brake_version": self._version_token_locked(tenant),
            }
        envelope = EventEnvelope(
            event_id=str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version,
            occurred_at=now, recorded_at=now, tenant_id=tenant,
            aggregate_type=AGGREGATE_TYPE, aggregate_id=aggregate_id,
            aggregate_version=int(aggregate_version), previous_aggregate_version=previous,
            causation_id=None, correlation_id=aggregate_id,
            producer_component=PRODUCER_COMPONENT, producer_transition_id=transition_id,
            actor_type=self._actor_type(actor_kind), actor_id=actor,
            trace_id=f"trace-{aggregate_id}", payload=dict(payload), **pins,
        )
        ob.emit(envelope)

    def _store_security_event(self, tenant: str, envelope: EventEnvelope, actor: str) -> None:
        next_id = self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM security_events WHERE tenant = ?",
            (tenant,),
        ).fetchone()[0]
        self._conn.execute(
            "INSERT INTO security_events (tenant, id, event_type, actor, payload_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (tenant, next_id, envelope.event_name, actor,
             json.dumps(dict(envelope.payload), sort_keys=True), self._ts()),
        )

    def _ts(self) -> str:
        return format_instant(self._clock())

    @staticmethod
    def _actor_type(actor_kind: str) -> str:
        return {"HUMAN": "human", "DETECTOR": "detector"}.get(actor_kind, "system")

    @staticmethod
    def _f14_actor_type(attempted_kind: str) -> str:
        # The F14 event is the SYSTEM recording that a non-human attempted a release — the recorder
        # is the system, and the ATTEMPTED kind travels in the payload. A detector attempt is
        # recorded as `detector`; everything else (automation, a model, a timer, a retry handler, a
        # counterparty) is `system`. It is never `model`: ER-9 forbids a model actor_type from
        # producing anything but a claim/proposal, and this security record is neither.
        return "detector" if str(attempted_kind).upper() == "DETECTOR" else "system"

    @staticmethod
    def _require_actor(actor: str, actor_kind: str) -> str:
        if not str(actor or "").strip():
            raise BrakeError("a brake operation records WHO; an empty actor is not an actor")
        if actor_kind not in (HUMAN, DETECTOR):
            raise BrakeError(
                f"actor_kind must be {HUMAN!r} or {DETECTOR!r}, got {actor_kind!r}. A model is "
                f"neither: it may raise a signal for a detector, never touch the brake itself."
            )
        return actor_kind

    @staticmethod
    def _row_status(row: sqlite3.Row) -> BrakeStatus:
        keys = row.keys()
        return BrakeStatus(
            brake_id=row["brake_id"], tenant=row["tenant"], scope=row["scope"],
            state=row["state"], actor=row["actor"], actor_kind=row["actor_kind"],
            engaged_reason=row["engaged_reason"], engaged_at=row["engaged_at"],
            brake_version=int(row["brake_version"]),
            signal_count=int(row["signal_count"]) if "signal_count" in keys else 1,
        )

    @staticmethod
    def _platform_status_row(row: sqlite3.Row) -> BrakeStatus:
        keys = row.keys()
        return BrakeStatus(
            brake_id="platform", tenant=None, scope="GLOBAL", state=row["state"],
            actor=row["actor"] or "", actor_kind=row["actor_kind"] or "",
            engaged_reason=row["engaged_reason"] or "", engaged_at=row["engaged_at"] or "",
            brake_version=int(row["brake_version"]),
            signal_count=int(row["signal_count"]) if "signal_count" in keys else 0,
        )
