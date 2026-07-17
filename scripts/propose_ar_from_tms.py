"""Read ready-to-bill loads from the LIVE TMS and post AR invoice Approve buttons to Slack.

The AR trigger, real-TMS sourced (vs the synthetic corpus): navigate the human-logged-in TMS to its
loads page, read which loads are delivered-but-not-invoiced and their Total, and post one signed
"Invoice [Approve & run]" button per load at that Total. A tap then drives the PROVEN raise_invoice
write — so the proposed load_ref always matches a writable record.

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
from freight_recon.cdp_actuator import CdpActuator  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
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
from run_action_callback_server import _build_live_operation_router  # noqa: E402
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
    act.session.evaluate(f"location.href={loads_url!r}")
    time.sleep(2.5)
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
    load_ref = str(row.get("load_ref") or "").strip()
    if not load_ref:
        return None
    page_readable = False
    try:
        target = _detail_nav_target(list_observation, load_ref)
        if target and hasattr(act, "navigate"):
            page_readable = bool(act.navigate(target))
        elif hasattr(act, "click"):
            page_readable = bool(act.click(load_ref))
        if not page_readable:
            return None
        labels = attachment_labels_from_detail_observation(act.observe())
        return has_pod_from_detail(labels, page_readable=True)
    except Exception:  # noqa: BLE001 - a detail-read failure is not a billing greenlight
        return None
    finally:
        try:
            if hasattr(act, "navigate"):
                act.navigate(loads_url)
            else:
                act.session.evaluate(f"location.href={loads_url!r}")
        except Exception:  # noqa: BLE001
            pass


def _detail_nav_target(observation: dict | None, load_ref: str) -> str | None:
    for nav in (observation or {}).get("nav") or []:
        text = str(nav.get("text") or "")
        url = str(nav.get("url") or "")
        hay = f"{text} {url}"
        if load_ref and load_ref in hay:
            return url
    return None


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
    p.add_argument("--autonomous", action="store_true", help="run GRADUATED loads unattended (money-fenced + capped) instead of only posting a button; ungraduated/over-cap loads still get a button")
    p.add_argument("--operation-model", default=os.getenv("NEYMA_OPERATION_MODEL", "gpt-5.5"), help="model for the autonomous write agent")
    p.add_argument("--operation-max-steps", type=int, default=int(os.getenv("NEYMA_OPERATION_MAX_STEPS", "40")))
    args = p.parse_args()
    if args.autonomous and not args.db:
        p.error("--autonomous requires --db (graduation policy + commit-once + autonomous-run cap live in the workspace DB)")

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

    from pathlib import Path as _Path
    router = None
    if args.autonomous:
        # The SAME money-fenced router the Slack callback uses — graduation, commit-once, verify-by-
        # readback, browser-lock, all identical. Autonomy just means we call it with approve=None.
        router = _build_live_operation_router(
            cdp_url=args.cdp_url, url_filter=args.url_filter or None,
            model=args.operation_model, max_steps=args.operation_max_steps,
            workspace=_Path(args.db).parent, db_path=_Path(args.db),
        )

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as session:
        act = CdpActuator(session)
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
