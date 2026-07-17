"""Resolve the canonical tenant for a command-line entry point. Explicit or nothing.

The canonical production tenant source is `client_id` in the client configuration — a tenant-scoped
configuration record naming the Neyma workspace. It is stable, it is not a counterparty, it is not a
display name, and it is not derived from any document, load, or email.

    A CLI that cannot name its tenant does not get a store.

There is no default and no fallback. `--tenant` is offered for operator tools that legitimately
select a tenant by hand; everything else reads `client_id` from the client config it was already
given. If neither is present the entry point fails here, before any persistence exists.
"""

from __future__ import annotations

from pathlib import Path

from .tenant import MissingTenant, require_tenant


def tenant_from_client_config(path: str | Path) -> str:
    """The canonical source: `client_id` from a tenant-scoped client configuration record."""
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    client_id = data.get("client_id")
    if not client_id:
        raise MissingTenant(
            f"{path} has no `client_id`, so it names no tenant. A client config without one cannot "
            f"establish whose data this process may touch."
        )
    return require_tenant(client_id, context=f"client_config={path}")


def resolve_cli_tenant(*, tenant: str | None = None, client_config: str | None = None,
                       context: str = "") -> str:
    """An explicit --tenant, or the client config's client_id. Never a guess.

    Order matters: an operator's explicit selection wins over the config, because an operator tool is
    exactly the case where a human is deliberately choosing which tenant to act on. Absent both, this
    raises - it does not pick.
    """
    if tenant:
        return require_tenant(tenant, context=context or "--tenant")
    if client_config:
        return tenant_from_client_config(client_config)
    raise MissingTenant(
        f"no tenant identity{' for ' + context if context else ''}: pass --tenant, or --client-config "
        f"naming a client configuration whose `client_id` identifies the workspace. There is no "
        f"default — this process will not guess whose data it is about to touch."
    )
