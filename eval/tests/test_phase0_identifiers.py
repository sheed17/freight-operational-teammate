"""U0.6 - canonical identifier resolution.

Prevents recurrence of the invented `AC-SEC-000` completion oracle (planning review M-1). A
completion oracle must resolve to a canonical acceptance case; otherwise the unit can never be
proven done, and will be marked done anyway.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import planning_corpus


def test_the_probes_evaluate_real_populations():
    planning_corpus.canonical_acceptance_ids().require_population(minimum=100)
    planning_corpus.cited_acceptance_ids().require_population(minimum=20)


def test_every_cited_acceptance_id_resolves_to_the_frozen_corpus():
    """REG-5 / INV-P0-4. The guard that would have caught AC-SEC-000 on the day it was written."""
    canonical = set(planning_corpus.canonical_acceptance_ids().accepted)
    cited_ev = planning_corpus.cited_acceptance_ids()
    cited_ev.require_population()

    # The planning review REPORTS the defects it fixed, by name. Quoting a defect is not using it.
    reported_only = {"AC-SEC-000", "AC-MACH-2xx"}

    orphans = set()
    for token in cited_ev.accepted:
        if token in canonical:
            continue
        if token in reported_only:
            continue
        # The 105 checkpoint cases are declared by SCHEME, not enumerated. A derived id resolves.
        if planning_corpus.checkpoint_id_is_valid(token):
            continue
        orphans.add(token)

    assert not orphans, (
        f"Acceptance identifier(s) cited by the plan that do NOT exist in the frozen corpus:\n  "
        + "\n  ".join(sorted(orphans))
        + "\n\nAn oracle naming a test that does not exist is not an oracle (M-1)."
    )


def test_the_invented_id_appears_only_as_a_reported_finding():
    """AC-SEC-000 may be NAMED as the defect it was. It may never be USED as an oracle again."""
    impl = Path(__file__).resolve().parents[2] / "docs" / "implementation"
    for path in impl.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "AC-SEC-000" not in text:
            continue
        assert path.name == "implementation-planning-review.md", (
            f"{path.name} references AC-SEC-000, which does not exist. Only the review may name it, "
            f"and only as the finding M-1."
        )
        assert "DID NOT EXIST" in text


def test_u03_completion_oracle_resolves():
    """The specific repair: U0.3's oracle is now the real frozen case."""
    pr = (Path(__file__).resolve().parents[2] / "docs" / "implementation" / "pr-sequence.md").read_text()
    u03 = next(line for line in pr.split("\n") if line.startswith("| **U0.3**"))
    assert "AC-CKPT-6-missing" in u03
    assert "AC-SEC-000" not in u03
    canonical_source = (
        Path(__file__).resolve().parents[2]
        / "docs" / "specifications" / "acceptance" / "platform-safety-acceptance.md"
    ).read_text()
    assert "AC-CKPT-6-*" in canonical_source


def test_no_duplicate_or_conflicting_unit_namespace():
    """M-5: the gap matrix once said T2.1 where the PR sequence said U2.1, for the same work."""
    impl = Path(__file__).resolve().parents[2] / "docs" / "implementation"
    import re

    legacy = re.compile(r"(?<![A-Za-z])T\d+\.\d+(?![0-9])")
    offenders = {}
    for path in impl.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        hits = legacy.findall(text)
        if not hits:
            continue
        # The review may QUOTE the old namespace as the finding M-5. Naming a defect is not using it.
        if path.name == "implementation-planning-review.md" and "M-5" in text:
            continue
        offenders[path.name] = sorted(set(hits))
    assert not offenders, (
        f"legacy T* unit namespace still present: {offenders}\n"
        f"The gap matrix once said T2.1 where the PR sequence said U2.1, for the same work (M-5)."
    )


def test_every_referenced_unit_is_declared_by_the_pr_sequence():
    declared = set(planning_corpus.declared_units().accepted)
    referenced_ev = planning_corpus.referenced_units()
    referenced_ev.require_population()
    unknown = set(referenced_ev.accepted) - declared
    assert not unknown, (
        f"Unit(s) referenced but never declared in pr-sequence.md: {sorted(unknown)}"
    )
