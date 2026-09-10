"""The Evidence Store — Phase 7.

Evidence is a retained artifact, and the span within it, that a human would look at to check a claim
(ADR-007 sec 3, entity 08-evidence). This module is the Evidence Store (entity sec 5): it retains
content-addressed immutable artifacts, appends the spans that make a MODEL_EXTRACTED claim checkable,
and answers "may a consequential action rest on this evidence?" — failing CLOSED when the artifact is
lost or illegible.

THE LOAD-BEARING RULES THIS STORE ENFORCES

  * ### Content addressing is the identity (entity sec 8/9/17/21/33). `content_digest` is a RUNTIME
    sha256 of the bytes — never taken from a caller — and identical bytes DEDUPLICATE to one Evidence.
    Storing the same bytes twice is idempotent: it returns the existing row (C-3).
  * ### The digest is verified against the bytes ON WRITE (entity sec 16/37/43(b)). A caller that
    supplies an `expected_digest` that does not match the bytes is REFUSED — a row whose stored bytes
    do not match its digest is a structurally impossible state.
  * ### Evidence is DATA (entity sec 35, M-66). It may EVIDENCE a claim; it may never MAKE one,
    authorize an effect, or set provenance. So the store writes no `provenance_class` and mints no
    gate decision — the provenance_class that says HOW a value came to be believed lives on the CLAIM
    that points at the span (M6).
  * ### A MODEL_EXTRACTED claim MUST reference an Evidence span (entity sec 13/43(c), ADR-002
    sec 2.3). The store refuses to certify a MODEL_EXTRACTED claim against an Evidence with no span.
  * ### Lost or illegible evidence BLOCKS the consequential action (entity sec 36, ADR-007 sec 10).
    A claim whose evidence we can no longer show is a claim we can no longer defend, so the store
    fails closed rather than degrading to "best available".
  * ### Immutable and never deleted (entity sec 6/16/22/26/28, C-8). The database triggers enforce
    it; this store never issues an UPDATE of content and never a DELETE.

SHIPS DARK. Nothing in production imports this module; the checkpoint stays the sole gate minter and
this store mints nothing. Only `scripts/probe_phase7_evidence.py` and the Phase-7 tests reach it.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass

from .tenant import require_tenant

# The provenance class that a model READ off an artifact and that is therefore checkable only WITH a
# retained span (ADR-002 sec 2.3, entity 08-evidence sec 13/43(c)). Named as a constant so the span
# requirement points at the same word M6's `ck_ibc_model_extracted_needs_span` does; the full
# six-member canonical provenance vocabulary is a separate Phase-7 increment (AC-2) and is not
# redefined here.
MODEL_EXTRACTED = "MODEL_EXTRACTED"

# The evidence-anchor conditions this store distinguishes. `stale`, `unknown` and `conflicting` are
# CLAIM-level conditions (ADR-002 C5) and are not answered here — an artifact is either present and
# legible (`consistent`), present but unreadable (`illegible`), or gone (`absent`). Kept DISTINCT:
# collapsing `absent` into `consistent` is exactly the fail-open defect entity sec 36 forbids.
CONDITION_CONSISTENT = "consistent"
CONDITION_ILLEGIBLE = "illegible"
CONDITION_ABSENT = "absent"


class EvidenceError(Exception):
    """Base class for Evidence Store refusals."""


class DigestMismatch(EvidenceError):
    """The bytes do not hash to the digest the caller expected — refused on write (entity sec 43(b))."""


class EvidenceAbsent(EvidenceError):
    """The referenced Evidence is not retained: a consequential action on it BLOCKS (entity sec 36)."""


class EvidenceIllegible(EvidenceError):
    """The Evidence is retained but unreadable: a consequential action on it BLOCKS (entity sec 36)."""


class SpanRequired(EvidenceError):
    """A MODEL_EXTRACTED claim was certified against an Evidence with no span (entity sec 13/43(c))."""


@dataclass(frozen=True)
class EvidenceRecord:
    """A read-only view of one retained artifact. Not the bytes — the content-addressed record."""

    tenant: str
    evidence_id: str
    content_digest: str
    content_ref: str
    media_type: str
    source_observation_id: str
    illegible: bool
    superseded_by: str | None
    created_at: str


def content_digest_of(content: object) -> str:
    """The RUNTIME content digest: a sha256 hex of the bytes. Never taken from inbound content — the
    store computes it, so a caller can never assert a digest the bytes do not support (R-P1 analog).
    Accepts `object` and validates: this is the boundary where a non-bytes artifact is refused."""
    if not isinstance(content, (bytes, bytearray)):
        raise EvidenceError(
            "evidence content must be raw bytes: the digest is computed from the bytes retained, and "
            "a str has no single canonical byte encoding to hash"
        )
    return hashlib.sha256(bytes(content)).hexdigest()


class EvidenceStore:
    """The Evidence Store over one connection. Store-and-register is one transaction (entity sec 15)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # -- retention ---------------------------------------------------------------------------------

    def retain(
        self,
        tenant: object,
        *,
        content: bytes,
        media_type: str,
        source_observation_id: str,
        now: str,
        evidence_id: str | None = None,
        expected_digest: str | None = None,
    ) -> str:
        """Retain an artifact content-addressed, and return its `evidence_id`.

        Identical bytes deduplicate to ONE Evidence (entity sec 17/33): a second retention of the same
        (tenant, content_digest) returns the existing row rather than creating a duplicate, and the
        race between two concurrent retentions is decided by the UNIQUE index in the database, not by a
        check in this method. If `expected_digest` is supplied and does not match the RUNTIME digest of
        the bytes, the write is REFUSED (entity sec 43(b)).
        """
        tenant = require_tenant(tenant, context="EvidenceStore.retain")
        if not (isinstance(media_type, str) and media_type.strip()):
            raise EvidenceError("media_type is required: an artifact with no media type cannot be shown")
        if not (isinstance(source_observation_id, str) and source_observation_id.strip()):
            raise EvidenceError(
                "source_observation_id is required: an Evidence enters via the Observation that "
                "retained it (entity sec 10/14). An artifact from nowhere has no lineage."
            )
        digest = content_digest_of(content)
        if expected_digest is not None and expected_digest != digest:
            raise DigestMismatch(
                f"the stored bytes hash to {digest!r} but the caller expected {expected_digest!r}: a "
                f"content-addressed row whose bytes do not match its digest is a structurally "
                f"impossible state (entity 08-evidence sec 16/37/43(b))."
            )
        content_ref = f"sha256:{digest}"

        # Content addressing is idempotency: the same bytes already retained ARE the same Evidence.
        existing = self._id_for_digest(tenant, digest)
        if existing is not None:
            return existing

        new_id = evidence_id or uuid.uuid4().hex
        try:
            self.conn.execute(
                "INSERT INTO evidence (tenant, evidence_id, content_digest, content_ref, media_type, "
                "source_observation_id, illegible, superseded_by, created_at) "
                "VALUES (?,?,?,?,?,?,0,NULL,?)",
                (tenant, new_id, digest, content_ref, media_type, source_observation_id, now),
            )
            self.conn.commit()
            return new_id
        except sqlite3.IntegrityError:
            # A concurrent writer won the (tenant, content_digest) race: the DB, not a Python check,
            # serialized us, and dedup is the correct outcome. If the collision was NOT the digest
            # (e.g. a foreign-key violation on source_observation_id), there is no such row and we
            # re-raise the real error rather than masking it.
            self.conn.rollback()
            raced = self._id_for_digest(tenant, digest)
            if raced is not None:
                return raced
            raise

    def _id_for_digest(self, tenant: str, digest: str) -> str | None:
        row = self.conn.execute(
            "SELECT evidence_id FROM evidence WHERE tenant = ? AND content_digest = ?",
            (tenant, digest),
        ).fetchone()
        return row[0] if row else None

    # -- spans -------------------------------------------------------------------------------------

    def attach_span(
        self,
        tenant: object,
        evidence_id: str,
        *,
        locator: str,
        now: str,
        region: str | None = None,
        extracted_text: str | None = None,
        span_id: str | None = None,
    ) -> str:
        """Append a span — the WHERE a claim points into the artifact (entity sec 11/22). Appending a
        span never edits the content; a span, once written, is itself immutable."""
        tenant = require_tenant(tenant, context="EvidenceStore.attach_span")
        if not (isinstance(locator, str) and locator.strip()):
            raise EvidenceError("a span must name WHERE it is: locator (page|offset) is required")
        if self.get(tenant, evidence_id) is None:
            raise EvidenceAbsent(
                f"cannot attach a span to Evidence {evidence_id!r}: it is not retained. A span into "
                f"nothing is a location into an artifact that does not exist (entity sec 11/14)."
            )
        new_id = span_id or uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO evidence_spans (tenant, span_id, evidence_id, locator, region, "
            "extracted_text, created_at) VALUES (?,?,?,?,?,?,?)",
            (tenant, new_id, evidence_id, locator, region, extracted_text, now),
        )
        self.conn.commit()
        return new_id

    def spans_for(self, tenant: object, evidence_id: str) -> list[dict]:
        tenant = require_tenant(tenant, context="EvidenceStore.spans_for")
        rows = self.conn.execute(
            "SELECT span_id, evidence_id, locator, region, extracted_text, created_at "
            "FROM evidence_spans WHERE tenant = ? AND evidence_id = ? ORDER BY span_id",
            (tenant, evidence_id),
        ).fetchall()
        return [
            {"span_id": r[0], "evidence_id": r[1], "locator": r[2], "region": r[3],
             "extracted_text": r[4], "created_at": r[5]}
            for r in rows
        ]

    # -- annotations (the only mutable columns) ----------------------------------------------------

    def mark_illegible(self, tenant: object, evidence_id: str) -> None:
        """Record that a retained artifact is unreadable (entity sec 11/36). This is a legibility
        observation, not a content edit; a consequential action on illegible evidence BLOCKS."""
        tenant = require_tenant(tenant, context="EvidenceStore.mark_illegible")
        if self.get(tenant, evidence_id) is None:
            raise EvidenceAbsent(f"Evidence {evidence_id!r} is not retained")
        self.conn.execute(
            "UPDATE evidence SET illegible = 1 WHERE tenant = ? AND evidence_id = ?",
            (tenant, evidence_id),
        )
        self.conn.commit()

    def supersede(self, tenant: object, old_evidence_id: str, new_evidence_id: str) -> None:
        """A newer artifact supersedes an older one (entity sec 24). The OLD is RETAINED — a claim may
        have rested on it — and only the `superseded_by` link is set; the bytes never change."""
        tenant = require_tenant(tenant, context="EvidenceStore.supersede")
        if self.get(tenant, old_evidence_id) is None:
            raise EvidenceAbsent(f"cannot supersede {old_evidence_id!r}: it is not retained")
        if self.get(tenant, new_evidence_id) is None:
            raise EvidenceAbsent(f"cannot supersede with {new_evidence_id!r}: it is not retained")
        self.conn.execute(
            "UPDATE evidence SET superseded_by = ? WHERE tenant = ? AND evidence_id = ?",
            (new_evidence_id, tenant, old_evidence_id),
        )
        self.conn.commit()

    # -- reads and fail-closed guards --------------------------------------------------------------

    def get(self, tenant: object, evidence_id: str) -> EvidenceRecord | None:
        tenant = require_tenant(tenant, context="EvidenceStore.get")
        row = self.conn.execute(
            "SELECT tenant, evidence_id, content_digest, content_ref, media_type, "
            "source_observation_id, illegible, superseded_by, created_at "
            "FROM evidence WHERE tenant = ? AND evidence_id = ?",
            (tenant, evidence_id),
        ).fetchone()
        if row is None:
            return None
        return EvidenceRecord(
            tenant=row[0], evidence_id=row[1], content_digest=row[2], content_ref=row[3],
            media_type=row[4], source_observation_id=row[5], illegible=bool(row[6]),
            superseded_by=row[7], created_at=row[8],
        )

    def evidence_condition(self, tenant: object, evidence_id: str) -> str:
        """`consistent`, `illegible` or `absent` — the three evidence-anchor conditions, kept DISTINCT
        (ADR-002 C5). Absent (lost/unretrievable) and illegible are the two that fail closed."""
        record = self.get(tenant, evidence_id)
        if record is None:
            return CONDITION_ABSENT
        if record.illegible:
            return CONDITION_ILLEGIBLE
        return CONDITION_CONSISTENT

    def claim_may_proceed_on(self, tenant: object, evidence_id: str) -> bool:
        """Fail-closed: a consequential action may rest on this Evidence ONLY when it is present and
        legible. Absent or illegible ⇒ False, so the caller BLOCKS rather than acting on a claim it
        can no longer defend (entity sec 36, ADR-002 C6)."""
        return self.evidence_condition(tenant, evidence_id) == CONDITION_CONSISTENT

    def assert_supports_consequential_action(self, tenant: object, evidence_id: str) -> None:
        """Raise the fail-closed exception a consequential path must not swallow. The distinction
        between absent and illegible is preserved in the exception type (both BLOCK, entity sec 36)."""
        condition = self.evidence_condition(tenant, evidence_id)
        if condition == CONDITION_ABSENT:
            raise EvidenceAbsent(
                f"Evidence {evidence_id!r} is absent: a claim whose evidence we can no longer show is "
                f"a claim we can no longer defend — the consequential action BLOCKS (entity sec 36)."
            )
        if condition == CONDITION_ILLEGIBLE:
            raise EvidenceIllegible(
                f"Evidence {evidence_id!r} is illegible: it cannot be shown to a human, so the "
                f"consequential action BLOCKS rather than degrading to best-available (entity sec 36)."
            )

    def require_span_for_model_extracted(
        self, tenant: object, evidence_id: str, provenance_class: str
    ) -> None:
        """A MODEL_EXTRACTED claim MUST reference an Evidence span (entity sec 13/43(c), ADR-002
        sec 2.3): that span is exactly what distinguishes a checkable MODEL_EXTRACTED reading from a
        MODEL_INFERRED guess. A MODEL_EXTRACTED claim against an Evidence with no span is refused."""
        if provenance_class != MODEL_EXTRACTED:
            return
        if not self.spans_for(tenant, evidence_id):
            raise SpanRequired(
                f"a {MODEL_EXTRACTED} claim references Evidence {evidence_id!r}, which has no span: a "
                f"model saying it read a value off an artifact is checkable only WITH the region it "
                f"read (entity sec 13/43(c)). Without a span it is indistinguishable from a guess."
            )

    def trace(self, tenant: object, evidence_id: str) -> dict:
        """Walk from an Evidence to its complete chain: the artifact, its spans, and the Observation
        that retained it (ADR-002 sec 2.1 concern 5, ADR-007 sec 13). The chain terminates in a
        source observation id, never in a dangling pointer."""
        tenant = require_tenant(tenant, context="EvidenceStore.trace")
        record = self.get(tenant, evidence_id)
        if record is None:
            raise EvidenceAbsent(f"Evidence {evidence_id!r} is not retained: nothing to trace")
        return {
            "evidence": record,
            "spans": self.spans_for(tenant, evidence_id),
            "source_observation_id": record.source_observation_id,
            "superseded_by": record.superseded_by,
        }
