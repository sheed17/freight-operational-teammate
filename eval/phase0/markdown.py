"""A strict markdown-table parser.

The frozen corpus is markdown. Parsing it loosely is how a probe ends up examining nothing while
reporting success. This parser therefore: requires a header row it can name, counts every candidate
row, and RECORDS rows it could not parse as ``unmatched`` rather than skipping them — the caller's
``require_population()`` then turns any unmatched row into a hard failure.
"""

from __future__ import annotations

from pathlib import Path


def _split_row(line: str) -> list[str]:
    cells = line.split("|")
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _is_separator(line: str) -> bool:
    body = line.replace("|", "").replace(":", "").replace("-", "").replace(" ", "")
    return body == "" and "-" in line and "|" in line


def parse_tables(path: Path) -> list[dict]:
    """Return every pipe table in the file as {'headers': [...], 'rows': [ [cells] ], 'line_nos': []}."""
    tables: list[dict] = []
    lines = path.read_text(encoding="utf-8").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            headers = _split_row(line)
            rows, line_nos = [], []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                if not _is_separator(lines[j]):
                    rows.append(_split_row(lines[j]))
                    line_nos.append(j + 1)
                j += 1
            tables.append({"headers": headers, "rows": rows, "line_nos": line_nos, "path": path})
            i = j
        else:
            i += 1
    return tables


def find_table(path: Path, *required_headers: str) -> dict:
    """The one table in `path` whose headers include all of `required_headers`.

    Raises when absent or ambiguous. A probe that cannot find its table must fail, not return [].
    """
    matches = []
    for t in parse_tables(path):
        norm = [clean(h).lower() for h in t["headers"]]
        if all(any(r.lower() == n or r.lower() in n for n in norm) for r in required_headers):
            matches.append(t)
    if not matches:
        raise LookupError(
            f"No table in {path.name} has headers {required_headers}. "
            f"Found tables with headers: {[t['headers'] for t in parse_tables(path)]}"
        )
    if len(matches) > 1:
        raise LookupError(f"{len(matches)} tables in {path.name} match headers {required_headers}; ambiguous.")
    return matches[0]


def clean(cell: str) -> str:
    """Strip the corpus's emphasis markup (### ** ` *) to get at the value."""
    out = cell.replace("###", "").replace("**", "").replace("`", "")
    return out.strip().strip("*").strip()


def column(table: dict, name: str) -> int:
    """Index of the column whose header matches `name`. Raises rather than returning -1."""
    for idx, h in enumerate(table["headers"]):
        if clean(h).lower() == name.lower():
            return idx
    for idx, h in enumerate(table["headers"]):
        if name.lower() in clean(h).lower():
            return idx
    raise LookupError(f"No column {name!r} in headers {table['headers']}")
