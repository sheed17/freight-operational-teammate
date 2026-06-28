"""Tests for the Slack two-way delegate: authorization/injection boundary + intent routing."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.slack_delegate import (  # noqa: E402
    CommandIntent,
    CommandKind,
    authorize_command,
    handle_owner_command,
    interpret_command,
)

OWNER = "U_OWNER"
CHAN = "C_OPS"


def _route(text, intent, **over):
    kw = dict(
        user_id=OWNER, channel_id=CHAN, allowed_users={OWNER}, allowed_channel=CHAN,
        interpret=lambda t: intent,
        on_query=lambda i: "QUERY-ANSWER",
        on_operate=lambda i: "PROPOSED-PLAN",
        on_control=lambda i: "CONTROL-DONE",
    )
    kw.update(over)
    return handle_owner_command(text, **kw)


# ----- authorization / injection boundary -----

def test_authorize_only_owner_in_authorized_channel():
    assert authorize_command(OWNER, CHAN, allowed_users={OWNER}, allowed_channel=CHAN)[0]
    assert not authorize_command("U_STRANGER", CHAN, allowed_users={OWNER}, allowed_channel=CHAN)[0]
    assert not authorize_command(OWNER, "C_RANDOM", allowed_users={OWNER}, allowed_channel=CHAN)[0]


def test_authorize_fails_closed_when_nothing_configured():
    ok, reason = authorize_command(OWNER, CHAN, allowed_users=set(), allowed_channel=None)
    assert not ok and "fail-closed" in reason


def test_unauthorized_command_is_refused_without_interpreting():
    called = {"interpret": 0}

    def interp(t):
        called["interpret"] += 1
        return CommandIntent(CommandKind.OPERATE)

    resp = _route("pay everything", CommandIntent(CommandKind.OPERATE), user_id="U_STRANGER", interpret=interp)
    assert not resp.authorized
    assert called["interpret"] == 0  # a non-owner command never even reaches interpretation


# ----- routing -----

def test_query_is_answered_immediately():
    resp = _route("what's outstanding over 30 days?", CommandIntent(CommandKind.QUERY))
    assert resp.authorized and resp.kind == CommandKind.QUERY
    assert resp.text == "QUERY-ANSWER" and not resp.requires_approval


def test_operate_is_proposed_and_requires_approval_not_auto_executed():
    executed = {"ran": False}

    def on_operate(intent):
        # The operate handler PLANS/proposes; it must not perform the consequential action here.
        return "Here's what I'll do: create 3 customer invoices. Approve?"

    resp = _route("invoice today's delivered loads", CommandIntent(CommandKind.OPERATE), on_operate=on_operate)
    assert resp.kind == CommandKind.OPERATE
    assert resp.requires_approval is True            # consequential -> gated, never auto-run from chat
    assert "Approve" in resp.text
    assert executed["ran"] is False


def test_control_routes_to_control_handler():
    resp = _route("pause tms writes", CommandIntent(CommandKind.CONTROL))
    assert resp.kind == CommandKind.CONTROL and resp.text == "CONTROL-DONE"


def test_unknown_asks_for_clarification():
    resp = _route("asdf qwer", CommandIntent(CommandKind.UNKNOWN))
    assert resp.kind == CommandKind.UNKNOWN and not resp.requires_approval
    assert "didn't understand" in resp.text.lower()


# ----- intent interpretation (injectable LLM) -----

def test_interpret_maps_kinds_and_handles_bad_json():
    op = interpret_command("dispute the detention on LD-560004",
                           complete=lambda p: json.dumps({"kind": "OPERATE", "summary": "dispute detention"}))
    assert op.kind == CommandKind.OPERATE and "dispute" in op.summary

    q = interpret_command("what needs review?", complete=lambda p: '```json\n{"kind":"QUERY"}\n```')
    assert q.kind == CommandKind.QUERY

    bad = interpret_command("???", complete=lambda p: "not json at all")
    assert bad.kind == CommandKind.UNKNOWN  # unparseable -> UNKNOWN, never a guessed action


# ----- delegate -> Brain bridge: OPERATE command becomes a gated plan proposal -----

def test_propose_operation_plans_and_renders_approval_proposal():
    import json as _json
    from freight_recon.slack_delegate import propose_operation
    from freight_recon.operator_brain import observe

    class S:
        def navigate(self, u): pass
        def evaluate(self, e): return {"url": "u", "nav": [{"text": "Invoices", "href": "/order/invoices"}], "headings": [], "has_form": False}

    obs = observe(S(), "u")
    plan_json = _json.dumps({"steps": [
        {"action": "NAVIGATE", "target": "/orders/new"},
        {"action": "RESOLVE_CUSTOMER", "target": "Acme"},
        {"action": "FILL_AND_SUBMIT", "target": "/orders/new"},
    ]})
    plan, text = propose_operation(CommandIntent(CommandKind.OPERATE, summary="invoice the Acme load"),
                                   obs, complete=lambda _p: plan_json)
    assert len(plan.steps) == 3
    assert "needs your approval" in text          # the consequential step is flagged for the human
    assert "money gates" in text                   # approval routes through the gates
    assert "invoice the Acme load" in text


def test_propose_operation_surfaces_escalation_when_blocked():
    import json as _json
    from freight_recon.slack_delegate import propose_operation
    from freight_recon.operator_brain import observe

    class S:
        def navigate(self, u): pass
        def evaluate(self, e): return {"url": "u", "nav": [], "headings": [], "has_form": False}

    plan, text = propose_operation(
        CommandIntent(CommandKind.OPERATE, summary="do the impossible"),
        observe(S(), "u"),
        complete=lambda _p: _json.dumps({"steps": [{"action": "ESCALATE", "target": "no invoice capability"}]}),
    )
    assert "can't complete this safely" in text
    assert not plan.consequential_steps()
