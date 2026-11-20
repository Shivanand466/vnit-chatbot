"""
Put every table cell from VNIT's documents into a small SQLite database.

Why: fee amounts and exam dates live in tables, and a table row turned into a
sentence is a poor fit for passage search -- the M.Sc tuition row sits under a
lead-in that OCR turned into "Folr t orf VNIT, Nagpur.", so no search for
"M.Sc tuition" reaches it. TableRAG keeps document tables in a database and
answers table questions with a query; MARAUS gives numeric questions their own
agent. Here the agent gets a second kind of tool (tools.lookup_table): a
structured lookup, filtered by programme, gender, category and year, which it
can use alongside text search.

Docling already wrote every table row as one line of data/raw/doc_*.txt, in
one of two shapes (checked on real lines before writing this):

    <lead-in> | <caption>: <row header>: <row label> — <column>: <value>; <column>: <value>
    <lead-in> | <caption>: <row label> | <value> | <value>        (no column headers)

Each cell becomes one row of `facts`. The programme, gender, category, year of
study and academic year are read from the document's title, the lead-in and
the row label (slots.py, programme_terms.py), so a filter can find the M.Sc
fee sheet by its title even where OCR damaged the text around the table.

Rebuild after chunk.py / build_index.py:

    python build_facts.py
"""
import re
import sqlite3
import sys
from pathlib import Path

import query
import slots
from programme_terms import years

RAW = Path(__file__).parent.parent / "data" / "raw"
DB_PATH = Path(__file__).parent.parent / "data" / "processed" / "facts.db"

SCHEMA = """
CREATE TABLE facts (
    id INTEGER PRIMARY KEY,
    doc_url TEXT, title TEXT, date TEXT,
    lead_in TEXT, row_label TEXT, column TEXT, value TEXT, number REAL,
    programme TEXT, gender TEXT, category TEXT, study_year TEXT, academic_year TEXT
)
"""

_NIL = re.compile(r"^(nil|nill|free|waived)$", re.I)
_NUMBER = re.compile(r"^\d[\d,]*(?:\.\d+)?$")


def parse_number(value: str):
    """"1,25,000", "Rs. 32650/-", "₹ 7500.00", "*20000" -> float; "Nil" -> 0; else None."""
    v = re.sub(r"(?i)^(rs\.?|inr|₹)\s*", "", value.strip()).replace("₹", "")
    v = v.strip(" *#").removesuffix("/-").strip()
    if _NIL.match(v):
        return 0.0
    if _NUMBER.match(v):
        return float(v.replace(",", ""))
    return None


def parse_line(line: str):
    """One table line -> (lead_in, row_label, [(column, value), ...]), or None if it isn't one."""
    if " | " not in line:
        # A table with no paragraph before it has no lead-in either:
        # "<caption>: <row label> — <column>: <value>; <column>: <value>" (the
        # placement report's "Number of Companies Visited" row). Taken only in
        # that strict shape, with two cells or more, so prose with a dash is not.
        left, dash, right = line.partition(" — ")
        cells = right.split("; ")
        if not dash or ": " not in left or len(cells) < 2 or not all(": " in c for c in cells):
            return None
        lead_in, rest = "", line
    else:
        lead_in, rest = line.split(" | ", 1)
    if " — " in rest:
        left, right = rest.split(" — ", 1)
        label_part = left.rsplit(": ", 1)
        caption, row_label = (label_part if len(label_part) == 2 else ("", left))
        cells = []
        for cell in right.split("; "):
            if ": " in cell:
                column, value = cell.rsplit(": ", 1)
                cells.append((column.strip(), value.strip()))
    else:
        parts = [p.strip() for p in rest.split(" | ")]
        label_part = parts[0].rsplit(": ", 1)
        caption, row_label = (label_part if len(label_part) == 2 else ("", parts[0]))
        cells = [(f"column {i}", p) for i, p in enumerate(parts[1:], 1) if p]
    cells = [(c, v) for c, v in cells if v]
    if not cells or not row_label.strip():
        return None
    lead = lead_in.strip()
    if caption.strip():
        lead = f"{lead} | {caption.strip()}" if lead else caption.strip()
    return lead, row_label.strip(), cells


def _header(text: str) -> dict:
    head = {}
    for line in text.splitlines()[:8]:
        for key in ("SOURCE_URL", "TITLE", "FETCHED"):
            if line.startswith(f"{key}: "):
                head[key] = line[len(key) + 2:].strip()
    return head


def _tags(text: str) -> dict:
    tags = slots.extract(text)
    found = years(text)
    tags["academic_year"] = next(iter(found)) if len(found) == 1 else None
    return tags


def build():
    # Only documents that made it into the index: the privacy filter and the
    # exclusions of ingest_documents.py apply here too.
    indexed = {s["url"] for s in query.list_sources()}
    DB_PATH.unlink(missing_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute(SCHEMA)
    per_kind, documents = {}, 0
    for path in sorted(RAW.glob("doc_*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        head = _header(text)
        url, title = head.get("SOURCE_URL"), head.get("TITLE", "")
        if url not in indexed:
            continue
        rows = []
        for line in text.splitlines():
            parsed = parse_line(line)
            if not parsed:
                continue
            lead_in, row_label, cells = parsed
            tags = _tags(f"{title} {lead_in} {row_label}")
            for column, value in cells:
                rows.append((url, title, head.get("FETCHED", ""), lead_in, row_label, column, value,
                             parse_number(value), tags.get("programme"), tags.get("gender"),
                             tags.get("category"), tags.get("study_year"), tags["academic_year"]))
        if rows:
            documents += 1
            db.executemany("INSERT INTO facts (doc_url, title, date, lead_in, row_label, column, "
                           "value, number, programme, gender, category, study_year, academic_year) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            kind = _kind(title)
            per_kind[kind] = per_kind.get(kind, 0) + len(rows)
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    numeric = db.execute("SELECT COUNT(*) FROM facts WHERE number IS NOT NULL").fetchone()[0]
    db.close()
    print(f"{total:,} table cells from {documents} documents ({numeric:,} numeric) -> {DB_PATH}")
    for kind, n in sorted(per_kind.items(), key=lambda kv: -kv[1]):
        print(f"  {kind:<22} {n:>6,}")


def _kind(title: str) -> str:
    t = title.lower()
    for kind, words in (("hostel fees", ("hostel",)), ("fees", ("fee",)),
                        ("calendar / timetable", ("calendar", "timetable", "time table", "exam")),
                        ("scholarship", ("scholarship",)), ("placement", ("placement",)),
                        ("admission", ("admission", "brochure"))):
        if any(w in t for w in words):
            return kind
    return "other"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
