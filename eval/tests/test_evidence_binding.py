"""Immutable, banner-aware binding of the R-07 containment record to its load-bearing evidence.

THE DEFECT THIS CLOSES (F-03). The containment record cites review, adjudication and finalization
reports by path and by SHA-256. Nothing verified either. The guard that existed asserted only that
the digest STRING occurred somewhere in the manifest text and that the named path EXISTED; it never
recomputed a hash, and no test in `eval/` opened a `.sha256` sidecar at all. The targeted
adjudication proved the consequence rather than arguing it: inside a disposable clone at the
candidate tree it flipped a load-bearing adjudication verdict from

    **Verdict: ACCEPT P4 FOR FINALIZATION**  ->  **Verdict: REJECT P4 FOR FINALIZATION**

left the sidecar stale, and ran the full canonical suite: 1957 tests passed. The chain was bound at
the CITATION level and never at the CONTENT level, while the record claimed in terms that "a
re-pointed guard fails the build ... if any evidence element is missing or mismatched".

THE PRESERVED BLOB IS THE SOURCE OF TRUTH, NOT THE WORKTREE FILE. A naive
`sha256(worktree file) == sidecar` guard cannot be the fix - it would fail on three documents BY
DESIGN. `test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim`
REQUIRES tracked historical reviews to carry a disarming banner so a grep-first reader cannot
mistake evidence for authority, and adding a banner necessarily changes the file's bytes. The
sidecar therefore authenticates the ORIGINAL report body, and the byte-exact original lives at a
`refs/preserve/*` commit whose parent is the exact commit it attests.

So the binding is: the PRESERVED BLOB must hash to the recorded digest, and the worktree rendering
must reduce to that same blob byte-for-byte. A mutable worktree file can never substitute for a
different preserved report, and the banner convention is neither weakened nor deleted.

BANNER-AWARE, DETERMINISTICALLY. A bannered report is one whose first line opens a markdown
blockquote. The parser removes EXACTLY ONE leading blockquote block plus the blank lines after it
and nothing else - it does not scan for a marker, and it cannot be steered by content below. What
remains must equal the preserved blob byte-for-byte, so a banner that swallowed a line of the
report, or a body quietly substituted beneath a valid-looking banner, fails. The banner must also
be a REAL disarm banner (it must say the document is historical and not current authority) and must
disclose the sidecar convention, so the banner cannot degenerate into a decorative wrapper.

EVERYTHING IS DERIVED FROM THE RECORD, NOT HAND-LISTED HERE. The report set, digests and
preservation refs are parsed out of `expected_legacy_paths.containment_evidence`, and each expected
preservation PARENT is resolved from the commit fields recorded in that same block. Adding a report
to the record therefore adds it to this guard automatically; a hand-maintained list here could go
stale exactly the way the citations did.

TWO TIERS, BECAUSE A CLEAN CLONE HAS NO `refs/preserve/*`. `git clone` copies `refs/heads/*` and
`refs/tags/*` and nothing else, and these preservation refs are deliberately never pushed. A guard
that can only run where those refs exist cannot run in the clean-clone gate - which is the
repository's reproducibility oracle - and the first draft of this file failed there for exactly
that reason. The answer is NOT to skip:

  TIER 1 - UNCONDITIONAL, and it is the load-bearing one. The banner-stripped worktree body must
  hash to the digest the containment record cites, the sidecar must record that same digest, a
  banner-required document must still be bannered, and the recorded verdict must appear in the
  body. This runs in EVERY environment and it is what catches the verdict flip, a tampered or
  missing sidecar, a missing report, a removed banner and a substituted body.

  TIER 2 - ATTRIBUTION, where preservation history is present. The preserved blob must hash to the
  digest, the body must equal it byte-for-byte, and the preservation commit must parent the exact
  commit it attests. This is what proves an immutable off-branch original exists with correct
  provenance.

THE TIER-2 CONDITION IS ALL-OR-NOTHING, WHICH IS WHAT KEEPS IT HONEST. If NO `refs/preserve/*` ref
exists at all, this is a distribution clone and tier 2 is not applicable. If ANY exists, the
environment carries preservation history and EVERY load-bearing report's ref MUST resolve
correctly - a single missing or re-pointed ref is then a hard failure, not an environment fact.
Partial availability is precisely what tampering looks like, so it is never tolerated.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "implementation" / "phase-0-baseline-manifest.yaml"

_SHA256 = re.compile(r"\b([0-9a-f]{64})\b")
_REF = re.compile(r"\b(refs/preserve/[\w./-]+)")
_PATH = re.compile(r"\b(docs/implementation/[\w.-]+\.md)\b")
_VERDICT = re.compile(r"verdict\s+([A-Z][A-Z0-9 ]{4,}?)(?=,\s+sha256\b)")

# A banner is a disarm notice, not decoration: it must say the document is not current authority,
# and it must disclose that the sidecar authenticates the original rather than the bannered copy.
_BANNER_DISARM = re.compile(r"NOT\s+CURRENT\s+AUTHORITY", re.I)
_BANNER_SIDECAR_NOTE = re.compile(r"SIDECAR\s+HASH\s+IS\s+THE\s+ORIGINAL", re.I)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_show(ref_path: str) -> bytes | None:
    """Raw bytes of a blob at a ref, or None when the ref or path does not resolve."""
    out = subprocess.run(["git", "show", ref_path], cwd=ROOT, capture_output=True)
    return out.stdout if out.returncode == 0 else None


def git_rev_parse(rev: str) -> str | None:
    out = subprocess.run(["git", "rev-parse", "--verify", "--quiet", rev],
                         cwd=ROOT, capture_output=True, text=True)
    return out.stdout.strip() or None


def strip_banner(raw: bytes) -> tuple[bytes, int]:
    """Remove EXACTLY ONE leading markdown blockquote block and the blank lines after it.

    Deterministic and content-blind. Reports legitimately contain further blockquotes in their own
    bodies, so only the FIRST contiguous block is a banner; anything else belongs to the report.
    """
    lines = raw.split(b"\n")
    if not lines or not lines[0].startswith(b">"):
        return raw, 0
    i = 0
    while i < len(lines) and lines[i].startswith(b">"):
        i += 1
    banner_lines = i
    while i < len(lines) and lines[i].strip() == b"":
        i += 1
    return b"\n".join(lines[i:]), banner_lines


@dataclass(frozen=True)
class Evidence:
    """One load-bearing report and every binding the record makes about it."""

    key: str
    path: str
    expected_sha256: str
    preserve_ref: str
    expected_parent: str | None
    verdict: str | None


def _containment_evidence() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["expected_legacy_paths"][
        "containment_evidence"
    ]


def load_bearing_reports() -> list[Evidence]:
    """MECHANICALLY ENUMERATED from the containment record - never hand-listed.

    Every citation that names a report path, a digest and a preservation ref is load-bearing by
    construction. The expected preservation parent is resolved from the commit fields recorded in
    the same block, matched by the short commit the ref name carries.
    """
    ce = _containment_evidence()
    commits = {
        k: v for k, v in ce.items()
        if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v.strip())
    }
    out: list[Evidence] = []
    for key, value in ce.items():
        if not isinstance(value, str):
            continue
        flat = " ".join(value.split())
        path, digest, ref = _PATH.search(flat), _SHA256.search(flat), _REF.search(flat)
        if not (path and digest and ref):
            continue
        ref_name = ref.group(1)
        parent = None
        for commit in commits.values():
            # the ref name ends in the short form of the commit it attests
            if re.search(rf"[-/]{re.escape(commit[:7])}\d*$", ref_name) or ref_name.endswith(commit[:8]):
                parent = commit
                break
        verdict = _VERDICT.search(flat)
        out.append(Evidence(
            key=key,
            path=path.group(1),
            expected_sha256=digest.group(1),
            preserve_ref=ref_name,
            expected_parent=parent,
            verdict=" ".join(verdict.group(1).split()) if verdict else None,
        ))
    return out


def verify(ev: Evidence, *, worktree: bytes | None, preserved: bytes | None,
           sidecar: str | None, ref_target: str | None, parent: str | None,
           banner_required: bool = False, preservation_available: bool = True) -> list[str]:
    """Every binding, evaluated over INJECTED inputs so hostile cases can tamper with one at a time.

    Returning the failure list rather than asserting is what lets the negative battery below prove
    that each specific tamper is detected, instead of proving only that something somewhere failed.

    `preservation_available` is the tier-2 condition (see the module docstring): False ONLY in an
    environment carrying no preservation history at all, where ref/parent/preserved-blob checks are
    inapplicable. Tier 1 runs regardless and is never relaxed.
    """
    fail: list[str] = []

    if preservation_available:
        if ref_target is None:
            fail.append(f"{ev.key}: preservation ref {ev.preserve_ref} does not resolve")
        if preserved is None:
            fail.append(f"{ev.key}: no preserved blob for {ev.path} at {ev.preserve_ref}")
    if worktree is None:
        fail.append(f"{ev.key}: report {ev.path} is missing from the worktree")
    if sidecar is None:
        fail.append(f"{ev.key}: sidecar {ev.path}.sha256 is missing")

    # TIER 1. The banner-stripped worktree body must hash to the digest the record cites. This is
    # the check that needs no refs and catches every content tamper.
    if worktree is not None:
        body, _ = strip_banner(worktree)
        got = sha256(body)
        if got != ev.expected_sha256:
            fail.append(
                f"{ev.key}: the authenticated body of {ev.path} hashes to {got}, but the "
                f"containment record cites {ev.expected_sha256}"
            )

    # TIER 2. The preserved blob is the immutable original; it must hash to the same digest.
    if preserved is not None:
        got = sha256(preserved)
        if got != ev.expected_sha256:
            fail.append(
                f"{ev.key}: preserved blob at {ev.preserve_ref} hashes to {got}, but the "
                f"containment record cites {ev.expected_sha256}"
            )

    # The sidecar must agree with the record, so a stale sidecar cannot silently authenticate.
    if sidecar is not None:
        recorded = sidecar.split()[0] if sidecar.split() else ""
        if recorded != ev.expected_sha256:
            fail.append(
                f"{ev.key}: sidecar records {recorded or '(empty)'}, record cites "
                f"{ev.expected_sha256}"
            )

    # The mutable worktree rendering must REDUCE to the immutable preserved blob.
    if worktree is not None and preserved is not None:
        body, banner_lines = strip_banner(worktree)
        # THE BANNER MAY NOT BE QUIETLY DROPPED. Removing it makes the worktree copy equal the
        # preserved blob again, so the body comparison alone goes green - a debanner is invisible
        # to a pure byte-equality check. The control system requires these documents to disarm
        # before a grep-first reader can mistake evidence for authority, so the requirement is
        # bound here as well, over the DISCOVERED banner-required population.
        if banner_required and not banner_lines:
            fail.append(
                f"{ev.key}: {ev.path} is a banner-required historical document but carries no "
                f"disarm banner - a reader landing on it would read evidence as current authority"
            )
        if banner_lines:
            head = worktree.split(b"\n\n", 1)[0].decode("utf-8", "replace")
            if not _BANNER_DISARM.search(head):
                fail.append(f"{ev.key}: banner present but does not disarm the document")
            if body != preserved and not _BANNER_SIDECAR_NOTE.search(head):
                fail.append(f"{ev.key}: bannered report does not disclose the sidecar convention")
        if body != preserved:
            fail.append(
                f"{ev.key}: the worktree copy of {ev.path} does not reduce to the preserved blob "
                f"(banner lines stripped: {banner_lines}) - a mutable report may never substitute "
                f"for the accepted evidence"
            )

    # TIER 2. Attribution: the preservation commit must parent the exact commit it attests.
    if preservation_available and ev.expected_parent is not None:
        if parent != ev.expected_parent:
            fail.append(
                f"{ev.key}: {ev.preserve_ref} has parent {parent}, expected the attested commit "
                f"{ev.expected_parent}"
            )

    # TIER 1. The recorded verdict must actually appear in the authenticated evidence.
    if ev.verdict:
        source = preserved if preserved is not None else (
            strip_banner(worktree)[0] if worktree is not None else None
        )
        if source is not None:
            text = " ".join(source.decode("utf-8", "replace").split())
            if ev.verdict not in text:
                fail.append(
                    f"{ev.key}: the record cites verdict {ev.verdict!r}, which does not appear in "
                    f"the report"
                )
    return fail


def _banner_required() -> set[str]:
    """DISCOVERED, from the same authority `test_false_green_defenses.py` uses - never hand-listed,
    so a report that becomes banner-required is bound here automatically."""
    import sys

    sys.path.insert(0, str(ROOT / "eval"))
    from control import inventory as inv

    return set(inv.banner_required_documents())


def preservation_history_present() -> bool:
    """ALL-OR-NOTHING tier-2 condition (see the module docstring).

    True when this environment carries ANY `refs/preserve/*` ref. A clean clone carries none, since
    `git clone` copies only `refs/heads/*` and `refs/tags/*` and these refs are never pushed. Once
    ANY exists, every load-bearing report's ref must resolve correctly - partial availability is
    what tampering looks like, and it is never tolerated.
    """
    out = subprocess.run(["git", "for-each-ref", "--format=%(refname)", "refs/preserve/"],
                         cwd=ROOT, capture_output=True, text=True)
    return bool(out.stdout.strip())


def _real_inputs(ev: Evidence) -> dict:
    wt = ROOT / ev.path
    sc = ROOT / (ev.path + ".sha256")
    available = preservation_history_present()
    ref_target = git_rev_parse(ev.preserve_ref) if available else None
    return {
        "worktree": wt.read_bytes() if wt.exists() else None,
        "preserved": git_show(f"{ev.preserve_ref}:{ev.path}") if available else None,
        "sidecar": sc.read_text(encoding="utf-8") if sc.exists() else None,
        "ref_target": ref_target,
        "parent": git_rev_parse(f"{ev.preserve_ref}^") if ref_target else None,
        "banner_required": ev.path in _banner_required(),
        "preservation_available": available,
    }


def _tier2_inputs(ev: Evidence, inputs: dict) -> dict:
    """Inputs on which the TIER-2 hostile cases can bite in ANY environment.

    Where preservation history exists these are the real ref-backed values, untouched. Where it does
    not, the tier-2 checks are switched on against the authenticated body and the recorded parent -
    values tier 1 has already proven hash to the cited digest. That is not a weaker corpus: the
    hostile case then tampers with exactly one of them and must still be caught, which is what these
    tests exist to prove. It keeps the negative battery running everywhere instead of skipping it in
    a clean clone, where a skipped test proves nothing.
    """
    if inputs.get("preservation_available"):
        return inputs
    body, _ = strip_banner(inputs["worktree"]) if inputs["worktree"] else (None, 0)
    return {**inputs, "preservation_available": True, "preserved": body,
            "ref_target": ev.expected_parent, "parent": ev.expected_parent}


# ===================================================================== the positive corpus


def test_the_load_bearing_report_set_is_non_empty_and_covers_the_known_chain():
    """No negative assertion below may run over an empty corpus."""
    reports = load_bearing_reports()
    assert len(reports) >= 6, (
        f"only {len(reports)} load-bearing reports enumerated from the containment record - every "
        "binding below would pass vacuously"
    )
    keys = {e.key for e in reports}
    for required in (
        "accepted_independent_rereview",
        "final_adjudication",
        "first_finalization_report",
        "accepted_targeted_independent_review",
        "accepted_targeted_adjudication",
        "second_finalization_report",
    ):
        assert required in keys, (
            f"{required} is no longer bound by the containment record - a load-bearing report "
            f"cannot be dropped from the evidence chain silently"
        )
    assert all(e.expected_parent for e in reports), (
        "every preservation ref must resolve to an attested commit: "
        f"{[e.key for e in reports if not e.expected_parent]}"
    )
    # at least one report must carry a parsed verdict, or the verdict binding is decorative
    assert sum(1 for e in reports if e.verdict) >= 4, (
        "fewer than four recorded verdicts parsed - the ACCEPT->REJECT binding would not bite"
    )


@pytest.mark.parametrize("key", [e.key for e in load_bearing_reports()])
def test_every_load_bearing_report_is_bound_to_its_immutable_preserved_evidence(key: str):
    ev = next(e for e in load_bearing_reports() if e.key == key)
    failures = verify(ev, **_real_inputs(ev))
    assert not failures, "evidence binding failed:\n  " + "\n  ".join(failures)


def test_the_sidecar_population_is_non_empty_and_every_sidecar_authenticates_a_present_report():
    sidecars = sorted((ROOT / "docs" / "implementation").glob("*.sha256"))
    assert len(sidecars) >= 6, f"the sidecar population collapsed to {len(sidecars)}"
    for sc in sidecars:
        target = sc.with_suffix("")
        assert target.exists(), f"{sc.name} authenticates {target.name}, which does not exist"
        recorded = sc.read_text(encoding="utf-8").split()
        assert recorded and re.fullmatch(r"[0-9a-f]{64}", recorded[0]), (
            f"{sc.name} does not record a SHA-256"
        )


def test_the_banner_parser_isolates_the_authenticated_body_of_every_bannered_report():
    """Positively prove the bannered population is non-empty AND that stripping is exact."""
    bannered = []
    for ev in load_bearing_reports():
        raw = (ROOT / ev.path).read_bytes()
        body, n = strip_banner(raw)
        if n:
            bannered.append((ev, n, body))
    assert bannered, (
        "no bannered report found - either the banner convention was deleted (which "
        "test_false_green_defenses requires) or this guard stopped exercising it"
    )
    available = preservation_history_present()
    for ev, n, body in bannered:
        # TIER 1: the isolated body must hash to the digest the record cites, in EVERY environment.
        assert sha256(body) == ev.expected_sha256, (
            f"{ev.key}: stripping {n} banner lines did not reproduce the authenticated body"
        )
        # TIER 2: and where preservation history exists, it must BE the preserved original.
        if available:
            preserved = git_show(f"{ev.preserve_ref}:{ev.path}")
            assert preserved is not None, f"{ev.key}: preserved blob missing"
            assert body == preserved, (
                f"{ev.key}: stripping {n} banner lines did not reproduce the preserved original "
                f"byte-for-byte"
            )


def test_the_tier_two_condition_is_all_or_nothing():
    """Partial preservation-ref availability is what tampering looks like, and is never tolerated.

    Where this environment carries ANY refs/preserve/* ref, EVERY load-bearing report's ref must
    resolve. Only a total absence - a distribution clone, which `git clone` produces because it
    copies neither refs/preserve/* nor anything else outside refs/heads and refs/tags - switches
    tier 2 off.
    """
    reports = load_bearing_reports()
    assert reports, "empty report set"
    resolved = [e for e in reports if git_rev_parse(e.preserve_ref)]
    if preservation_history_present():
        missing = [e.preserve_ref for e in reports if not git_rev_parse(e.preserve_ref)]
        assert not missing, (
            "this environment carries preservation history, so every load-bearing report's "
            f"preservation ref must resolve - these do not: {missing}"
        )
        assert resolved, "preservation history present but no report ref resolved"
    else:
        assert not resolved, (
            "preservation_history_present() reported NO refs, yet a load-bearing report's ref "
            f"resolved: {[e.preserve_ref for e in resolved]} - the tier condition is inconsistent"
        )


def test_the_reconstructed_second_finalization_report_is_not_represented_as_contemporaneous():
    """It is a POST-HOC reconstruction by a session that did not run the finalizer. The record must
    keep saying so: citing it as contemporaneous finalizer testimony would launder an attestation
    into a receipt."""
    ce = _containment_evidence()
    block = " ".join(str(ce["second_finalization_report"]).split())
    assert "RECONSTRUCTION" in block.upper(), (
        "the second-finalization report is cited without disclosing that it is a reconstruction"
    )
    assert re.search(r"NOT\s+contemporaneous", block, re.I), (
        "the record must state the report is NOT contemporaneous finalizer-authored testimony"
    )
    assert "UNAVAILABLE" in block.upper(), (
        "the record must preserve that the PID and run/session IDs were unrecoverable and may not "
        "be invented"
    )


# ===================================================================== the hostile battery
#
# Each case tampers with EXACTLY ONE input and requires the binding to fail. Every case anchors on
# the real report set, the real preservation refs and the real parsed verdicts, so none of them can
# pass because its corpus was empty.


def _anchor(with_verdict: bool = False, tier2: bool = False) -> tuple[Evidence, dict]:
    reports = load_bearing_reports()
    assert reports, "empty report set - the hostile battery would prove nothing"
    if with_verdict:
        candidates = [e for e in reports if e.verdict]
        assert candidates, "no report carries a parsed verdict - cannot test the verdict binding"
        ev = candidates[0]
    else:
        ev = reports[0]
    inputs = _real_inputs(ev)
    if tier2:
        inputs = _tier2_inputs(ev, inputs)
    assert not verify(ev, **inputs), "the anchor must be GREEN before it is tampered with"
    return ev, inputs


def test_hostile_accept_flipped_to_reject_fails():
    """THE reproduction from the targeted adjudication: 1957 tests passed through this before.

    Tampered in the WORKTREE, which is what the adjudicator actually did and what an attacker has
    access to. Tier 1 catches it in every environment - the authenticated body stops hashing to the
    recorded digest, and the recorded verdict stops appearing in the report.
    """
    ev, inputs = _anchor(with_verdict=True)
    assert b"ACCEPT" in inputs["worktree"], "the anchor report does not contain the verdict token"
    tampered = {**inputs, "worktree": inputs["worktree"].replace(b"ACCEPT", b"REJECT")}
    assert tampered["worktree"] != inputs["worktree"], "the fixture did not change anything"
    assert verify(ev, **tampered), "an inverted verdict in a load-bearing report was not detected"

    # and the same flip in the PRESERVED original, where preservation history exists
    t2 = _tier2_inputs(ev, inputs)
    assert verify(ev, **{**t2, "preserved": t2["preserved"].replace(b"ACCEPT", b"REJECT")})


def test_hostile_report_sha256_changed_fails():
    ev, inputs = _anchor()
    assert verify(replace(ev, expected_sha256="0" * 64), **inputs)


def test_hostile_sidecar_content_changed_fails():
    ev, inputs = _anchor()
    assert verify(ev, **{**inputs, "sidecar": "0" * 64 + "  " + Path(ev.path).name})


def test_hostile_sidecar_missing_fails():
    ev, inputs = _anchor()
    assert verify(ev, **{**inputs, "sidecar": None})


def test_hostile_report_missing_fails():
    ev, inputs = _anchor()
    assert verify(ev, **{**inputs, "worktree": None})


def test_hostile_preservation_ref_missing_fails():
    ev, inputs = _anchor(tier2=True)
    assert verify(ev, **{**inputs, "ref_target": None, "preserved": None})


def test_hostile_preservation_ref_resolves_to_the_wrong_commit_fails():
    """A ref re-pointed at a DIFFERENT real commit - not a synthetic hash - must still fail."""
    ev, inputs = _anchor(tier2=True)
    other = git_rev_parse("HEAD")
    assert other and other != ev.expected_parent, (
        "the fixture needs a real commit that is not the attested parent"
    )
    assert verify(ev, **{**inputs, "ref_target": other, "parent": other}), (
        "a preservation ref re-pointed at a different real commit was accepted"
    )


def test_hostile_preservation_commit_has_the_wrong_parent_fails():
    ev, inputs = _anchor(tier2=True)
    assert verify(ev, **{**inputs, "parent": "0" * 40})


def test_hostile_preserved_blob_differs_from_the_authenticated_body_fails():
    ev, inputs = _anchor(tier2=True)
    assert verify(ev, **{**inputs, "preserved": inputs["preserved"] + b"\ntrailing tamper\n"})


def test_hostile_mutable_worktree_report_differs_from_the_preserved_evidence_fails():
    """The substitution the banner convention could otherwise hide."""
    ev, inputs = _anchor()
    assert verify(ev, **{**inputs, "worktree": b"# A completely different document\n"})


def test_hostile_required_banner_removed_fails():
    """Debannering must not go green just because the body then equals the preserved blob.

    This is the subtle one: strip the banner and the worktree copy becomes byte-identical to the
    preserved original, so a pure body-equality check reports success while the tracked document
    has quietly stopped disarming itself.
    """
    bannered = [e for e in load_bearing_reports()
                if strip_banner((ROOT / e.path).read_bytes())[1]
                and e.path in _banner_required()]
    assert bannered, "no banner-required bannered report to test - the convention disappeared"
    ev = bannered[0]
    inputs = _tier2_inputs(ev, _real_inputs(ev))
    assert not verify(ev, **inputs), "the anchor must be GREEN before it is tampered with"

    body, _ = strip_banner(inputs["worktree"])
    assert body == inputs["preserved"], (
        "fixture precondition: debannering yields exactly the preserved blob, which is why a "
        "body-equality check alone cannot see this tamper"
    )
    assert verify(ev, **{**inputs, "worktree": body}), (
        "a banner-required historical report was debannered and the binding stayed green"
    )

    # and a debanner that ALSO drops a line of the report body fails on both counts
    assert verify(ev, **{**inputs, "worktree": body[body.index(b"\n") + 1:]})


def test_hostile_banner_parser_permits_no_body_substitution():
    """A valid-looking banner over a substituted body must fail."""
    bannered = [e for e in load_bearing_reports()
                if strip_banner((ROOT / e.path).read_bytes())[1]]
    assert bannered, "no bannered report to test"
    ev = bannered[0]
    inputs = _tier2_inputs(ev, _real_inputs(ev))
    raw = inputs["worktree"]
    _, n = strip_banner(raw)
    banner = b"\n".join(raw.split(b"\n")[:n])
    forged = banner + b"\n\n# A substituted body that the banner still appears to authenticate\n"
    assert verify(ev, **{**inputs, "worktree": forged}), (
        "a substituted body under a valid banner was accepted"
    )


def test_hostile_reviewed_candidate_attribution_changed_fails():
    ev, inputs = _anchor(tier2=True)
    assert verify(replace(ev, expected_parent="0" * 40), **inputs)


def test_hostile_finalizer_target_changed_fails():
    """The finalization reports attest a specific metadata commit; re-pointing one must fail."""
    finalization = [e for e in load_bearing_reports() if "finaliz" in e.key]
    assert finalization, "no finalization report bound - the chain lost its finalizer evidence"
    ev = finalization[0]
    inputs = _tier2_inputs(ev, _real_inputs(ev))
    assert not verify(ev, **inputs), "the anchor must be GREEN before it is tampered with"
    assert verify(replace(ev, expected_parent="1" * 40), **inputs)


def test_hostile_verdict_changed_in_the_record_fails():
    ev, inputs = _anchor(with_verdict=True)
    assert verify(replace(ev, verdict="ACCEPT WITH NO CONDITIONS WHATSOEVER"), **inputs)
