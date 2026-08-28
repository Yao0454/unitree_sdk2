from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("pages", nargs="+", type=int)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(args.pdf)
    for page_number in args.pages:
        if not 1 <= page_number <= document.page_count:
            raise ValueError(f"page {page_number} is outside 1..{document.page_count}")
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pixmap.save(args.output / f"page-{page_number:04d}.png")


if __name__ == "__main__":
    main()
