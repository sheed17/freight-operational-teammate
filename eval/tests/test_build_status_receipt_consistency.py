"""The BUILD-STATUS receipt-consistency guard (N-1).

BUILD-STATUS.yaml is classified CURRENT_STATUS, but only its `derived:` block is machine-written by
the finalizer. Its `snapshot:` narrative is HAND-AUTHORED, and nothing checked it against the
finalizer's own receipts. That gap is exactly how N-1 arose: the snapshot kept asserting the
finalizer had REFUSED and the clean-clone gate had FAILED long after both had actually run and
passed on the finalized P3 content commit. A CURRENT_STATUS document narrating a failure the
authoritative receipts contradict is a false status, and until now no guard would notice.

The authoritative receipts are the two files the finalizer/gate PRODUCE from their own in-process
observations and bind to a commit+tree:

  - docs/implementation/SUITE-RESULT.json  (scripts/run_canonical_suite via finalize_status)
  - docs/implementation/GATE-RESULT.json   (scripts/clean_clone_gate)

This guard reads those receipts, resolves whether the finalizer and clean-clone actually PASSED on
the recorded content commit, and then requires the authored snapshot to AGREE - in BOTH directions:

  - the snapshot may not claim finalizer / clean-clone FAILURE (or that no such success exists)
    when the receipts record PASS for the recorded content commit/tree, and
  - the snapshot may not claim PASS when the receipts do not support it.

It is intentionally receipt-grounded, not prose-graded: the narrative's leading verdict TOKEN on
`finalizer_result` / `clean_clone_result` is the machine-checkable claim, cross-checked against the
receipts; a small, documented set of stale-failure ASSERTION signatures is additionally forbidden
anywhere in the snapshot while the receipts say PASS. The mutation fixtures below are frozen copies
of the exact N-1 stale text and prove the checker fires on it - the guard is not vacuous, and it
catches the reverse contradiction too.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
IMPL = ROOT / "docs" / "implementation"
BUILD_STATUS = IMPL / "BUILD-STATUS.yaml"
CURRENT = IMPL / "CURRENT.md"
SUITE_RESULT = IMPL / "SUITE-RESULT.json"
GATE_RESULT = IMPL / "GATE-RESULT.json"

# The controlled verdict vocabulary the two result fields must lead with. The receipts decide which
# one is legal; the field only has to state it truthfully.
SUCCESS_TOKENS = {"PASS"}
FAILURE_TOKENS = {"REFUSED", "FAILED", "NOT EXECUTED", "BLOCKED", "NOT PASSING"}

# Stale-failure ASSERTION signatures: present-tense claims that the finalizer / clean-clone did NOT
# succeed, or that the status state is illegal. Each is a phrase from the N-1 stale narrative that
# flatly contradicts PASS receipts. They are assertion-shaped, not neutral description, so a
# corrected narrative that says the old deadlock "has been resolved" does not trip them.
STALE_FAILURE_CLAIMS = [
    r"\bNO finalizer(?:[ -]or[ -]clean-clone)?\s+success is (?:recorded|claimed)\b",
    r"\bno finalizer success is claimed\b",
    r"\bno clean-clone success is claimed\b",
    r"\bREFUSED for P3\b",
    r"\bFAILED for P3\b",
    r"\bNOT EXECUTED \(blocked\b",
    r"\bthe (?:repository|status state) is (?:in an )?ILLEGAL\b",
    r"\btwo unfinalized content commits\b",
    r"\bfull-suite final-tree validation:\s*NOT PASSING\b",
    r"\bno finalizer-executed suite record exists\b",
]


# ------------------------------------------------------------------ receipt resolution

def _recorded_content() -> tuple[str, str]:
    """(content_commit, content_tree) as recorded in CURRENT.md's finalizer-written status block."""
    m = re.search(r"```yaml\n(# status-block:.*?)```", CURRENT.read_text(encoding="utf-8"), re.S)
    assert m, "CURRENT.md has no machine-maintained status-block"
    blk = yaml.safe_load(m.group(1))
    return blk["content_commit"], blk["content_tree"]


def _receipt_pass(path: Path, commit: str, tree: str, *, suite: bool) -> bool:
    """True iff the receipt exists, binds to the recorded (commit, tree), and records success.

    For the suite receipt, success is exit 0, zero failures, some tests passed. For the gate
    receipt, success is passed:true. A receipt for a DIFFERENT commit/tree cannot certify the
    current content - it is treated as no evidence of success (False)."""
    if not path.exists():
        return False
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    if d.get("commit") != commit or d.get("tree") != tree:
        return False
    if suite:
        return d.get("exit_status") == 0 and d.get("failed") == 0 and int(d.get("passed", 0)) > 0
    return bool(d.get("passed"))


def _leading_verdict(field: str) -> str | None:
    """The leading canonical verdict token of a result field, or None if it carries none.
    'PASS - ...' -> 'PASS'; 'NOT EXECUTED (blocked...' -> 'NOT EXECUTED'; 'REFUSED for P3' ->
    'REFUSED'. The run of leading capitals/spaces is matched, then compared to the vocabulary."""
    m = re.match(r"^[A-Z][A-Z ]*", field.strip())
    if not m:
        return None
    lead = " ".join(m.group(0).split())
    for tok in sorted(SUCCESS_TOKENS | FAILURE_TOKENS, key=len, reverse=True):
        if lead == tok or lead.startswith(tok + " "):
            return tok
    return None


# ------------------------------------------------------------------ the pure checker (both directions)

def receipt_consistency_errors(finalizer_pass: bool, clean_clone_pass: bool, snapshot: dict) -> list[str]:
    """Contradictions between the authored snapshot and the receipt-derived truth. Empty == agree.

    Direction 1 (the N-1 defect): a PASS receipt with a FAILURE narrative.
    Direction 2 (the reverse): a PASS narrative the receipts do not support.
    """
    errs: list[str] = []
    for field_name, passed in (("finalizer_result", finalizer_pass), ("clean_clone_result", clean_clone_pass)):
        value = str(snapshot.get(field_name, ""))
        tok = _leading_verdict(value)
        if tok is None:
            errs.append(f"{field_name} carries no canonical leading verdict token "
                        f"(expected one of {sorted(SUCCESS_TOKENS | FAILURE_TOKENS)}): {value[:60]!r}")
            continue
        is_success = tok in SUCCESS_TOKENS
        if passed and not is_success:
            errs.append(f"{field_name} claims {tok!r} but the authoritative receipt for the "
                        f"recorded content commit records PASS")
        if not passed and is_success:
            errs.append(f"{field_name} claims {tok!r} but no passing receipt for the recorded "
                        f"content commit supports it")

    if finalizer_pass and clean_clone_pass:
        blob = yaml.safe_dump(snapshot, sort_keys=False, allow_unicode=True)
        for pat in STALE_FAILURE_CLAIMS:
            if re.search(pat, blob, re.I):
                errs.append(f"snapshot asserts a stale finalizer/clean-clone failure while the "
                            f"receipts record PASS: /{pat}/")
    return errs


# ------------------------------------------------------------------ the real-tree assertion

def _snapshot() -> dict:
    return yaml.safe_load(BUILD_STATUS.read_text(encoding="utf-8"))["snapshot"]


def test_the_scan_population_is_non_empty():
    """A negative scan over an empty pattern set passes vacuously. Prove the population exists."""
    assert STALE_FAILURE_CLAIMS, "the stale-failure signature list is empty - the scan is vacuous"
    assert SUCCESS_TOKENS and FAILURE_TOKENS, "the verdict vocabulary collapsed"


def test_build_status_snapshot_agrees_with_the_authoritative_receipts():
    """The live guard: BUILD-STATUS's authored narrative may not contradict the finalizer/gate
    receipts for the recorded content commit, in either direction."""
    commit, tree = _recorded_content()
    snap = _snapshot()
    assert snap.get("finalizer_result") and snap.get("clean_clone_result"), (
        "snapshot is missing the finalizer_result / clean_clone_result fields this guard checks"
    )
    fin_pass = _receipt_pass(SUITE_RESULT, commit, tree, suite=True)
    cc_pass = _receipt_pass(GATE_RESULT, commit, tree, suite=False)
    errs = receipt_consistency_errors(fin_pass, cc_pass, snap)
    assert not errs, (
        "BUILD-STATUS snapshot contradicts the authoritative receipts:\n  " + "\n  ".join(errs)
        + f"\n(receipt truth: finalizer_pass={fin_pass}, clean_clone_pass={cc_pass})"
    )


def test_the_result_fields_lead_with_a_canonical_verdict_token():
    snap = _snapshot()
    for field in ("finalizer_result", "clean_clone_result"):
        assert _leading_verdict(str(snap[field])) is not None, (
            f"{field} must lead with a canonical verdict token so it is machine-checkable: "
            f"{str(snap[field])[:60]!r}"
        )


# ------------------------------------------------------------------ mutation proofs (run every suite)
# Frozen copies of the EXACT N-1 stale text. If the checker did not fire on these, it would not have
# caught N-1 - so each proves the guard is load-bearing, and together they exercise both directions.

_STALE_FINALIZER = ("REFUSED for P3 - not merely unexecuted. On the remediated tree it was executed "
                    "twice and refused both times: the status authority is stale because 38f2714 and "
                    "the remediation commit are two unfinalized content commits. NO finalizer success "
                    "is claimed.")
_STALE_CLEAN_CLONE = ("FAILED for P3, and it never reached the suite. It FAILS at the declared-dependency "
                      "install because pip cannot verify pypi.org TLS certificates. NO clean-clone "
                      "success is claimed for any P3 tree.")


def test_catches_the_n1_failure_narrative_under_passing_receipts():
    """Direction 1: PASS receipts + the exact stale REFUSED/FAILED narrative -> flagged."""
    stale = {"finalizer_result": _STALE_FINALIZER, "clean_clone_result": _STALE_CLEAN_CLONE}
    errs = receipt_consistency_errors(True, True, stale)
    assert any("finalizer_result claims 'REFUSED'" in e for e in errs), errs
    assert any("clean_clone_result claims 'FAILED'" in e for e in errs), errs
    assert any("stale finalizer/clean-clone failure" in e for e in errs), errs


def test_catches_the_reverse_contradiction():
    """Direction 2: a PASS narrative the receipts do NOT support -> flagged for both fields."""
    green = {"finalizer_result": "PASS - the finalizer ran and recorded the status",
             "clean_clone_result": "PASS - the gate reproduced the suite"}
    errs = receipt_consistency_errors(False, False, green)
    assert any("finalizer_result claims 'PASS'" in e and "no passing receipt" in e for e in errs), errs
    assert any("clean_clone_result claims 'PASS'" in e and "no passing receipt" in e for e in errs), errs


def test_catches_a_stale_illegal_status_claim_in_any_field():
    """A resolved-deadlock assertion left present-tense anywhere in the snapshot, under PASS
    receipts, is a contradiction even if the two result fields themselves read PASS."""
    snap = {"finalizer_result": "PASS - ran clean", "clean_clone_result": "PASS - reproduced",
            "open_program_risks": ["the repository is in an ILLEGAL status state: two unfinalized "
                                   "content commits"]}
    errs = receipt_consistency_errors(True, True, snap)
    assert any("stale finalizer/clean-clone failure" in e for e in errs), errs


def test_a_matching_pass_narrative_under_passing_receipts_is_accepted():
    """No false positive: a correct PASS narrative under PASS receipts yields no errors."""
    snap = _snapshot()
    assert receipt_consistency_errors(True, True, snap) == [], (
        "the corrected real snapshot must be accepted under PASS receipts"
    )
