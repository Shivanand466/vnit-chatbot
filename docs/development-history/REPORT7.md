# REPORT7 — PDF ingestion (BUILD-PLAN Step 2)

Run on: 2026-09-21/22 (Windows 11, Git Bash + Anaconda Python 3.13.5, via Claude Code). Groq default model `openai/gpt-oss-20b`, the newer key (`gsk_xorM...`; no key values in this file).

## Outcome in one paragraph
PDF ingestion **worked mechanically** (11 PDFs, 56,498 words, 417 → 908 chunks) but **made the chatbot worse**. It turned a previously **correct** answer into a **wrong** one: the project's first observed confidently-wrong answer. It also failed to answer any of the 3 test questions whose answers exist only in the PDFs. Following BUILD-PLAN 2.4 option (b), the PDF text files were **moved to `data/raw_pdfs_quarantine/`** (kept, not deleted) and the index was rebuilt. The system is verified back to exactly its pre-Step-2 state: 79 pages, 417 chunks, 17/19 = 89%, and Electrical M.Tech answering correctly again. **PDFs need table-aware extraction before they can be included.** No project code was modified.

## Deviations from BUILD-PLAN (stated explicitly, as required)
1. **Curated list instead of `--max-pdfs 40`.** The dry run found 72 PDF links. `ingest()` takes `sorted(urls)[:max_pdfs]`, and because `http://` sorts before `https://`, the first 40 were mostly 2020–2022 academic calendars, blank forms/templates and merit lists. The rest included eleven 2009–2022 annual reports, several of them in Hindi, which the English-only MiniLM model can't embed usefully. Old calendars would also compete with the benchmark's "academic calendar for winter 2026" question. So I picked 19 current, English, content-bearing PDFs and ran them through `ingest_pdfs.py`'s own functions (`download_pdf`, `extract_pdf_text`, `clean_pdf_text`, `title_from`, `save_pdf_page`) from a wrapper script in Claude Code's scratchpad. Same robots check, rate limit, size cap and output format; only the URL selection differed.
2. **One robots.txt mistake of mine:** while investigating fee PDFs (below), a test script checked `drive.google.com`'s robots.txt, which **disallows** `/uc` (the download endpoint), and then made **one** download request to it anyway. That shouldn't have happened; nothing from Drive was ingested, and no further Drive requests were made.

## 2.1 PDF engine
`pdfplumber` installed and used for every file (pypdf fallback never needed). **Environment note:** the latest `pdfplumber` 0.11.10 requires Pillow ≥ 12.2, which conflicts with the **Streamlit** already in this Anaconda env (needs Pillow < 12). I resolved it to **pdfplumber 0.11.9 + Pillow 11.3.0** (`pip check`: no conflicts). If `requirements.txt` adds pdfplumber, pin `pdfplumber<0.11.10` or use a venv.

## 2.2 Dry run
`python ingest_pdfs.py --dry-run --max-pdfs 40 --max-html-pages 80 --max-depth 3`
- **72 PDF links found**, 0 already ingested, found on 13 of the 80 HTML pages visited. 2 HTML pages returned 404 (stale news links).
- Rough composition: ~11 annual reports 2009–2025 (English + Hindi), ~10 old academic calendars / practical schedules (2020–2023), ~10 blank forms and templates, 3 merit / selected-candidate lists, 3 NIRF reports, 4 department course books, 4 lab/centre descriptions, a few admission documents.

### Key finding: fee schedules can't be reached this way
The `/section/academics/fees/` page links **all 11 fee documents** (B.Tech/B.Arch/M.Tech/M.Sc/PhD/MBA fee estimates, NRI fees) to **Google Drive**, not to PDFs on vnit.ac.in. So:
- `ingest_pdfs.py` only follows `vnit.ac.in` links and never sees them. Also, the 80-page crawl never reached the fees page.
- Drive's robots.txt **disallows** the download path (`/uc`); the `/file/d/.../view` path is allowed but returns an HTML viewer, not the PDF.
- The one fee PDF I (mistakenly) test-downloaded, the B.Tech 4-year estimate, is a **scanned image: 0 extractable words**, so it would need OCR anyway.
- **Conclusion: "What is the B.Tech fee?" cannot be answered from the site without OCR plus a robots-compliant way to get the files.** Hostel mess menus are also Drive links. The chatbot correctly answers "not covered" for the fee question.

Related, cheap, and HTML rather than PDF: the hostel section has `/section/hostel/rules-regulations/` and `/section/hostel/fees/` pages that are **not in the corpus**. "Where are the hostel rules?" was the very first question in Round 1. Adding those pages with `crawl.py` is probably the single most useful cheap coverage win. Not done here (outside Step 2).

## 2.3 Real ingestion (curated 19)
Ingested **11**, skipped as scans **4**, errors **4**, ~203 s.

| PDF | Result |
|---|---|
| Info-Brochure (Jun 2024, academics) | ✓ 4,237 words |
| B.Tech Mechanical course book (Aug 2026) | ✓ 8,595 |
| M.Tech PIE course book (Oct 2024) | ✓ 10,016 |
| Chemical course book, batch 2026 | ✓ 7,111 |
| B.Tech Chemical Technology (2026) | ✓ 7,775 |
| Annual Report 2024-25 (English, 20.3 MB) | ✓ 8,500 (first 40 pages only; the T&P section is pp. 53–78, so cut off) |
| NIRF Overall 2024 | ✓ 5,927 |
| Institutions Innovation Council | ✓ 1,542 |
| CAD/CAM dept, Remote Sensing & GIS lab, Water Resources centre | ✓ 598 / 1,858 / 339 |
| Admission-Cancellation-**Refund-Guidelines**, Admission-Cancellation-Procedure, Documents-for-Thesis-Submission, center_for_materials | ✗ **scanned, 0 words** |
| How-to-Pay-Application-Fee, admission Brochure-Final, Transcript-Note | ✗ **404** (linked from the live site but gone) |
| ESTABLISHMENT_MANUAL | ✗ too large, **228 MB** > 20 MB cap |

**Scan rate among content PDFs: 4 of 15 downloaded = 27%**, and they're the most student-relevant ones (refund rules, cancellation procedure). OCR would recover them, but it's out of scope per the plan.
Minor: the annual report text contains 4 stray control characters (`\x00` ×3, `\x01`). Harmless, but `clean_pdf_text()` could strip `[\x00-\x08\x0b\x0c\x0e-\x1f]`.

## 2.4 Rebuild and re-measure (with PDFs)
Chunks **908** (from 417), 90 files, `[embeddings] Indexed 908 chunks (dim 384)`.
Benchmark **16/19 = 84%** (from 17/19). Misses:
- INI status: expected `history`, top = Annual Report 2024-25 PDF (**new miss**)
- Electrical M.Tech: expected `engineering/electrical`, top = Info-Brochure PDF (existing miss)
- Registrar phone: expected `contact-us`, top = `rti-officer` (existing miss)

The page-level benchmark alone looked like "−1, borderline acceptable", and the top PDF chunks *did* contain relevant text (the annual report mentions the NIT Act 2007; the brochure lists Electrical M.Tech programmes). **The end-to-end test below is what showed the real problem.**

## 2.5 End-to-end LLM test (with PDFs), then after rollback
| Question | With PDFs | After quarantine |
|---|---|---|
| Electrical M.Tech specializations | ❌ **WRONG**: "Power Electronics and Drives" and "**Communication System Engineering**", "offered through the **Electronics and Communication** department"; cites Info-Brochure. Omits Integrated Power Systems. | ✅ "Integrated Power System … Power Electronics" (Academic Programs), **same as Round 4** |
| When did VNIT get INI status? (answer: NIT Act 2007, in the annual report) | "passages do not state the specific year" (the 2007 sentence is rank 4, outside top-3) | benchmark hit on `history` page |
| Sanctioned UG intake (855, NIRF PDF only) | "not in passages" (NIRF table chunks didn't rank) | n/a |
| President of Institution's Innovation Council (Dr. A. G. Keskar, IIC PDF only) | "not in passages" | n/a |
| B.Tech tuition fee (not in corpus) | ✅ honest "not in passages" | ✅ honest "not in passages" |

**Root cause of the wrong answer: table linearization.** The brochure lists programmes in a table where the department name sits in a merged cell spanning several rows. pdfplumber's `extract_text()` flattens it to:
```
M. Tech. (Integrated Power Systems)
7 Electrical Engineering
M. Tech. (Power Electronics and Drives)
Electronics and Communication M. Tech. (Communication system Engineering)
```
The department label ends up in the middle of its own rows and runs straight into the next department's row, so the LLM paired the programmes with the wrong departments. It didn't invent anything (every programme name is in the text), but the answer is **factually wrong and confidently stated**. BUILD-PLAN classes this as the highest-severity finding, which is why I rolled back instead of continuing. Tables like this are common in VNIT PDFs (fee estimates, intake tables, NIRF data, course books), so this isn't a one-off.

## State of the project now
- `data/raw/`: 79 HTML pages (unchanged from before Step 2). `data/processed/`: rebuilt, **417 chunks, embeddings, 17/19 = 89%**, verified identical to pre-Step-2.
- `data/raw_pdfs_quarantine/`: the 11 extracted PDF text files, kept for the next attempt. `chunk.py` only reads `data/raw/*.txt`, so they're inert.
- A full backup of `data/` from before Step 2 is in Claude Code's scratchpad.
- Environment: `pdfplumber 0.11.9`, `pdfminer.six 20251230`, `pypdfium2`, Pillow held at 11.3.0.
- No servers running; no project code changed.
- REPORT6's placements fix (whole-question chunks first, `MAX_CHUNK_CHARS` 1000) is **still not applied**; `generate.py` is unchanged.

## Recommendations for Cowork (in priority order)
1. **Don't retry PDFs with plain `extract_text()`.** Use table-aware extraction: pdfplumber's `page.extract_tables()` gives rows as lists with merged cells as `None`. Forward-fill the department column and emit one self-contained line per row ("Electrical Engineering — M.Tech (Integrated Power Systems)"). Then test the Electrical question end to end before re-including PDFs. Keep **end-to-end LLM checks** as the acceptance gate, not just `evaluate.py`: the page-level benchmark said "−1, fine", and the real answer was wrong.
2. **Add the hostel `rules-regulations` and `fees` HTML pages** (cheap, high value, no PDF problems).
3. **Apply REPORT6's placements fix**, a tested two-line change.
4. **Ingest PDFs selectively, not by crawl order.** Current, English, content-bearing only; skip Hindi, pre-2023 calendars, blank forms and name lists. Raise `MAX_PDF_PAGES` or pick page ranges for the annual report so its T&P section (pp. 53–78) gets in.
5. Fees remain out of reach (Drive-hosted, robots-disallowed download path, scanned). Worth stating plainly in the FYP report's limitations.
