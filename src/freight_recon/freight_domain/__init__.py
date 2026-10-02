"""P9 — the freight-domain spine.

The canonical freight entities of `docs/specifications/domain-entities/registry.md`, projected from
the foundational primitives P6-P8 already landed: an inbound record becomes an Observation (M5), is
bound to a canonical entity by an Identity Binding Claim (M6) resolved through the External Entity
Mapping, and the canonical Brokerage Load, Carrier Movement, Stops, Documents, Messages, Tracking
Events and financial records are a deterministic fold over those durable records. Disagreement is a
Conflict (M7), a missing thing is an Expectation (M8), and anything a human must decide is an
Exception (M9) with one accountable owner.

### NO NEW PLATFORM PRIMITIVE. This package defines no second conflict system, no second expectation
system, no second provenance vocabulary and no gate. `foundation.py` is the ONE module that imports
the P6-P8 machines; every other module here reaches them through it.

### SHIPS DARK. Nothing on a live path imports this package. It calls no adapter, performs no external
effect, mints no witness or grant, and uses no model: correlation is deterministic and exact, and the
place where model-assisted candidate generation will later attach is an explicit, empty boundary.
"""
