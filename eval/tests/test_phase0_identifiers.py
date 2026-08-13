"""U0.6 - canonical identifier resolution.

Prevents recurrence of the invented `AC-SEC-000` completion oracle (planning review M-1). A
completion oracle must resolve to a canonical acceptance case; otherwise the unit can never be
proven done, and will be marked done anyway.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import planning_corpus

# Reviews may NAME a defect. Naming a defect is not using it. DISCOVERED (H-6), not typed.
def _review_docs() -> set[str]:
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
    from control import inventory as _inv
    names = {p.rsplit("/", 1)[-1] for p in _inv.implementation_review_documents()}
    assert len(names) >= 3, "review population collapsed"
    return names


REVIEW_DOCS = _review_docs()


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
        assert path.name in REVIEW_DOCS, (
            f"{path.name} references AC-SEC-000, which does not exist. Only a REVIEW may name it, "
            f"and only as the finding it was (M-1)."
        )
        assert "DID NOT EXIST" in text or "invented" in text, (
            f"{path.name} names AC-SEC-000 without marking it as the defect it was"
        )


def test_u03_completion_oracle_resolves():
    """The specific repair: U0.3's oracle is now the real frozen case."""
    pr = (Path(__file__).resolve().parents[2] / "docs" / "implementation" / "pr-sequence.md").read_text()
    u03 = next(line for line in pr.split("\n") if "U0.3**" in line and line.startswith("|"))
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


# --------------------------------------------------------------------------- P5 id correspondence
# ### M-5 RECURRED IN A SHAPE THE NAMESPACE GUARD ABOVE CANNOT SEE, AND THIS IS THE GUARD FOR IT.
# `test_no_duplicate_or_conflicting_unit_namespace` catches two documents using DIFFERENT ids for the
# same work (T2.1 vs U2.1). It cannot catch two documents using the SAME id for DIFFERENT work, and
# that is what happened to P5: IMPLEMENTATION-REGISTRY.yaml recorded U5.1/U5.2 as two BUILT,
# certified and finalized G2 units, while pr-sequence.md and current-to-target-gap-matrix.md used the
# same two ids for the transactional outbox and the dedup inbox, neither of which exists. Every id
# resolved, every reference was declared, and the whole suite was green - because nothing anywhere
# compared what an id MEANS in one authority against what it means in the other.
#
# ### BOTH SIDES ARE DERIVED, NEITHER IS RESTATED. The registry side is parsed out of the P5 unit's
# `sub_units` (built) and `planned_sub_units` (unbuilt) records. The plan side is parsed out of
# pr-sequence.md's `**P5:**` line and the gap matrix's own table rows. The node then asserts four
# things, and each one independently would have gone red on the collision:
#   1. no id is both BUILT and PLANNED - the id-reuse defect itself;
#   2. the id SETS agree exactly, in both directions - so neither authority can gain or drop a unit;
#   3. each id's pinned `plan_phrase` appears in THAT id's segment of the P5 line and in NO other
#      id's segment - so the ids cannot be permuted, which is the exact collision;
#   4. each gap-matrix row whose Task cell names only P5 units carries the `Depends on` set the
#      registry records for those units - so the dependency edges cannot drift either. This is what
#      makes U5.3 -> U5.7/U5.8 (a lower unit depending on higher ones) a checked fact rather than a
#      typo waiting to be tidied away.
def _p5_registry_records() -> tuple[dict, dict, dict]:
    """(built_phrases, planned_phrases, depends_on) keyed by sub-unit id, from the registry."""
    import yaml

    registry = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docs" / "implementation"
         / "IMPLEMENTATION-REGISTRY.yaml").read_text(encoding="utf-8")
    )
    p5 = next(u for u in registry["units"] if u["unit_id"] == "P5")
    built = {s["sub_unit_id"]: s["plan_phrase"] for s in p5["sub_units"]}
    planned = {s["sub_unit_id"]: s["plan_phrase"] for s in p5["planned_sub_units"]}
    deps = {s["sub_unit_id"]: set(s["depends_on"])
            for s in list(p5["sub_units"]) + list(p5["planned_sub_units"])}
    return built, planned, deps


def _p5_plan_segments() -> dict[str, str]:
    """Each `U5.N`'s own stretch of pr-sequence.md's `**P5:**` line, id -> concatenated text."""
    import re

    impl = Path(__file__).resolve().parents[2] / "docs" / "implementation"
    line = next(l for l in (impl / "pr-sequence.md").read_text(encoding="utf-8").split("\n")
                if l.startswith("**P5:**"))
    hits = list(re.finditer(r"\bU5\.\d+\b", line))
    assert hits, "the `**P5:**` line names no unit at all - this guard would pass vacuously"
    segments: dict[str, str] = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(line)
        segments[m.group()] = segments.get(m.group(), "") + line[m.end():end]
    return segments


def test_the_p5_unit_ids_name_the_same_work_in_the_registry_and_in_the_plan():
    import re

    built, planned, deps = _p5_registry_records()
    collisions = built.keys() & planned.keys()
    assert not collisions, (
        f"P5 sub-unit id(s) recorded as BUILT and as PLANNED at the same time: {sorted(collisions)}."
        f"\nA certified unit's id may never be reused for unbuilt work - that is the defect this "
        f"node exists for. Reassign the planned deliverable to an unused id."
    )
    registry_phrases = {**built, **planned}
    assert len(registry_phrases) >= 8, (
        f"only {len(registry_phrases)} P5 sub-unit records - the registry population collapsed and "
        f"this node would assert over almost nothing"
    )

    segments = _p5_plan_segments()
    missing_from_plan = sorted(registry_phrases.keys() - segments.keys())
    missing_from_registry = sorted(segments.keys() - registry_phrases.keys())
    assert not missing_from_plan and not missing_from_registry, (
        f"P5 unit ids disagree between IMPLEMENTATION-REGISTRY.yaml and pr-sequence.md:\n"
        f"  in the registry, absent from the plan: {missing_from_plan}\n"
        f"  in the plan, absent from the registry: {missing_from_registry}"
    )

    wrong_work = []
    for uid, phrase in sorted(registry_phrases.items()):
        if phrase not in segments[uid]:
            wrong_work.append(
                f"{uid}: the registry says it is {phrase!r}; pr-sequence.md's P5 line says "
                f"{segments[uid].strip()[:90]!r}"
            )
        elsewhere = sorted(o for o, seg in segments.items() if o != uid and phrase in seg)
        if elsewhere:
            wrong_work.append(
                f"{uid}: its pinned phrase {phrase!r} also appears under {elsewhere} - an "
                f"ambiguous phrase cannot pin an id, because a swap would keep this node green"
            )
    assert not wrong_work, (
        "A P5 unit id names DIFFERENT WORK in the registry and in the plan:\n  "
        + "\n  ".join(wrong_work)
        + "\n\nThe registry records what was BUILT and certified; the plan records what is PLANNED. "
          "Certified history is immutable - remap the unbuilt deliverable to an unused id, never "
          "the other way round."
    )

    matrix = (Path(__file__).resolve().parents[2] / "docs" / "implementation"
              / "current-to-target-gap-matrix.md").read_text(encoding="utf-8")
    checked, dep_errors = 0, []
    for row in matrix.split("\n"):
        cells = row.split("|")
        if len(cells) < 10 or not re.match(r"^\s*\d+\s*$", cells[1]):
            continue
        tasks = set(re.findall(r"\bU\d+\.\d+\b", cells[7]))
        if not tasks or tasks - registry_phrases.keys():
            continue                      # not a row whose Task cell is P5 units and nothing else
        checked += 1
        stated = set(re.findall(r"\bU\d+\.\d+\b", cells[8]))
        expected = set().union(*(deps[t] for t in tasks))
        if stated != expected:
            dep_errors.append(
                f"gap-matrix row {cells[1].strip()} (Task {sorted(tasks)}): the matrix says it "
                f"depends on {sorted(stated)}; the registry says {sorted(expected)}"
            )
    assert checked >= 3, (
        f"only {checked} gap-matrix rows carry a P5 Task cell - the dependency half of this node "
        f"would assert over almost nothing"
    )
    assert not dep_errors, (
        "P5 dependency edges disagree between the gap matrix and the registry:\n  "
        + "\n  ".join(dep_errors)
        + "\n\nThe edge is the thing that breaks when ids are reassigned: U5.3's prerequisites were "
          "left pointing at two units that no longer exist as planned."
    )
