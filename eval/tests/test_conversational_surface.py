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
    assert "text" in out and out["text"].startswith("Commands:")   # graceful help, no action
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
    assert "text" in out and "#560003 Maple Leaf Transport" in out["text"] and "past due" in out["text"]
    store.close()


def test_resume_signal_distinguishes_continue_from_a_new_question():
    # The bug we shipped: a question in a thread with a pending op got hijacked into a resume.
    from freight_recon.action_callback import _is_resume_signal
    for yes in ["submit", "go ahead", "yes", "approve", "do it", "send it", "try again", "confirm", "yep run it"]:
        assert _is_resume_signal(yes), yes
    for no in ["who owes us money?", "what have you done today", "what's our aging",
               "bill load 105", "how did we do", "status", "resume tms writes"]:
        assert not _is_resume_signal(no), no
