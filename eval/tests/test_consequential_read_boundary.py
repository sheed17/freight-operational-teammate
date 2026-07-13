"""Structural guard: a CONSEQUENTIAL_FRESHNESS_READ may never acquire a cache source.

WHY THIS TEST EXISTS (finding V-3, docs/architecture/tms-read-cache-safety-review.md):

``_build_load_amount_resolver`` is the reader that supplies the AMOUNT which gets bound into a money
action. It performs a LIVE read. It sits DIRECTLY BETWEEN two sibling readers
(``_build_receivables_reader``, ``_build_tms_brief_reader``) which — once Stream B's read cache is
promoted — take a ``cache_path``, with an identical signature shape.

Adding ``cache_path=...`` to the amount resolver is therefore a ONE-LINE change that:
  * is visually consistent with its neighbours,
  * reads as an obvious "symmetry fix" to a future engineer or coding agent tidying an inconsistency,
  * would be INVISIBLE in review,
  * and would immediately begin feeding CACHED, POSSIBLY-STALE AMOUNTS INTO THE MONEY FENCE.

That is a direct violation of ADR-001 C4:
    "The projection is for KNOWING. The authoritative system is for ACTING.
     A consequential action MUST revalidate against the authoritative source at execution time."

The cache is not unsafe today. It is one plausible line away from being unsafe, and nothing in the
code says so. A comment would not stop it. This test does.

This guard is deliberately landed BEFORE the read cache is promoted: the tripwire must exist before
the mine. Under ADR-004 it becomes redundant (the atomic pre-effect checkpoint revalidates against
the authoritative source regardless) — but ADR-004 is not built yet.

If you are here because this test failed: you are about to let a cached value decide money.
Do not "fix" the test. The reader you are editing must read LIVE, or it must not be consequential.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

# The register of CONSEQUENTIAL_FRESHNESS_READ builders: readers whose value can reach a financial
# effect. Adding a reader here is how you declare "this one decides money."
CONSEQUENTIAL_READ_BUILDERS = [
    "_build_load_amount_resolver",
]

# Constructor parameters that would give a reader a non-live source. A generic "read provider" counts:
# it is a cache in disguise — the reader can no longer prove its value came from the authoritative system.
FORBIDDEN_PARAM_SUBSTRINGS = ("cache", "cached", "stale", "fallback", "read_provider", "provider", "snapshot")

# Symbols that indicate a non-live source is reachable from inside the reader body.
FORBIDDEN_BODY_SYMBOLS = ("TmsReadCache", "tms_read_cache", "cache_path", "allow_stale", "CachedTmsRead")


def _load_builder(name):
    import run_action_callback_server as server

    fn = getattr(server, name, None)
    assert fn is not None, (
        f"{name} is on the CONSEQUENTIAL read register but no longer exists. "
        "If it was renamed, update the register — do not delete the guard."
    )
    return fn


@pytest.mark.parametrize("builder_name", CONSEQUENTIAL_READ_BUILDERS)
def test_consequential_reader_cannot_accept_a_cache_source(builder_name):
    """The money-sensitive resolver must be STRUCTURALLY unable to take a cache."""
    fn = _load_builder(builder_name)
    params = list(inspect.signature(fn).parameters)
    for param in params:
        lowered = param.lower()
        for forbidden in FORBIDDEN_PARAM_SUBSTRINGS:
            assert forbidden not in lowered, (
                f"\n\n  {builder_name}() gained the parameter '{param}'.\n"
                f"  This reader supplies the AMOUNT bound into a money action. It MUST read live.\n"
                f"  A cached or stale amount reaching the money fence violates ADR-001 C4.\n"
                f"  See docs/architecture/tms-read-cache-safety-review.md (V-3).\n"
            )


@pytest.mark.parametrize("builder_name", CONSEQUENTIAL_READ_BUILDERS)
def test_consequential_reader_body_references_no_cache(builder_name):
    """Belt and braces: no cache symbol may be reachable from inside the reader either."""
    fn = _load_builder(builder_name)
    source = inspect.getsource(fn)
    for symbol in FORBIDDEN_BODY_SYMBOLS:
        assert symbol not in source, (
            f"\n\n  {builder_name}() references '{symbol}'.\n"
            f"  A consequential freshness read may not consult a cache, on any code path.\n"
        )


def test_the_consequential_register_is_not_silently_emptied():
    """Deleting the register would make the guard vacuously pass. It must never be empty."""
    assert CONSEQUENTIAL_READ_BUILDERS, "the CONSEQUENTIAL read register must not be empty"


def test_cached_readers_are_the_only_readers_permitted_a_cache():
    """Document, structurally, WHICH readers may hold a cache — so a new one cannot appear unnoticed.

    Informational + decision-support readers MAY cache (with disclosure). Consequential readers MAY NOT.
    If a reader not on this list acquires a cache_path, that is a new, unclassified cached read path and
    it must be classified before it ships.
    """
    server_src = (ROOT / "scripts" / "run_action_callback_server.py").read_text()
    tree = ast.parse(server_src)

    permitted_to_cache = {
        "_build_receivables_reader",   # DECISION_SUPPORT_READ  (must disclose staleness — V-1)
        "_build_tms_brief_reader",     # INFORMATIONAL_READ     (must show as_of — V-2)
    }

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("_build_"):
            continue
        args = [a.arg for a in node.args.args + node.args.kwonlyargs]
        if any("cache" in a.lower() for a in args) and node.name not in permitted_to_cache:
            offenders.append(node.name)

    assert not offenders, (
        f"\n\n  These readers acquired a cache but are not classified as cacheable: {offenders}\n"
        f"  Classify the read (INFORMATIONAL / DECISION_SUPPORT / CONSEQUENTIAL) before shipping it.\n"
        f"  A CONSEQUENTIAL read may never be cached. See docs/architecture/stream-b-review.md.\n"
    )
