"""F2 — THE READ-ONLY CDP SURFACE IS READ-ONLY BY MECHANISM (P4 containment, R-07 scope).

The P4 checkpoint recorded F2 and deferred it: `cdp_session` exposes `evaluate()`, `command()` and
`set_file_input()`, so treating it as a "read substrate" was unsound — a tool that only wanted to
LOOK at a TMS still held actuation. F2 is closed by `freight_recon.cdp_readonly`, and these guards
are what make the closure a mechanism instead of a claim.

Everything here is browser-free ON PURPOSE. The clean-clone gate installs declared dependencies
into a fresh venv and has no Chrome; a guard that needed a browser would have to be skipped there,
and a skipped guard is silence, not a pass. The live-browser proof is a separate, runnable artifact
(`scripts/verify_readonly_cdp.py`) whose observations are recorded as checkpoint evidence.

The three barriers under test, each independently sufficient to defeat a different attack:

  1. NO MUTATION API EXISTS. `ReadOnlyCdpObserver` has no method by which a mutation can be
     expressed. Tested by attribute surface, not by reading the source.
  2. CALLER DATA IS NEVER CODE. Targets travel as `Runtime.callFunctionOn` `arguments`. Tested by
     AST over the dispatch path: no f-string, no concatenation, no formatting.
  3. THE CHANNEL REFUSES ANYTHING ELSE. Method allowlist plus exact-value script registry. Tested
     hostilely, including a vetted script with an appended payload.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon import cdp_readonly as ro  # noqa: E402
from freight_recon.cdp_readonly import (  # noqa: E402
    FORBIDDEN_PRIMITIVES,
    READ_ONLY_CDP_METHODS,
    VETTED_READ_SCRIPTS,
    ReadOnlyCdpError,
    ReadOnlyCdpObserver,
    _ReadOnlyChannel,
)

MODULE_SRC = Path(ro.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------- fakes (no browser, no network)

class FakeWs:
    """Records what would have reached the browser. Nothing here can actuate anything."""

    def __init__(self, value=None):
        self.sent: list[dict] = []
        self._value = value

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def recv(self) -> str:
        last = self.sent[-1]
        return json.dumps(
            {"id": last["id"], "result": {"result": {"value": self._value}}}
        )

    def close(self) -> None:
        pass


def channel(value=None) -> tuple[_ReadOnlyChannel, FakeWs]:
    ws = FakeWs(value)
    return _ReadOnlyChannel(ws, timeout=1), ws


def observer(value=None) -> tuple[ReadOnlyCdpObserver, FakeWs]:
    obs = ReadOnlyCdpObserver()
    chan, ws = channel(value)
    object.__setattr__(obs, "_ReadOnlyCdpObserver__channel", chan)
    object.__setattr__(obs, "_ReadOnlyCdpObserver__context_id", 1)
    return obs, ws


# ---------------------------------------------------------------- 1. no mutation API exists

def test_the_observer_exposes_no_mutation_primitive():
    """Barrier 1, by attribute surface — not by reading the file."""
    present = [name for name in FORBIDDEN_PRIMITIVES if hasattr(ReadOnlyCdpObserver, name)]
    assert not present, f"the read-only surface exposes mutation primitives: {present}"


def test_the_forbidden_list_actually_names_the_real_actuation_primitives():
    """A negative assertion over an empty/wrong population proves nothing.

    Every name in FORBIDDEN_PRIMITIVES must really exist on the write-capable surfaces, or this
    guard is checking for the absence of things that were never a threat.
    """
    from freight_recon.cdp_actuator import CdpActuator
    from freight_recon.cdp_session import CdpBrowserSession

    for name in FORBIDDEN_PRIMITIVES:
        assert hasattr(CdpBrowserSession, name) or hasattr(CdpActuator, name), (
            f"{name!r} is guarded against but exists on neither write-capable surface - the "
            "forbidden list has drifted away from the real primitives"
        )


def test_every_public_method_on_the_observer_is_an_observation():
    allowed = {
        "observe", "read", "money_field_values", "is_submit_target", "page_signature",
        # `load_row_links` reports which rows carry a load identifier and what anchors those rows
        # contain. It is EP-3's provenance OBSERVATION: it runs a vetted script like every other
        # read, returns structure, and can act on nothing it found. Reporting that a link exists is
        # not the authority to follow it - that decision lives on the navigator.
        "load_row_links",
        "current_url", "capture_screenshot", "connect", "close",
    }
    public = {
        n for n, _ in inspect.getmembers(ReadOnlyCdpObserver, inspect.isfunction)
        if not n.startswith("_")
    }
    assert public <= allowed, f"unexpected public methods on the read-only surface: {public - allowed}"


def test_the_observer_hands_out_no_object_that_can_actuate():
    """A read-side caller must not be able to REACH an actuator through the observer."""
    obs, _ = observer()
    for name in dir(obs):
        if name.startswith("_ReadOnlyCdpObserver__") or name.startswith("__"):
            continue
        value = getattr(obs, name, None)
        for primitive in ("evaluate", "command", "set_file_input"):
            assert not hasattr(value, primitive), (
                f"public attribute {name!r} exposes {primitive!r} - the read side can reach an actuator"
            )


# ---------------------------------------------------------------- 2. caller data is never code

def _function_named(name: str) -> ast.FunctionDef:
    tree = ast.parse(MODULE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in cdp_readonly")


def test_the_dispatch_path_builds_no_javascript_from_caller_data():
    """Barrier 2, structurally: `_call` contains no string interpolation of any kind."""
    node = _function_named("_call")
    offenders = [
        type(n).__name__
        for n in ast.walk(node)
        if isinstance(n, ast.JoinedStr)
        or (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mod)))
    ]
    assert not offenders, (
        f"_call performs string building ({offenders}) - caller data must reach the page as "
        "Runtime.callFunctionOn `arguments`, never spliced into JavaScript source"
    )


def test_caller_data_travels_as_protocol_arguments():
    obs, ws = observer(value="x")
    obs.read("Balance Due'; document.title='pwned")
    sent = ws.sent[-1]
    assert sent["method"] == "Runtime.callFunctionOn"
    assert sent["params"]["functionDeclaration"] == ro.READ_FN, "the script was not the vetted one"
    assert sent["params"]["arguments"] == [{"value": "Balance Due'; document.title='pwned"}], (
        "the target did not travel as a protocol argument"
    )
    assert "pwned" not in sent["params"]["functionDeclaration"], (
        "caller data reached the JavaScript SOURCE - this is the F2 defect"
    )


def test_a_hostile_target_cannot_escape_into_the_script():
    obs, ws = observer(value=False)
    for hostile in (
        "'); document.querySelector('button').click(); ('",
        '"); fetch("https://evil.example/x"); ("',
        "</script><script>alert(1)</script>",
    ):
        obs.is_submit_target(hostile)
        declaration = ws.sent[-1]["params"]["functionDeclaration"]
        assert declaration == ro.IS_SUBMIT_FN, "the vetted script was altered"
        assert hostile not in declaration


def test_the_read_only_module_imports_no_write_capable_surface():
    tree = ast.parse(MODULE_SRC)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    banned = [m for m in imported if "cdp_session" in m or "cdp_actuator" in m]
    assert not banned, (
        f"the read-only surface imports a write-capable module: {banned}. The dependency must run "
        "the other way, or the read substrate is actuation-capable again."
    )


# ---------------------------------------------------------------- 3. the channel refuses

@pytest.mark.parametrize(
    "method, params",
    [
        ("Runtime.evaluate", {"expression": "document.title='pwned'"}),
        ("Input.insertText", {"text": "1000000"}),
        ("Input.dispatchKeyEvent", {"type": "keyDown"}),
        ("Input.dispatchMouseEvent", {"type": "mousePressed"}),
        ("DOM.setFileInputFiles", {"files": ["/etc/passwd"]}),
        ("Page.navigate", {"url": "https://evil.example"}),
        ("Network.setCookie", {"name": "session"}),
    ],
)
def test_the_channel_refuses_every_non_read_cdp_method(method, params):
    chan, ws = channel()
    with pytest.raises(ReadOnlyCdpError):
        chan.send(method, params)
    assert ws.sent == [], f"{method} reached the browser before being refused"


def test_runtime_evaluate_is_not_allowlisted():
    """The arbitrary-JavaScript primitive is the whole of F2. It may never be admitted."""
    assert "Runtime.evaluate" not in READ_ONLY_CDP_METHODS


def test_the_channel_refuses_an_unvetted_script():
    chan, ws = channel()
    with pytest.raises(ReadOnlyCdpError):
        chan.send(
            "Runtime.callFunctionOn",
            {"functionDeclaration": "function(){document.querySelector('button').click();}"},
        )
    assert ws.sent == []


def test_the_channel_refuses_a_vetted_script_with_an_appended_payload():
    """Membership is by exact VALUE, so a lookalike or a superset is not a member."""
    chan, ws = channel()
    with pytest.raises(ReadOnlyCdpError):
        chan.send(
            "Runtime.callFunctionOn",
            {"functionDeclaration": ro.OBSERVE_FN + "\n;document.forms[0].submit();"},
        )
    assert ws.sent == []


def test_the_channel_admits_a_vetted_script():
    """The refusals above must not pass vacuously - the allowed path has to work."""
    chan, ws = channel(value={"url": "u"})
    chan.send("Runtime.callFunctionOn", {"functionDeclaration": ro.OBSERVE_FN})
    assert len(ws.sent) == 1


def test_reaching_the_private_channel_still_does_not_grant_actuation():
    """Python has no private state; the channel refuses anyway. That is why barrier 3 exists."""
    obs, ws = observer()
    private = getattr(obs, "_ReadOnlyCdpObserver__channel")
    with pytest.raises(ReadOnlyCdpError):
        private.send("Input.insertText", {"text": "x"})
    with pytest.raises(ReadOnlyCdpError):
        private.send("Runtime.evaluate", {"expression": "1"})
    assert ws.sent == []


# ---------------------------------------------------------------- the vetted scripts do not mutate

_MUTATING_JS = re.compile(
    r"\.click\s*\(|\.focus\s*\(|\.submit\s*\(|\.blur\s*\(|dispatchEvent|"
    r"\.value\s*=[^=]|\.innerHTML\s*=[^=]|\.innerText\s*=[^=]|location\s*=[^=]|"
    r"location\.(?:assign|replace)|document\.write|\.setAttribute\s*\(|\.remove\s*\(\s*\)"
)


@pytest.mark.parametrize("name", sorted(
    n for n in dir(ro) if n.endswith("_FN") and isinstance(getattr(ro, n), str)
))
def test_no_vetted_script_contains_a_mutating_operation(name):
    script = getattr(ro, name)
    found = _MUTATING_JS.findall(script)
    assert not found, f"{name} contains mutating DOM operations: {found}"


def test_the_vetted_registry_is_exactly_the_declared_read_scripts():
    declared = {
        getattr(ro, n) for n in dir(ro)
        if n.endswith("_FN") and isinstance(getattr(ro, n), str)
    }
    assert VETTED_READ_SCRIPTS == declared, (
        "the vetted registry and the declared read scripts disagree - a script is reachable that "
        "was never vetted, or a vetted entry has no source"
    )
    assert len(VETTED_READ_SCRIPTS) >= 5, "the vetted population collapsed"


def test_the_mutation_detector_actually_detects(  # mutation proof for the guard above
):
    """A detector never seen to fire is a decoration."""
    assert _MUTATING_JS.search("function(){document.querySelector('b').click();}")
    assert _MUTATING_JS.search("function(){el.value='9999';}")
    assert _MUTATING_JS.search("function(){el.dispatchEvent(new Event('input'));}")
    assert not _MUTATING_JS.search("function(){return location.href;}")


# ---------------------------------------------------------------- the two surfaces cannot drift

def test_the_actuator_sources_its_read_scripts_from_the_read_only_surface():
    """ONE source of truth: the write surface imports the read scripts, never re-implements them."""
    from freight_recon import cdp_actuator as act

    assert act._OBSERVE_JS == "(" + ro.OBSERVE_FN + ")()"
    assert act._IS_SUBMIT_JS == "(" + ro.IS_SUBMIT_FN + ")"
    assert act._MONEY_FIELDS_JS == "(" + ro.MONEY_FIELDS_FN + ")()"
    assert act._READ_JS == "(" + ro.READ_FN + ")"
