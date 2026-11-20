"""
Split raw scraped pages (data/raw/*.txt) into retrieval-sized chunks with metadata.
Each raw file starts with a small header:
    SOURCE_URL: <url>
    TITLE: <title>
    FETCHED: <date>
    ---
    <body text>
"""
import json
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "chunks.jsonl"

CHUNK_WORDS = 150   # ~ a couple hundred tokens per chunk
OVERLAP_WORDS = 30


def parse_file(path: Path):
    text = path.read_text(encoding="utf-8")
    header, _, body = text.partition("---\n")
    meta = {}
    for line in header.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, body.strip()


def split_into_paragraphs(body: str):
    # FIX (2026-09-21, see REPORT2.md): the original blank-line-only split
    # (r"\n\s*\n") worked on the WebFetch-paraphrased text used for the first
    # 19 pages (which happened to contain blank lines) but produces almost no
    # splits at all on real BeautifulSoup-scraped text from fetch_utils.py,
    # which separates block-level elements with single "\n" characters --
    # that made most pages collapse into one giant "paragraph" and defeated
    # chunk_paragraphs()'s word-budget logic entirely (confirmed by Claude
    # Code's REPORT2.md: 79-page corpus -> only 82 chunks, many oversized
    # enough to trip Groq's rate limit). Splitting on any run of newlines
    # keeps each line/block as its own unit instead.
    parts = re.split(r"\n+", body)
    return [p.strip() for p in parts if p.strip()]


def share_lead_ins(paragraphs, chunk_words=CHUNK_WORDS):
    """Write a table's lead-in once per group of rows instead of once per row.

    Converted documents write every table row as "<lead-in> | <row>", where the
    lead-in is the text before the table, so the reader of a single row knows
    what it belongs to. When the lead-in is long, it swamps the rows: in the
    2026 holiday list each row carries a 40-word "In terms of Office Memorandum
    F. No. 12/2/2023-JCA ..." prefix, a 135-word chunk holds two holidays, and
    the reranker cannot tell the chunk with Holi in it from the others (it
    ranked 8th). Repeated lead-ins are 16% of the documents' words.

    Consecutive rows with the same lead-in become paragraphs of
    "<lead-in> | <row> | <row> ...", each at most chunk_words long, so every
    chunk still starts with the lead-in and no row loses it.
    """
    out, lead, rows = [], None, []

    def flush():
        if not rows:
            return
        if len(rows) == 1:
            out.append(f"{lead} | {rows[0]}")
            return
        group = []
        for row in rows:
            if group and len(f"{lead} | {' | '.join(group + [row])}".split()) > chunk_words:
                out.append(f"{lead} | {' | '.join(group)}")
                group = []
            group.append(row)
        out.append(f"{lead} | {' | '.join(group)}")

    for para in paragraphs:
        this_lead, sep, row = para.partition(" | ")
        if sep and this_lead == lead:
            rows.append(row)
            continue
        flush()
        lead, rows = (this_lead, [row]) if sep else (None, [])
        if not sep:
            out.append(para)
    flush()
    return out


def chunk_paragraphs(paragraphs, chunk_words=CHUNK_WORDS, overlap_words=OVERLAP_WORDS):
    """Pack paragraphs into ~chunk_words-sized chunks with overlap.

    FIX (2026-09-21): the original version could only ever split *between*
    paragraphs, so a single unusually long paragraph (common on real scraped
    pages -- e.g. a dense notice or a table flattened to text with no
    internal newlines) would sail straight through as one oversized chunk
    with no upper bound at all. There is now a hard word-window fallback:
    any paragraph longer than chunk_words is itself split into fixed-size,
    overlapping windows, so no chunk this function emits can ever exceed
    chunk_words regardless of how the source text is laid out.
    """
    chunks = []
    current_words = []

    def flush():
        if current_words:
            chunks.append(" ".join(current_words))

    for para in paragraphs:
        para_words = para.split()

        if len(para_words) > chunk_words:
            # Oversized paragraph on its own: flush whatever's pending, then
            # window this paragraph into chunk-sized pieces directly.
            flush()
            current_words = []
            start = 0
            step = max(chunk_words - overlap_words, 1)
            while start < len(para_words):
                window = para_words[start:start + chunk_words]
                chunks.append(" ".join(window))
                start += step
            continue

        if len(current_words) + len(para_words) > chunk_words and current_words:
            chunks.append(" ".join(current_words))
            # start next chunk with overlap from the tail of this one
            current_words = current_words[-overlap_words:] if overlap_words else []
        current_words.extend(para_words)

    flush()
    return chunks


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_chunks = []
    for path in sorted(RAW_DIR.glob("*.txt")):
        meta, body = parse_file(path)
        paragraphs = share_lead_ins(split_into_paragraphs(body))
        chunks = chunk_paragraphs(paragraphs)
        for i, chunk_text in enumerate(chunks):
            all_chunks.append({
                "id": f"{path.stem}::{i}",
                "text": chunk_text,
                "source_url": meta.get("source_url", ""),
                "title": meta.get("title", path.stem),
                "fetched": meta.get("fetched", ""),
                "file": path.name,
            })

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_chunks)} chunks from {len(list(RAW_DIR.glob('*.txt')))} files to {OUT_PATH}")


if __name__ == "__main__":
    main()
