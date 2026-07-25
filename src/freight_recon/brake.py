"""The human brake — admission control (ADR-011, machine M13).

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
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from .tenant import require_tenant

# Scope grammar at P3: the whole tenant, or one action class within it. Wider vocabularies
# (counterparty, integration) arrive with the policy runtime (P8); the grammar is closed here so
# an unparseable scope cannot silently scope to nothing.
TENANT_WIDE = "tenant"

HUMAN = "HUMAN"
DETECTOR = "DETECTOR"

_TOKEN_PREFIX = "bv1"


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


def _scope_for(action_class: str | None) -> str:
    if action_class is None:
        return TENANT_WIDE
    text = str(action_class).strip().lower()
    if not text:
        raise BrakeError("an action-class brake scope needs a non-empty action class")
    return f"action:{text}"


class BrakeStore:
    """Brake reads and writes over one canonical database connection.

    Deliberately NOT bound to a tenant the way WorkflowStore is: the platform brake belongs to no
    tenant, and a Sev-0 tenant-isolation signal must be able to engage GLOBALLY. Tenant-scoped
    operations validate their tenant argument at the boundary exactly as the store does.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------ writes (the ratchet)

    def engage(
        self,
        *,
        tenant: str | None,
        action_class: str | None = None,
        actor: str,
        actor_kind: str,
        reason: str,
    ) -> BrakeStatus:
        """BR-1: any authenticated human INSTANTLY, or an automated Sev-0 detector. One row write.

        NEVER requires the system to be healthy. Idempotent on scope: engaging an already-braked
        scope records nothing new and returns the existing brake — a flapping detector is one
        ACTIVE brake, not a pile, and it cannot self-release, so flapping opens no window.
        """
        kind = self._require_actor(actor, actor_kind)
        if not str(reason or "").strip():
            raise BrakeError("a brake engagement records WHY; an empty reason is not a reason")
        if tenant is None:
            return self._engage_platform(actor=actor, actor_kind=kind, reason=reason)
        bound = require_tenant(tenant, context="BrakeStore.engage")
        scope = _scope_for(action_class)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self._conn.execute(
                "SELECT * FROM brakes WHERE tenant = ? AND scope = ? AND state = 'ACTIVE'",
                (bound, scope),
            ).fetchone()
            if existing is not None:
                self._conn.rollback()
                return self._row_status(existing)
            version = self._next_tenant_version_locked(bound)
            brake_id = str(uuid.uuid4())
            now = _now()
            self._conn.execute(
                """
                INSERT INTO brakes (
                    tenant, brake_id, scope, state, actor, actor_kind, engaged_reason,
                    engaged_at, brake_version
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?)
                """,
                (bound, brake_id, scope, actor, kind, reason, now, version),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return BrakeStatus(
            brake_id=brake_id, tenant=bound, scope=scope, state="ACTIVE", actor=actor,
            actor_kind=kind, engaged_reason=reason, engaged_at=now, brake_version=version,
        )

    def widen(self, *, tenant: str, brake_id: str, actor: str, actor_kind: str) -> BrakeStatus:
        """BR-2: widening a brake NARROWS AUTHORITY, so human OR automation may do it.

        At P3's closed scope grammar, widening means action-class -> tenant-wide.
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
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return self.status(tenant=bound, brake_id=brake_id)

    def narrow(
        self, *, tenant: str, brake_id: str, actor: str, actor_kind: str, to_action_class: str,
        decision_ref: str,
    ) -> BrakeStatus:
        """BR-3: narrowing a brake BROADENS AUTHORITY => an authenticated human ONLY."""
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

        Release preconditions beyond authority (in-flight effects accounted for, no unresolved
        Sev-0 in scope) are read against the ledger by the caller at P3-proportionate depth in
        `release_blockers`; this method enforces the structural ones the database can state.
        """
        kind = self._require_actor(actor, actor_kind)
        if kind != HUMAN:
            raise BrakeError(
                "automation may never release a brake — a detector cannot clear its own alarm "
                "(ADR-011 §6). Release is a human act with a decision_ref."
            )
        if not str(decision_ref or "").strip():
            raise BrakeError("release requires a decision_ref: an unexplained release is not a decision")
        now = _now()
        if tenant is None:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._platform_row_locked()
                if row["state"] != "ACTIVE":
                    self._conn.rollback()
                    raise BrakeError("the platform brake is not ACTIVE; nothing to release")
                self._conn.execute(
                    "UPDATE platform_brake SET state = 'RELEASED', brake_version = brake_version + 1, "
                    "released_by = ?, release_decision_ref = ?, released_at = ? WHERE id = 1",
                    (actor, decision_ref, now),
                )
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
                "release_decision_ref = ?, released_at = ? "
                "WHERE tenant = ? AND brake_id = ? AND state = 'ACTIVE'",
                (version, actor, decision_ref, now, bound, brake_id),
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

    # ------------------------------------------------------------------ reads (fail closed)

    def admission_denied(self, *, tenant: str, action_class: str) -> BrakeStatus | None:
        """The checkpoint step-7 / claim-CAS read: the ACTIVE brake covering this effect, if any.

        Read order is platform -> tenant-wide -> action-class, so the widest applicable brake is
        the one reported. Any read failure raises BrakeStoreUnreachable: the caller refuses.
        """
        bound = require_tenant(tenant, context="BrakeStore.admission_denied")
        scope = _scope_for(action_class)
        try:
            platform = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
            if platform is None:
                raise BrakeStoreUnreachable(
                    "the platform brake row is absent; refusing — an unreadable brake is not a "
                    "released brake"
                )
            if platform["state"] == "ACTIVE":
                return self._platform_status_row(platform)
            row = self._conn.execute(
                "SELECT * FROM brakes WHERE tenant = ? AND state = 'ACTIVE' "
                "AND scope IN (?, ?) ORDER BY CASE scope WHEN ? THEN 0 ELSE 1 END LIMIT 1",
                (bound, TENANT_WIDE, scope, TENANT_WIDE),
            ).fetchone()
            return self._row_status(row) if row is not None else None
        except sqlite3.Error as exc:
            raise BrakeStoreUnreachable(f"brake state could not be read: {exc}") from exc

    def version_token(self, *, tenant: str) -> str:
        """The composite brake-version token bound into witnesses and grants (M13 §17).

        Deterministic serialization of BOTH monotonic versions. Any brake event on either owner
        changes the token, which is exactly what makes the claim CAS refuse after one.
        """
        bound = require_tenant(tenant, context="BrakeStore.version_token")
        try:
            platform = self._conn.execute(
                "SELECT brake_version FROM platform_brake WHERE id = 1").fetchone()
            if platform is None:
                raise BrakeStoreUnreachable(
                    "the platform brake row is absent; a version token cannot be derived"
                )
            tenant_version = self._conn.execute(
                "SELECT COALESCE(MAX(brake_version), 0) AS v FROM brakes WHERE tenant = ?",
                (bound,),
            ).fetchone()["v"]
            return f"{_TOKEN_PREFIX}|global:{int(platform['brake_version'])}|tenant:{int(tenant_version)}"
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
        row = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
        if row is None:
            raise BrakeStoreUnreachable("the platform brake row is absent")
        return self._platform_status_row(row)

    def active_report(self, *, tenant: str) -> list[BrakeStatus]:
        """Every ACTIVE brake affecting this tenant, platform first (R17: reported unprompted)."""
        bound = require_tenant(tenant, context="BrakeStore.active_report")
        out: list[BrakeStatus] = []
        platform = self._conn.execute("SELECT * FROM platform_brake WHERE id = 1").fetchone()
        if platform is not None and platform["state"] == "ACTIVE":
            out.append(self._platform_status_row(platform))
        rows = self._conn.execute(
            "SELECT * FROM brakes WHERE tenant = ? AND state = 'ACTIVE' ORDER BY engaged_at",
            (bound,),
        ).fetchall()
        out.extend(self._row_status(r) for r in rows)
        return out

    # ------------------------------------------------------------------ internals

    def _engage_platform(self, *, actor: str, actor_kind: str, reason: str) -> BrakeStatus:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._platform_row_locked()
            if row["state"] == "ACTIVE":
                self._conn.rollback()
                return self._platform_status_row(row)
            self._conn.execute(
                "UPDATE platform_brake SET state = 'ACTIVE', brake_version = brake_version + 1, "
                "actor = ?, actor_kind = ?, engaged_reason = ?, engaged_at = ?, released_by = NULL, "
                "release_decision_ref = NULL, released_at = NULL WHERE id = 1",
                (actor, actor_kind, reason, _now()),
            )
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
        return BrakeStatus(
            brake_id=row["brake_id"], tenant=row["tenant"], scope=row["scope"],
            state=row["state"], actor=row["actor"], actor_kind=row["actor_kind"],
            engaged_reason=row["engaged_reason"], engaged_at=row["engaged_at"],
            brake_version=int(row["brake_version"]),
        )

    @staticmethod
    def _platform_status_row(row: sqlite3.Row) -> BrakeStatus:
        return BrakeStatus(
            brake_id="platform", tenant=None, scope="GLOBAL", state=row["state"],
            actor=row["actor"] or "", actor_kind=row["actor_kind"] or "",
            engaged_reason=row["engaged_reason"] or "", engaged_at=row["engaged_at"] or "",
            brake_version=int(row["brake_version"]),
        )


def _now() -> str:
    from .workflow import utc_now

    return utc_now()
