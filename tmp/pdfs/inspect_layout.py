from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import fitz


def inspect(path: Path) -> dict[str, Any]:
    document = fitz.open(path)
    blank_pages: list[int] = []
    out_of_bounds: list[dict[str, Any]] = []
    replacement_character_pages: list[int] = []
    literal_markdown_heading_pages: list[int] = []
    text_lengths: list[int] = []
    page_samples: list[dict[str, Any]] = []

    for index, page in enumerate(document):
        page_number = index + 1
        text = page.get_text("text")
        stripped = text.strip()
        text_lengths.append(len(stripped))
        body_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and line.strip() != "Unitree SDK2 Python Bindings"
            and line.strip() != "API Documentation"
            and line.strip() != str(page_number)
        ]
        body_text = " ".join(body_lines)
        page_samples.append(
            {
                "page": page_number,
                "body_characters": len(body_text),
                "sample": body_text[:120],
            }
        )
        if len(stripped) < 10:
            blank_pages.append(page_number)
        if "\ufffd" in text:
            replacement_character_pages.append(page_number)
        if re.search(r"(?m)^#{2,6}\s+\S", text):
            literal_markdown_heading_pages.append(page_number)

        page_rect = page.rect + (-1, -1, 1, 1)
        for block in page.get_text("blocks"):
            if len(block) < 7 or block[6] != 0 or not str(block[4]).strip():
                continue
            block_rect = fitz.Rect(block[:4])
            if not page_rect.contains(block_rect):
                out_of_bounds.append(
                    {
                        "page": page_number,
                        "rect": [round(value, 2) for value in block_rect],
                    }
                )

    return {
        "path": str(path),
        "pages": document.page_count,
        "minimum_text_characters": min(text_lengths),
        "maximum_text_characters": max(text_lengths),
        "sparsest_pages": sorted(
            page_samples, key=lambda item: item["body_characters"]
        )[:20],
        "blank_pages": blank_pages,
        "out_of_bounds_text_blocks": out_of_bounds,
        "replacement_character_pages": replacement_character_pages,
        "literal_markdown_heading_pages": literal_markdown_heading_pages,
    }


def main() -> None:
    reports = [inspect(Path(argument)) for argument in sys.argv[1:]]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    if any(
        report["blank_pages"]
        or report["out_of_bounds_text_blocks"]
        or report["replacement_character_pages"]
        or report["literal_markdown_heading_pages"]
        for report in reports
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
