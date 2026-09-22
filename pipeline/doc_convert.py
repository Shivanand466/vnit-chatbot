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
            label = cells[0][1]
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
            # Rows carry the table's lead-in sentence as well as its heading:
            # e.g. one fee PDF has identical-looking tables for OPEN/OBC and
            # SC/ST students, distinguished only by the sentence above them.
            context = " | ".join(p for p in (lead, section) if p)
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
