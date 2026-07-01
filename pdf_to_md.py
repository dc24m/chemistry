#!/usr/bin/env python3
"""Convert a PDF file to Markdown using PyMuPDF."""

import sys
import argparse
import statistics
from pathlib import Path


# PyMuPDF span flag bits
FLAG_ITALIC = 1 << 1      # 2
FLAG_BOLD   = 1 << 4      # 16


def spans_to_md(spans: list[dict], body_size: float) -> str:
    """Convert a list of spans (one line) to a Markdown string."""
    parts = []
    for span in spans:
        text = span["text"]
        if not text.strip():
            parts.append(text)
            continue
        size  = span["size"]
        flags = span["flags"]
        bold   = bool(flags & FLAG_BOLD)
        italic = bool(flags & FLAG_ITALIC)
        mono   = "mono" in span.get("font", "").lower() or "courier" in span.get("font", "").lower()

        # wrap in markdown syntax
        if mono:
            text = f"`{text}`"
        else:
            if bold and italic:
                text = f"***{text}***"
            elif bold:
                text = f"**{text}**"
            elif italic:
                text = f"*{text}*"

        parts.append(text)
    return "".join(parts)


def page_to_md(page, body_size: float, heading_sizes: list[float]) -> str:
    data = page.get_text("dict", flags=0)
    lines_out = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:  # 0 = text block
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue

            # representative size for the line: max span size
            line_size = max(s["size"] for s in spans)
            raw_text  = "".join(s["text"] for s in spans).strip()
            if not raw_text:
                continue

            # choose heading level based on size relative to body
            if heading_sizes and line_size > body_size * 1.05:
                # rank among heading sizes (largest = h1)
                rank = sorted(set(heading_sizes), reverse=True)
                try:
                    level = rank.index(min(rank, key=lambda s: abs(s - line_size))) + 1
                    level = min(level, 4)
                except ValueError:
                    level = 1
                lines_out.append(f"{'#' * level} {raw_text}")
            else:
                lines_out.append(spans_to_md(spans, body_size))

        lines_out.append("")  # blank line after each block

    return "\n".join(lines_out)


def collect_sizes(doc) -> tuple[float, list[float]]:
    """Sample the first 10 pages to find body size and heading sizes."""
    sizes = []
    sample = min(len(doc), 10)
    for i in range(sample):
        for block in doc[i].get_text("dict", flags=0).get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if t:
                        sizes.append(round(span["size"], 1))

    if not sizes:
        return 10.0, []

    body_size = statistics.mode(sizes)
    heading_sizes = sorted({s for s in sizes if s > body_size * 1.05}, reverse=True)
    return body_size, heading_sizes


def pdf_to_markdown(pdf_path: Path, output_path: Path) -> None:
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    total = len(doc)
    print(f"Converting {total} pages from '{pdf_path.name}' …")

    body_size, heading_sizes = collect_sizes(doc)

    chunks = []
    for i, page in enumerate(doc, 1):
        md = page_to_md(page, body_size, heading_sizes)
        if md.strip():
            chunks.append(f"<!-- page {i} -->\n\n{md}")
        if i % 10 == 0 or i == total:
            print(f"  {i}/{total} pages", end="\r")

    doc.close()
    print()

    output_path.write_text("\n\n---\n\n".join(chunks), encoding="utf-8")
    print(f"Written to '{output_path}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a PDF to Markdown.")
    parser.add_argument("pdf", help="Input PDF file")
    parser.add_argument(
        "-o", "--output",
        help="Output .md file (default: same name as PDF with .md extension)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        sys.exit(f"Error: '{pdf_path}' not found.")
    if pdf_path.suffix.lower() != ".pdf":
        sys.exit("Error: input file must be a .pdf.")

    output_path = (
        Path(args.output).expanduser().resolve() if args.output
        else pdf_path.with_suffix(".md")
    )

    pdf_to_markdown(pdf_path, output_path)


if __name__ == "__main__":
    main()
