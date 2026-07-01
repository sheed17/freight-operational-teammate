"""Tests for natural-language routing of /neyma — owner talks, we map to a read or a gated operation."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.nl_command import interpret_slash  # noqa: E402


def _llm(mapping):
    def complete(prompt):
        # match only the owner's MESSAGE line, not the prompt template (which names all the read types)
        line = prompt.split("MESSAGE:", 1)[-1].split("\n", 1)[0].lower()
        for needle, out in mapping.items():
            if needle.lower() in line:
                return json.dumps(out)
        return json.dumps({"action": "unknown"})
    return complete


def test_read_queries_route_to_the_right_read():
    c = _llm({
        "how much have we saved": {"action": "read", "read": "roi"},
        "what's outstanding": {"action": "read", "read": "unresolved"},
        "what are you doing": {"action": "read", "read": "status"},
    })
    assert interpret_slash("how much have we saved this week?", complete=c) == {"read": "roi"}
    # 'unresolved' is normalized to the command handle_ops_command understands
    assert interpret_slash("what's outstanding over 30 days?", complete=c) == {"read": "show unresolved"}
    assert interpret_slash("what are you doing right now?", complete=c) == {"read": "status"}


def test_operate_requests_route_to_operate():
    c = _llm({"invoice the Northbound load": {"action": "operate", "request": "invoice the Northbound load"}})
    assert interpret_slash("invoice the Northbound load", complete=c) == {"operate": "invoice the Northbound load"}


def test_unknown_and_empty_and_bad_model_fall_back_to_help():
    assert interpret_slash("blah blah nonsense", complete=_llm({})) == {}          # model says unknown
    assert interpret_slash("", complete=_llm({})) == {}                             # empty
    assert interpret_slash("x", complete=lambda p: "not json at all") == {}         # model junk -> {}
    # a read the handler doesn't know is dropped (never fabricate a command)
    assert interpret_slash("x", complete=lambda p: json.dumps({"action": "read", "read": "delete_everything"})) == {}
