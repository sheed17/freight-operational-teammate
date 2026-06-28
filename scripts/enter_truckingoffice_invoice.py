"""Drive ONE approved run through the gated spine into a REAL TruckingOffice invoice.

This is the first fully autonomous, gated, verified write against the live TMS. It reuses the exact
``enter_approved_payable`` path the mock uses — so approved-amount binding, idempotency, the state
machine, audit, and deterministic verify-by-readback all apply unchanged — but the ledger is the real
:class:`TruckingOfficeInvoiceLedger` driving Chrome over CDP.

Safety: the real-host write is refused unless ``--acknowledge-real-write`` is passed (the explicit,
audited "go live" switch). Nothing here decides an amount — it writes the human-approved figure and
verifies it by reading the /invoices ledger back.

By default it self-seeds a scratch approved run from the synthetic corpus so the proof is isolated and
repeatable; point ``--db``/``--run-id`` at a real run to drive that instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import (  # noqa: E402
    ReviewActionRequest,
    ReviewDecision,
    _decision_for_option,
    apply_review_action,
)
from freight_recon.tms_write import ExecutionStatusUpdate, approved_amount_for_run, enter_approved_payable  # noqa: E402
from freight_recon.truckingoffice_write import (  # noqa: E402
    DEFAULT_BASE_URL,
    TruckingOfficeInvoiceLedger,
    find_or_create_customer,
)
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "synthetic_corpus"


def seed_approved_run(store: WorkflowStore, corpus_dir: Path, load_id: str) -> int:
    """Seed a scratch APPROVED run from the corpus and approve it at its full invoice amount."""
    raw = json.loads((corpus_dir / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    seen: set[tuple[str, str]] = set()
    for load in loads:
        process_load_packet(
            store, load, primary_document_path=corpus_dir / load.documents["carrier_invoice"], seen_invoice_keys=seen
        )
    run = next(r for r in store.list_runs() if r.load_id == load_id)
    load = next(l for l in loads if l.load_id == load_id)
    payload = build_review_payload(run, load, age_hours=0)
    record_review_payload(store, payload)
    money_decisions = {ReviewDecision.APPROVE_FULL_AMOUNT, ReviewDecision.APPROVE_EXPECTED_AMOUNT}
    opt = next(
        (o for o in payload.action_options if _decision_for_option(o) in money_decisions and o.amount is not None),
        None,
    )
    if opt is None:
        raise SystemExit(f"load {load_id} has no money-approval option to seed; try a different --seed-load")
    apply_review_action(
        store,
        ReviewActionRequest(run_id=run.id, decision=_decision_for_option(opt), amount=Decimal(str(opt.amount))),
    )
    return run.id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "active_workspace" / "truckingoffice_demo.sqlite3"))
    parser.add_argument("--run-id", type=int, default=None, help="drive an existing approved run instead of seeding")
    parser.add_argument("--seed-load", default="LD-560007", help="corpus load to seed when --run-id is omitted")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--cdp-url", default="http://localhost:9222", help="CDP URL of the human-logged-in Chrome")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--acknowledge-real-write",
        action="store_true",
        help="REQUIRED to write the real TMS: the explicit, audited human acknowledgement to go live",
    )
    args = parser.parse_args()

    store = WorkflowStore(args.db)
    run_id = args.run_id if args.run_id is not None else seed_approved_run(store, Path(args.corpus), args.seed_load)
    run = store.get_run(run_id)
    if run.state != WorkflowState.APPROVED:
        store.close()
        parser.error(f"run {run_id} is {run.state.value}, not APPROVED")
    approved = approved_amount_for_run(store, run_id)
    print(f"run {run_id}: load={run.load_id} carrier={run.carrier!r} approved_amount={approved}")

    def on_status(u: ExecutionStatusUpdate) -> None:
        print(f"  [{u.phase.value}] {u.message}")

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter="truckingoffice") as session:
        ledger = TruckingOfficeInvoiceLedger(
            session=session,
            customer_resolver=lambda name: find_or_create_customer(session, name, base_url=args.base_url),
            base_url=args.base_url,
            approved_write_hosts=["secure.truckingoffice.com"],
            real_write_acknowledged=args.acknowledge_real_write,
        )
        outcome = enter_approved_payable(store, ledger, run_id, amount=approved, on_status=on_status)
    store.close()
    print(json.dumps(outcome.model_dump(mode="json"), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
