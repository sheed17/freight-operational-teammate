"""The tenant identity boundary.

A tenant is not a string that happens to be present. It is an identity that must have come from
somewhere canonical — an authenticated request, a worker message, a tenant-scoped configuration
record, or an operator's explicit assertion. This type cannot check where a value came from, but it
can refuse the values that betray that nobody decided: empty, blank, and the sentinels people reach
for when they have no answer and need the code to run anyway.

    "default" is not a tenant. It is the absence of one, spelled in a way that compiles.

That matters more here than it looks. A sentinel tenant does not fail loudly; it succeeds, and it
keeps succeeding, right up until two tenants share a database and one of them silently reads,
deduplicates against, or overwrites the other's rows. The whole point of Phase 2 is that this cannot
be reached by accident.
"""

from __future__ import annotations

# Values that mean "nobody decided". Each is a real habit, not a hypothetical: `tenant="default"`
# already exists in this repository's production code today.
FORBIDDEN_TENANTS = frozenset({
    "default", "global", "unknown", "none", "null", "n/a", "na", "-",
    "all", "any", "shared", "common", "system", "root", "admin",
    "tenant", "test",          # placeholders that leak from fixtures into production
    "todo", "tbd", "changeme", "placeholder", "example",
})


class MissingTenant(ValueError):
    """No tenant identity was supplied where one is structurally required. Fail closed."""


class InvalidTenant(ValueError):
    """A value was supplied that cannot be a tenant identity."""


def require_tenant(value: object, *, context: str = "") -> str:
    """Return a normalised tenant id, or refuse. There is no default and no fallback.

    Refusing is the feature. A caller that cannot name its tenant is a caller that does not know
    whose data it is about to touch, and the safe answer to that is to stop.
    """
    where = f" ({context})" if context else ""
    if value is None:
        raise MissingTenant(
            f"no tenant identity was supplied{where}. There is no default: a store must know whose "
            f"data it is reading and writing before it may do either."
        )
    if not isinstance(value, str):
        raise InvalidTenant(f"tenant must be a string, got {type(value).__name__}{where}")
    text = value.strip()
    if not text:
        raise MissingTenant(f"tenant identity is empty or blank{where}")
    if text.lower() in FORBIDDEN_TENANTS:
        raise InvalidTenant(
            f"{value!r} is not a tenant identity{where} — it is a placeholder for not having one. "
            f"Supply the canonical tenant (an authenticated request, a worker message, a "
            f"tenant-scoped config record, or an operator's explicit assertion)."
        )
    return text
