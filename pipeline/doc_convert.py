"""
Turn a PDF into chatbot-ready plain text using Docling, which understands page
layout, reads tables as real rows/columns, and OCRs scanned pages.

Needs the separate PDF environment (see README): Docling pulls in large
model files, so it's kept out of the main app's Python environment.

Tables are written as one self-contained line per row, e.g.
    Fees per year: Tuition Fee — First Year: 125000; Second Year: 125000
because chunk.py cuts text into ~150-word pieces and a bare row like
"| 1 | Tuition Fee | 125000 |" would lose its column headings. Plain-text
extraction of this kind of table caused a real wrong answer before
(a department name landed next to another department's programmes).
"""
import math
import re

_converter = None
_SERIAL_COL = re.compile(r"^(s\.?\s*n\.?|sn|sr\.?\s*no\.?|sl\.?\s*no\.?|no\.?|#)$", re.I)

# Academic calendars carry a month-by-month day grid: columns named after
# months and weekdays, cells holding bare day numbers. Each row became a line
# like "December 2026.WED: 2; December 2026.THU: 3; ..." -- dozens per
# calendar, answering nothing, and competing with the real lines for the
# reranker's attention.
_MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_WEEKDAYS = r"sun|mon|tue|wed|thu|fri|sat"
_MONTH_COL = re.compile(rf"^({_MONTHS})[a-z]*\.?\s*\d{{0,4}}(\.({_WEEKDAYS})[a-z]*)?$", re.I)

# The institute letterhead sits above a document's first table, so it becomes
# the "section" context and gets prefixed to every row of it. It labels no
# table, and its Hindi line comes through as mojibake from a legacy font
# ("fo'os'oj¸;k jk\"Vªh; izkS|ksfxdh laLFkku] Ukkxiwj").
_LETTERHEAD = re.compile(r"national institute of technology", re.I)
_GARBLED_WORD = re.compile(r"[a-z]*['\"¸ª;|\]]+[a-z'\"¸ª;|\]]*", re.I)


def _get_converter():
    global _converter
    if _converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions()
        opts.do_ocr = True
        opts.do_table_structure = True
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
    return _converter


def _clean(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def _lead_sentence(paragraph: str, max_words: int = 25) -> str:
    first = re.split(r"(?<=[a-z]{3}[.!?])\s+(?=[A-Z])", paragraph.strip())[0]  # not at "B. Tech."
    words = first.split()
    return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")


def _clean_context(text: str) -> str:
    """Strip the letterhead and mis-decoded non-Latin words from table context."""
    if _LETTERHEAD.search(text):
        return ""
    kept = [w for w in text.split() if not (_GARBLED_WORD.fullmatch(w) and not w.isalpha())]
    return re.sub(r"\s+", " ", " ".join(kept)).strip(" ,;|-")


def _is_day_grid(df) -> bool:
    """True for a calendar's month-day grid (see _MONTH_COL): columns named
    after months and cells holding bare day numbers. Its rows state no fact,
    so the whole table is skipped."""
    headers = [_clean(c) for c in df.columns]
    if len(headers) < 3:
        return False
    if sum(1 for h in headers if _MONTH_COL.match(h)) < len(headers) * 0.6:
        return False
    values = [v for v in (_clean(v) for _, row in df.iterrows() for v in row.tolist()) if v]
    if not values:
        return True
    day_numbers = sum(1 for v in values if re.fullmatch(r"\d{1,2}(\s*\([A-Za-z]{3}\))?", v))
    return day_numbers >= len(values) * 0.7


def _table_rows(df, context: str):
    headers = [_clean(c) for c in df.columns]
    has_header = any(h and not h.isdigit() for h in headers)
    lines = []
    for _, row in df.iterrows():
        cells = []
        for i, (h, v) in enumerate(zip(headers, row.tolist())):
            v = _clean(v)
            if not v or _SERIAL_COL.match(h or "-"):
                continue
            if i == 0 and re.fullmatch(r"\d{1,3}\.?", v):
                continue  # bare serial number in an unlabelled first column
            if cells and cells[-1] == (h, v):
                continue  # merged cell repeated under the same heading
            cells.append((h, v))
        if not cells:
            continue
        if has_header:
            h0, v0 = cells[0]
            # Keep the first column's own heading when it reads as a label: the
            # academic calendar's exam table is headed "EXAMINATIONS.Slot" with
            # values A-H, and dropping that heading left eight rows that looked
            # like eight conflicting End Sem dates (the LLM duly answered
            # "7-14 Dec" instead of "7-15 Dec"). A heading containing digits is
            # usually data from a misparsed header row (a date, an amount), so
            # it is not used as a label.
            label = f"{h0}: {v0}" if h0 and h0 != v0 and not re.search(r"\d", h0) else v0
            rest = "; ".join(f"{h}: {v}" if h and h != v else v for h, v in cells[1:])
            line = f"{label} — {rest}" if rest else label
        else:
            line = " | ".join(v for _, v in cells)
        lines.append(f"{context}: {line}" if context else line)
    return lines


def pdf_to_text(path, max_pages: int = 25):
    """Return (title, text) for a PDF file path (first max_pages pages only)."""
    from docling_core.types.doc import SectionHeaderItem, TableItem, TextItem

    doc = _get_converter().convert(str(path), page_range=(1, max_pages)).document
    lines, title, section, lead = [], "", "", ""
    for item, _level in doc.iterate_items():
        if isinstance(item, TableItem):
            try:
                df = item.export_to_dataframe(doc=doc)
            except TypeError:
                df = item.export_to_dataframe()
            if _is_day_grid(df):
                continue
            # Rows carry the table's lead-in sentence as well as its heading:
            # e.g. one fee PDF has identical-looking tables for OPEN/OBC and
            # SC/ST students, distinguished only by the sentence above them.
            parts = (_clean_context(lead), _clean_context(section))
            context = " | ".join(p for p in parts if p)
            lines.extend(_table_rows(df, context))
        elif isinstance(item, (SectionHeaderItem, TextItem)):
            text = _clean(item.text)
            if not text:
                continue
            if isinstance(item, SectionHeaderItem):
                section = text[:80].rstrip(": ")
                if not title and len(text.split()) >= 3:
                    title = text[:120]
            elif len(text.split()) >= 8:
                lead = _lead_sentence(text)
            lines.append(text)
    return title, "\n".join(lines)
