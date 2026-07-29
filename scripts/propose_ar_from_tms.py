"""Read ready-to-bill loads from the LIVE TMS and post AR invoice Approve buttons to Slack.

The AR trigger, real-TMS sourced (vs the synthetic corpus): open the human-logged-in TMS's loads
page, read which loads are delivered-but-not-invoiced and their Total, and post one signed
"Invoice [Approve & run]" button per load at that Total. A tap then drives the PROVEN raise_invoice
write — so the proposed load_ref always matches a writable record.

THE BROWSER SURFACE HERE IS READ-ONLY (P4 EP-3, R-07 containment). This script holds a
`ReadOnlyCdpNavigator` [[cdp_readonly]]: it can fetch a document and observe it, and it has no
evaluate, command, click, type, select or upload method to call. It previously reached the TMS
through `cdp_session.evaluate("location.href=...")` — caller data interpolated into JavaScript, the
exact defect F2 exists to remove — with a `cdp_actuator.click()` fallback for opening a load's
detail page. Both are gone. Detail pages are reached only by FOLLOWING a link the loads list itself
published, which never runs the SPA's `onclick` handler.

The invoice WRITE is not this script's browser surface. Under P4/R-07 the live browser-write router
is removed: this script only READS the loads page and posts supervised Approve buttons. The tap's
effect (the raise_invoice write) runs through the DARK governed effect boundary
(effect_boundary.execute_invoice_write, checkpoint/witness/grant/claim), and live supervised writes
are enabled and validated at P12. `--autonomous` (unattended live writes) is therefore refused here.

Runs once, or continuously with --interval-seconds. Coordinated + idempotent:
- --lock-path: DEFER a cycle while the write-agent holds the shared browser (never navigate mid-write).
- --db: dedup so a still-un-invoiced load isn't re-proposed every cycle (recorded as invoice_proposal_posted).

Prereqs: the teammate running with --enable-operation-router + allowlist; a Chrome on
--remote-debugging-port=9222 logged into the TMS. Amounts are the loads' Totals (deterministic).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.cli_tenant import resolve_cli_tenant
from freight_recon.browser_lock import BrowserLock  # noqa: E402
from freight_recon.cdp_readonly import ReadOnlyCdpNavigator  # noqa: E402
from freight_recon.channels import load_delivery_config, slack_channel_for_route  # noqa: E402
from freight_recon.delivery_dispatch import SlackApiPoster  # noqa: E402
from freight_recon.operation_proposal import (  # noqa: E402
    attachment_labels_from_detail_observation,
    build_ready_to_bill_digest,
    has_pod_from_detail,
    loads_missing_pod,
    loads_unknown_pod,
    ready_to_bill_from_loads_table,
)
from freight_recon.review import ReviewRoute  # noqa: E402
from freight_recon.roi_ledger import receipt_from_result, render_operation_receipt  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_gmail_to_slack_dogfood import _delivery_signer  # noqa: E402

_INVOICE_PROPOSED_EVENT = "invoice_proposal_posted"
_INVOICE_BLOCKED_EVENT = "invoice_proposal_blocked"
_INVOICE_AUTOCOMMITTED_EVENT = "invoice_autocommitted"


def _raise_invoice_intent(row: dict) -> CommandIntent:
    """The raise_invoice intent for one ready-to-bill load. The approved amount is the load's Total
    (deterministic) — never a model-chosen figure, so the money fence holds even unattended."""
    return CommandIntent(
        kind=CommandKind.OPERATE,
        summary=f"Invoice {row.get('customer')} for {row.get('load_ref')}",
        params={
            "lane": "raise_invoice",
            "customer": row.get("customer"),
            "load_ref": row.get("load_ref"),
            "approved_amount": row.get("amount"),
        },
    )


def autonomy_split(rows, *, graduation, tenant: str = "default"):
    """Pure decision (unit-tested): split ready-to-bill rows into (autonomous, supervised) by the owner's
    graduation guardrails. A load runs UNATTENDED only if autonomy_allows says yes for its amount+party —
    over the ceiling, off the allowlist, or past the daily cap falls back to a supervised Approve button."""
    autonomous, supervised = [], []
    for row in rows:
        allowed = False
        if graduation is not None:
            allowed, _reason = graduation.autonomy_allows(
                tenant, "raise_invoice", amount=row.get("amount"), party=row.get("customer"),
            )
        (autonomous if allowed else supervised).append(row)
    return autonomous, supervised


def _buttons_for_rows(rows, *, signer, channel) -> list[dict]:
    """Build supervised 'Invoice [Approve & run]' buttons for a specific set of ready-to-bill rows."""
    from types import SimpleNamespace

    from freight_recon.operation_proposal import proposals_for_ready_to_bill
    loads = [SimpleNamespace(load_id=r["load_ref"], customer=r["customer"], delivery_date="ready") for r in rows]
    amounts = {r["load_ref"]: r["amount"] for r in rows}
    return proposals_for_ready_to_bill(
        loads, signer=signer, channel_id=channel, amount_for_load=lambda load: amounts.get(load.load_id),
    )


def _run_autonomous(rows, *, router, store, live, poster, channel) -> int:
    """Run graduated loads UNATTENDED through the money-fenced router, then receipt each to Slack. The
    router enforces the guardrails (ceiling/allowlist/daily-cap) and commit-once; a per-load dedup guard
    here stops a re-run in the window before the TMS status flips to Invoiced."""
    if not rows:
        return 0
    already = set()
    if store is not None:
        already = {e["payload"].get("load_ref") for e in store.security_events()
                   if e["event_type"] == _INVOICE_AUTOCOMMITTED_EVENT}
    committed = 0
    for row in rows:
        if row.get("load_ref") in already:
            continue
        if not live:
            print(f"   - AUTONOMOUS: would invoice {row.get('load_ref')} for {row.get('customer')} ${row.get('amount')}")
            continue
        result = router.run(_raise_invoice_intent(row), approve=None)  # fenced + capped + commit-once
        status = str(getattr(result, "status", "?"))
        if poster is not None:
            text = render_operation_receipt(receipt_from_result(result, amount=row.get("amount")))
            poster.post_message(channel=channel, payload={"text": text})
        if status.upper() == "DONE":
            committed += 1
            if store is not None:
                store.add_security_event(
                    _INVOICE_AUTOCOMMITTED_EVENT, actor="system",
                    payload={"load_ref": row.get("load_ref"), "channel_id": channel},
                )
        print(f"propose-ar-from-tms: autonomous invoice {row.get('load_ref')} -> {status}")
    return committed


def _cycle(*, act, signer, channel, loads_url, store, lock, live, poster, require_pod: bool = True, router=None) -> int:
    """One pass: defer if the browser is busy; else read /loads. Graduated loads run UNATTENDED through
    the router (when one is given); the rest get a supervised Approve button; POD-unproven loads get an
    exception. Falls back cleanly to propose-only when no router is wired."""
    if lock is not None and lock.is_busy():
        print("propose-ar-from-tms: browser busy (a write is in progress) — deferring this cycle.")
        return 0
    act.visit(loads_url)
    observation = act.observe()
    ready = ready_to_bill_from_loads_table(observation)
    if require_pod:
        ready = _resolve_unknown_pods_from_detail(act=act, rows=ready, loads_url=loads_url, list_observation=observation)
    billable = [r for r in ready if r.get("has_pod")] if require_pod else ready
    autonomous_rows, supervised_rows = [], billable
    if router is not None:
        autonomous_rows, supervised_rows = autonomy_split(billable, graduation=getattr(router, "graduation", None))
    # Autonomous first — each write holds the browser lock and may flip its load to Invoiced.
    autocommitted = _run_autonomous(autonomous_rows, router=router, store=store, live=live, poster=poster, channel=channel)
    blocked_rows = [r for r in ready if r.get("has_pod") is not True] if require_pod else []
    if store is not None:
        already = {
            e["payload"].get("load_ref")
            for e in store.security_events()
            if e["event_type"] == _INVOICE_PROPOSED_EVENT
        }
        supervised_rows = [r for r in supervised_rows if r.get("load_ref") not in already]
        already_blocked = {
            (e["payload"].get("load_ref"), e["payload"].get("reason"))
            for e in store.security_events()
            if e["event_type"] == _INVOICE_BLOCKED_EVENT
        }
        blocked_rows = [r for r in blocked_rows if (r.get("load_ref"), _pod_reason(r)) not in already_blocked]
    if not supervised_rows and not blocked_rows and not autonomous_rows:
        print("propose-ar-from-tms: no new ready-to-bill loads.")
        return 0
    # ONE digest instead of a wall of per-load posts (the owner narrative's summary ping). Capped per
    # cycle, so a first-run backlog trickles in digestible batches instead of flooding the channel.
    digest = build_ready_to_bill_digest(supervised_rows, signer=signer, channel_id=channel, blocked=blocked_rows)
    if not live:
        if digest is not None:
            print("   - DIGEST:", digest.get("text"))
            for r in supervised_rows[:10]:
                print(f"       • {r.get('load_ref')} {r.get('customer')} ${r.get('amount')}")
        print(f"(dry-run: {len(autonomous_rows)} autonomous, digest covers {len(digest.get('load_refs') or []) if digest else 0} "
              f"button(s) + {len(blocked_rows)} POD exception(s))")
        return 0
    posted = 0
    if digest is not None:
        result = poster.post_message(channel=digest["channel"], payload={"text": digest["text"], "blocks": digest["blocks"]})
        if getattr(result, "ok", False):
            shown = set(digest.get("load_refs") or [])
            posted = len(shown)
            if store is not None:
                for ref in shown:  # only the loads actually SHOWN are marked proposed; the rest follow next cycle
                    store.add_security_event(
                        _INVOICE_PROPOSED_EVENT, actor="system",
                        payload={"load_ref": ref, "channel_id": channel},
                    )
                for r in blocked_rows[:8]:
                    store.add_security_event(
                        _INVOICE_BLOCKED_EVENT, actor="system",
                        payload={"load_ref": r.get("load_ref"), "reason": _pod_reason(r), "channel_id": channel},
                    )
    print(
        f"propose-ar-from-tms: auto-invoiced {autocommitted}, digest posted with {posted} approve "
        f"button(s) + {min(len(blocked_rows), 8)} POD exception(s) to {channel}."
    )
    return posted


def _pod_reason(row: dict) -> str:
    return "missing_pod" if row.get("has_pod") is False else "unknown_pod"


def _resolve_unknown_pods_from_detail(*, act, rows: list[dict], loads_url: str, list_observation: dict | None) -> list[dict]:
    """For list-view POD unknowns, inspect the load detail/documents page. Fail closed on any read miss."""
    out: list[dict] = []
    for row in rows:
        if row.get("has_pod") is not None:
            out.append(row)
            continue
        resolved = _read_pod_from_detail(act=act, row=row, loads_url=loads_url, list_observation=list_observation)
        out.append({**row, "has_pod": resolved})
    return out


def _read_pod_from_detail(*, act, row: dict, loads_url: str, list_observation: dict | None) -> bool | None:
    """Open a load's detail page and read whether a POD is attached. FAILS CLOSED to None.

    The detail page is reached ONLY through a PROVENANCE RECORD the loads list itself supports
    (P4 EP-3): the anchor contained by the one row whose cells carry this load's identifier, bound
    to that load by exact link text or an exact path segment, on an observational route, shaped like
    a plain document link — and re-derived from the live page at follow time. See
    `cdp_readonly.select_load_detail_link`.

    That is deliberately stricter than "a same-origin link the page published", which is NOT
    inherently read-only: legacy TMS systems expose state-changing GET routes, and Rails-style
    `<a href="/loads/101" data-method="delete">` is a link by tag and a DELETE by behaviour. A
    generic follower of any observed anchor would reach logout, delete, approve and pay routes.

    There is also no click fallback: a click dispatches the SPA's `onclick` handler, which can POST
    an invoice while being no kind of form submit target, so no structural test on the element could
    have made that fallback safe. A load whose detail document cannot be bound simply stays
    POD-unknown, and an unknown POD blocks the money button — the safe direction.
    """
    load_ref = str(row.get("load_ref") or "").strip()
    if not load_ref:
        return None
    try:
        link = act.detail_link_for_load(load_ref)
        if link is None:
            return None  # nothing provenance-bound to follow; not a billing greenlight
        if not bool(act.follow(link)):
            return None
        labels = attachment_labels_from_detail_observation(act.observe())
        return has_pod_from_detail(labels, page_readable=True)
    except Exception:  # noqa: BLE001 - a detail-read failure is not a billing greenlight
        return None
    finally:
        try:
            act.visit(loads_url)
        except Exception:  # noqa: BLE001
            pass


def _pod_block_messages(observation: dict | None, *, channel: str) -> list[dict]:
    messages: list[dict] = []
    for row in loads_missing_pod(observation):
        messages.append(_pod_block_message(row, channel=channel, reason="missing_pod"))
    for row in loads_unknown_pod(observation):
        messages.append(_pod_block_message(row, channel=channel, reason="unknown_pod"))
    return messages


def _pod_block_messages_for_rows(rows: list[dict], *, channel: str) -> list[dict]:
    messages: list[dict] = []
    for row in rows:
        if row.get("has_pod") is False:
            messages.append(_pod_block_message(row, channel=channel, reason="missing_pod"))
        elif row.get("has_pod") is None:
            messages.append(_pod_block_message(row, channel=channel, reason="unknown_pod"))
    return messages


def _pod_block_message(row: dict, *, channel: str, reason: str) -> dict:
    load_ref = row.get("load_ref")
    customer = row.get("customer") or "customer"
    label = "Missing POD" if reason == "missing_pod" else "POD status unknown"
    text = f"{label}: {load_ref} for {customer} is delivered but not ready for customer invoicing."
    return {
        "channel": channel,
        "text": text,
        "load_ref": load_ref,
        "reason": reason,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{label}*\n{text}"}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "No money button was posted. Attach or verify the POD first, then rerun Neyma.",
                    }
                ],
            },
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client-config", required=True)
    p.add_argument("--cdp-url", default="http://localhost:9222")
    p.add_argument("--url-filter", default="truckingoffice")
    p.add_argument("--loads-url", default="https://secure.truckingoffice.com/loads")
    p.add_argument("--allow-local-dev-secret", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="read + build proposals but do not post")
    p.add_argument("--no-require-pod", action="store_true", help="unsafe/dev only: allow AR invoice proposals without proven POD")
    p.add_argument("--db", default=None, help="WorkflowStore path for dedup (don't re-propose a load)")
    p.add_argument("--lock-path", default=None, help="browser-busy marker to defer to an in-progress write")
    p.add_argument("--interval-seconds", type=int, default=0, help="0 = run once; >0 = loop on this interval")
    p.add_argument("--autonomous", action="store_true", help="CONTAINED under P4/R-07: the live browser-write router is removed, so this is refused. Supervised Approve buttons are still posted; the write runs through the dark governed effect boundary (live supervised writes are P12).")
    p.add_argument("--operation-model", default=os.getenv("NEYMA_OPERATION_MODEL", "gpt-5.5"), help="model for the autonomous write agent")
    p.add_argument("--operation-max-steps", type=int, default=int(os.getenv("NEYMA_OPERATION_MAX_STEPS", "40")))
    args = p.parse_args()
    if args.autonomous:
        # P4 EP-1 ADAPTER CONTAINMENT (R-07). The unattended invoice write used to run through the same
        # live browser-agent OperationRouter the callback used (build_agent -> CdpActuator). That
        # construction site is DELETED, not disabled: the only external-write path in the system is now
        # the DARK governed effect boundary (effect_boundary.execute_invoice_write), and live supervised
        # writes are enabled and validated at P12. This script's READ + supervised-proposal surface is
        # unaffected; only the unattended live write is refused.
        p.error(
            "--autonomous is contained under P4/R-07: the live browser-write router is removed. This "
            "script now only READS the TMS and posts supervised Approve buttons; the invoice write runs "
            "through the dark governed effect boundary, and live supervised writes are enabled at P12.")

    config = load_delivery_config(args.client_config)
    if config is None or config.slack is None:
        p.error("client-config has no Slack config")
    channel = slack_channel_for_route(config.slack, ReviewRoute.CHANNEL_POST)
    signer = _delivery_signer(args.client_config, args.allow_local_dev_secret)
    live = not args.dry_run
    poster = None
    if live:
        token = os.environ.get(config.slack.bot_token_env or "")
        if not token:
            p.error(f"no Slack bot token in env var {config.slack.bot_token_env!r}")
        poster = SlackApiPoster(token)
    lock = BrowserLock(args.lock_path) if args.lock_path else None

    # P4 EP-1 ADAPTER CONTAINMENT (R-07): no live-write router is constructed here. `--autonomous` is
    # refused above, so this always runs router-free — READ the loads page and post supervised Approve
    # buttons. The invoice WRITE (the tap's effect) is the dark governed route; live writes are P12.
    router = None

    # F-02: the navigation origin is pinned from the OPERATOR-CONFIGURED --loads-url, not inferred
    # from anything the TMS page publishes and not left to the optional --url-filter (which defaults
    # to empty). A page that publishes a cross-origin row link is refused by the parsed-origin
    # policy even when no filter is configured at all.
    with ReadOnlyCdpNavigator(cdp_url=args.cdp_url, url_filter=args.url_filter or None,
                              allowed_origin=args.loads_url) as act:
        while True:
            store = WorkflowStore(args.db, tenant=resolve_cli_tenant(tenant=getattr(args, "tenant", None), client_config=getattr(args, "client_config", None), context="propose_ar_from_tms.py")) if args.db else None
            try:
                _cycle(
                    act=act, signer=signer, channel=channel, loads_url=args.loads_url,
                    store=store, lock=lock, live=live, poster=poster,
                    require_pod=not args.no_require_pod, router=router,
                )
            finally:
                if store is not None:
                    store.close()
            if args.interval_seconds <= 0:
                break
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
