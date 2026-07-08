"""The conversational assistant surface: a plain-English owner message -> answer or gated proposal.

This is what makes Neyma feel like a teammate: the owner replies to a notification in natural language
and it acts, through the SAME interpreter + money gates the /neyma slash path uses.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.action_callback import route_conversational_message  # noqa: E402
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.operation_router import OperationRouter, freight_lanes  # noqa: E402
from freight_recon.ops_control import OpsControl  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

_SIGNER = DeliverySigner(b"bridge-secret")


def _router():
    return OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None)


def _config(*, nl_completer=None):
    return SimpleNamespace(
        status_file=None, operation_router=_router(), signer=_SIGNER, nl_completer=nl_completer,
    )


def _ctx(tmp_path):
    return OpsControl(tmp_path / "ops.json"), WorkflowStore(str(tmp_path / "w.sqlite3"))


def test_read_command_is_answered_immediately_no_gate(tmp_path):
    ops, store = _ctx(tmp_path)
    store.add_security_event("learned", actor="owner", payload={})  # any state
    out = route_conversational_message(
        "know", actor="U1", channel_id="C", config=_config(), ops_control=ops, store=store
    )
    assert "text" in out and "proposal" not in out          # a read -> immediate answer
    assert not out["text"].startswith("Commands:")
    store.close()


def test_operation_command_becomes_a_gated_proposal_with_button(tmp_path):
    ops, store = _ctx(tmp_path)
    out = route_conversational_message(
        "record payable to Iron Horse for LD-5 amount 1421.00",
        actor="U1", channel_id="C", config=_config(), ops_control=ops, store=store,
    )
    assert "proposal" in out                                 # a money action -> a proposal, never auto-run
    assert out["proposal"].get("blocks")                     # carries the Approve button in blocks
    assert "record_payable" in out["proposal"]["text"]
    store.close()


def test_operation_without_amount_asks_for_one_never_guesses(tmp_path):
    ops, store = _ctx(tmp_path)
    out = route_conversational_message(
        "invoice Acme for LD-9",                             # no amount in the message
        actor="U1", channel_id="C", config=_config(), ops_control=ops, store=store,
    )
    # the fence holds: it asks for an approved amount rather than fabricating one
    text = out.get("proposal", {}).get("text", "") + out.get("text", "")
    assert "amount" in text.lower()
    store.close()


def test_unrecognized_message_with_no_nl_falls_back_to_help(tmp_path):
    ops, store = _ctx(tmp_path)
    out = route_conversational_message(
        "hey what's up", actor="U1", channel_id="C", config=_config(nl_completer=None),
        ops_control=ops, store=store,
    )
    # a conversational miss gets a short human reply, not a command dump (live-found trust-killer)
    assert "text" in out and "didn't quite get that" in out["text"]
    out2 = route_conversational_message(
        "help", actor="U1", channel_id="C", config=_config(nl_completer=None), ops_control=ops, store=store,
    )
    assert out2["text"].startswith("Commands:")                    # the full list only when asked
    store.close()


def test_nl_routing_reads_when_the_model_classifies_a_query(tmp_path):
    ops, store = _ctx(tmp_path)
    # a stub NL completer that routes any plain words to the 'know' read
    def fake_complete(_prompt):
        return '{"action": "read", "read": "know"}'
    out = route_conversational_message(
        "how are we doing today", actor="U1", channel_id="C",
        config=_config(nl_completer=fake_complete), ops_control=ops, store=store,
    )
    assert "text" in out and not out["text"].startswith("Commands:")
    store.close()


def test_bill_load_resolves_amount_from_tms_so_owner_neednt_type_it(tmp_path):
    # "bill load 105" with no amount: the resolver fetches load 105's Total from the TMS and the
    # proposal is built at that deterministic amount — the owner doesn't have to type it.
    ops, store = _ctx(tmp_path)
    cfg = _config()
    cfg.load_amount_resolver = lambda ref: "2400.00" if ref == "105" else None
    out = route_conversational_message(
        "bill load 105", actor="U1", channel_id="C", config=cfg, ops_control=ops, store=store
    )
    assert "proposal" in out and "2400.00" in out["proposal"]["text"]   # resolved, not asked
    store.close()


def test_extract_load_ref_variants():
    from freight_recon.action_callback import _extract_load_ref
    assert _extract_load_ref("bill load 105") == "105"
    assert _extract_load_ref("invoice LD-4471 please") == "LD-4471"
    assert _extract_load_ref("handle order #88") == "88"
    assert _extract_load_ref("what's outstanding") is None


def test_aging_query_answers_with_a_live_receivables_digest(tmp_path):
    # "who owes us money?" -> a live aged-AR digest (a read), not the workflow 'unresolved' list.
    ops, store = _ctx(tmp_path)
    cfg = _config()
    cfg.receivables_reader = lambda: [
        {"invoice": "560003", "customer": "Maple Leaf Transport", "total": "3634.50",
         "balance_due": "184.50", "invoiced_on": "2020-01-01"},   # long overdue
    ]
    cfg.ar_aging_min_days = 1
    out = route_conversational_message(
        "who owes us money?", actor="U1", channel_id="C", config=cfg, ops_control=ops, store=store
    )
    assert "text" in out and "#560003 Maple Leaf Transport" in out["text"]
    assert "outstanding" in out["text"] and "past due" not in out["text"]
    store.close()


def test_aging_query_does_not_false_clear_when_tms_read_fails(tmp_path):
    ops, store = _ctx(tmp_path)
    cfg = _config()
    cfg.receivables_reader = lambda: None
    out = route_conversational_message(
        "who owes us money?", actor="U1", channel_id="C", config=cfg, ops_control=ops, store=store
    )
    assert "couldn't read the invoices" in out["text"]
    assert "No outstanding receivables" not in out["text"]
    store.close()


def test_resume_signal_distinguishes_continue_from_a_new_question():
    # The bug we shipped: a question in a thread with a pending op got hijacked into a resume.
    from freight_recon.action_callback import _is_resume_signal
    for yes in ["submit", "go ahead", "yes", "approve", "do it", "send it", "try again", "confirm", "yep run it"]:
        assert _is_resume_signal(yes), yes
    for no in ["who owes us money?", "what have you done today", "what's our aging",
               "bill load 105", "how did we do", "status", "resume tms writes"]:
        assert not _is_resume_signal(no), no


def test_batch_background_run_fences_each_item_and_posts_one_consolidated_receipt(tmp_path):
    # [Approve all N]: every item runs through the router with ITS signed amount (commit authorized by
    # the tap); one consolidated receipt; per-item audit events; one bad item doesn't sink the batch.
    import threading as _threading

    from freight_recon.action_callback import _start_batch_background_run
    from freight_recon.operation_router import OperationResult

    ran = []

    class _Router:
        def run(self, intent, approve=None):
            ran.append(dict(intent.params))
            if intent.params["load_ref"] == "104":
                raise RuntimeError("browser hiccup")          # one failure, contained
            return OperationResult("DONE", "raise_invoice", f"invoice for {intent.params['load_ref']} saved", [])

    posts = []

    def poster(payload):
        posts.append(payload)

    store = WorkflowStore(str(tmp_path / "w.sqlite3")); store.close()
    batch = {"action_id": "batch1", "lane": "raise_invoice", "items": [
        {"load_ref": "103", "customer": "Acme", "amount": "2500.00"},
        {"load_ref": "104", "customer": "Echo", "amount": "1200.00"},
    ]}
    t = _start_batch_background_run(db_path=str(tmp_path / "w.sqlite3"), router=_Router(), batch=batch,
                                    actor="U1", channel_id="C", thread_ts="1.1", poster=poster)
    t.join(timeout=10)
    assert [p["load_ref"] for p in ran] == ["103", "104"]
    assert all(p["approved_amount"] in ("2500.00", "1200.00") and p["commit"] is True for p in ran)
    assert len(posts) == 1                                    # ONE consolidated receipt
    text = posts[0]["text"]
    assert "1/2 invoiced" in text and "103" in text and "104" in text and "FAILED" in text
    s = WorkflowStore(str(tmp_path / "w.sqlite3"))
    try:
        events = [e for e in s.security_events() if e["event_type"] == "slack_operation_applied"]
        assert len(events) == 2                               # per-item audit trail
        assert all(e["payload"].get("batch_action_id") == "batch1" for e in events)
    finally:
        s.close()


def test_whats_happening_brief_composes_loads_ready_and_ar(tmp_path):
    # "what's happening?" -> the pocket snapshot: loads by status + ready-to-bill + outstanding AR.
    ops, store = _ctx(tmp_path)
    cfg = _config()
    cfg.tms_brief_reader = lambda: {
        "status_counts": {"Delivered": 2, "Dispatched": 1, "Invoiced": 3},
        "ready": [{"load_ref": "103", "customer": "Acme", "amount": "2500.00"}],
        "receivables": [{"invoice": "560009", "customer": "Coyote", "total": "2000.00",
                         "balance_due": "1950.00", "invoiced_on": "2020-01-01"}],
    }
    out = route_conversational_message(
        "what's happening?", actor="U1", channel_id="C", config=cfg, ops_control=ops, store=store
    )
    text = out["text"]
    assert "2 Delivered" in text and "3 Invoiced" in text
    assert "Ready to bill: 1 load ($2,500.00)" in text
    assert "$1,950.00" in text                       # outstanding AR total
    store.close()


def test_whats_happening_brief_never_fakes_an_all_clear(tmp_path):
    ops, store = _ctx(tmp_path)
    cfg = _config()
    cfg.tms_brief_reader = lambda: None              # busy/unreadable TMS
    out = route_conversational_message(
        "what's happening", actor="U1", channel_id="C", config=cfg, ops_control=ops, store=store
    )
    assert "couldn't read the TMS" in out["text"]
    store.close()


def test_who_owes_us_the_most_ranks_by_customer(tmp_path):
    ops, store = _ctx(tmp_path)
    cfg = _config()
    cfg.receivables_reader = lambda: [
        {"invoice": "1", "customer": "Global Tranz", "balance_due": "18400.00", "total": "18400.00",
         "invoiced_on": "2020-01-01"},
        {"invoice": "2", "customer": "Chiquita Brands", "balance_due": "12000.00", "total": "12000.00",
         "invoiced_on": "2020-01-02"},
    ]
    out = route_conversational_message(
        "who owes us the most?", actor="U1", channel_id="C", config=cfg, ops_control=ops, store=store
    )
    lines = out["text"].splitlines()
    assert "Who owes us the most" in lines[0]
    assert "Global Tranz" in lines[1] and "$18,400.00" in lines[1]   # biggest first
    store.close()


def test_typed_operation_binds_the_named_record_and_asks_when_missing(tmp_path):
    # LIVE-FOUND: owner said "raise_invoice 100" and the agent drove load 101 — the proposal never
    # carried the record. The named ref must bind into the intent; a record lane with no ref must ASK.
    from freight_recon.action_callback import _build_operation_command_proposal, _verify_operation_approval_value
    from freight_recon.operation_router import OperationRouter, freight_lanes

    router = OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None)
    msg = _build_operation_command_proposal("raise_invoice 100 amount 2850.00",
                                            signer=_SIGNER, router=router, channel_id="C")
    btn = next(b for b in msg["blocks"] if b["type"] == "actions")["elements"][0]
    approval = _verify_operation_approval_value(btn["value"], _SIGNER)
    assert approval.intent.params["load_ref"] == "100"             # anchored to what the owner NAMED
    assert approval.intent.params["lane"] == "raise_invoice"

    ask = _build_operation_command_proposal("invoice the customer amount 500.00",
                                            signer=_SIGNER, router=router, channel_id="C")
    assert "which load/invoice" in ask["text"]                     # no ref -> ask, never freelance


def test_non_money_lane_proposal_needs_no_amount(tmp_path):
    # LIVE-FOUND: "…why are you attaching this to 101?" was answered with "I need an approved amount"
    # for file_document — a non-money lane must propose without demanding a dollar figure.
    from freight_recon.action_callback import _build_operation_command_proposal
    from freight_recon.operation_router import OperationRouter, freight_lanes

    router = OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None)
    msg = _build_operation_command_proposal("attach the POD to load 101",
                                            signer=_SIGNER, router=router, channel_id="C")
    assert msg.get("blocks"), msg                                  # a real proposal, not an amount nag
    assert "need an approved amount" not in (msg.get("text") or "")


def test_challenge_in_a_pending_op_thread_gets_op_context_not_a_new_lane(tmp_path):
    # LIVE-FOUND: the owner's complaint in the escalated thread was lane-matched into file_document.
    from freight_recon.action_callback import _render_pending_op_context

    pending = {"lane": "raise_invoice", "status": "ESCALATED",
               "summary": "Invoice the customer for 100",
               "note": "blocked: POD/BOL attachment file is required but no file is available to upload",
               "steps": [{"action": "CLICK", "target": "101", "ok": True},
                         {"action": "CLICK", "target": "Attach BOL", "ok": True}]}
    out = _render_pending_op_context(pending, "did i not say 100 why are you attaching this to 101?")
    assert "Invoice the customer for 100" in out and "Clicked 101" in out
    assert "fresh request" in out                                   # tells the owner how to redirect
    assert "amount 2850.00" not in out                              # never echoes garbage examples
