#!/usr/bin/env python3
"""Convert PDF files to Markdown. Requires: pip install pymupdf"""

import sys
import os
import re
import fitz  # pymupdf


def pdf_to_md(pdf_path: str, out_path: str | None = None) -> str:
    out_path = out_path or os.path.splitext(pdf_path)[0] + ".md"
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc, 1):
        blocks = page.get_text("dict")["blocks"]
        lines = []

        for block in blocks:
            if block["type"] != 0:  # skip images
                continue
            for span_line in block["lines"]:
                text = " ".join(s["text"] for s in span_line["spans"]).strip()
                if not text:
                    continue

                # Heuristic: large/bold text → heading
                size = max(s["size"] for s in span_line["spans"])
                bold = any(s["flags"] & 16 for s in span_line["spans"])  # flag 16 = bold

                if size >= 18:
                    text = f"# {text}"
                elif size >= 14 or (bold and size >= 12):
                    text = f"## {text}"

                lines.append(text)

        page_md = "\n".join(lines)
        page_md = re.sub(r"\n{3,}", "\n\n", page_md)
        pages.append(f"<!-- page {i} -->\n{page_md}")

    md = "\n\n---\n\n".join(pages)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"  {pdf_path} → {out_path}")
    return out_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_md.py file.pdf [file2.pdf ...]")
        print("       python pdf_to_md.py folder/")
        sys.exit(1)

    targets = sys.argv[1:]
    pdfs = []

    for t in targets:
        if os.path.isdir(t):
            pdfs += [os.path.join(t, f) for f in os.listdir(t) if f.lower().endswith(".pdf")]
        elif t.lower().endswith(".pdf"):
            pdfs.append(t)
        else:
            print(f"Skipping {t} (not a PDF or directory)")

    if not pdfs:
        print("No PDF files found.")
        sys.exit(1)

    print(f"Converting {len(pdfs)} file(s)...")
    for pdf in pdfs:
        try:
            pdf_to_md(pdf)
        except Exception as e:
            print(f"  ERROR {pdf}: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
