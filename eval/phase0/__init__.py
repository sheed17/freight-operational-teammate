"""Phase-0 baseline and migration guards.

Phase 0 does not make anything safe. It makes the current unsafe state explicit, measurable, and
unable to regress silently. Every probe here RECOMPUTES a repository fact and compares it to an
adjudicated baseline manifest; a changed fact requires deliberate adjudication, never a silent pass.

See docs/implementation/phase-0-implementation-review.md.
"""
