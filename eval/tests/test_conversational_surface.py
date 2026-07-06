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
