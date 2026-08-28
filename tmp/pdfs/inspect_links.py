from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject


def flatten_outline(items: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for item in items:
        if isinstance(item, list):
            flattened.extend(flatten_outline(item))
        else:
            flattened.append(item)
    return flattened


def action_file(action: DictionaryObject) -> str:
    file_spec = action.get("/F")
    if file_spec is None:
        return ""
    file_spec = file_spec.get_object()
    if isinstance(file_spec, DictionaryObject):
        return str(file_spec.get("/UF") or file_spec.get("/F") or "")
    return str(file_spec)


def inspect(path: Path) -> dict[str, Any]:
    reader = PdfReader(path)
    named_destinations = reader.named_destinations
    outline = flatten_outline(reader.outline)
    invalid_outline = 0
    for destination in outline:
        try:
            page_number = reader.get_destination_page_number(destination)
        except Exception:
            invalid_outline += 1
            continue
        if page_number is None or not 0 <= page_number < len(reader.pages):
            invalid_outline += 1

    link_count = 0
    internal_count = 0
    remote_count = 0
    uri_count = 0
    other_count = 0
    invalid_internal = 0
    markdown_targets: set[str] = set()
    remote_targets: set[str] = set()

    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            link_count += 1

            destination = annotation.get("/Dest")
            action = annotation.get("/A")
            if destination is not None:
                internal_count += 1
                destination = destination.get_object()
                if isinstance(destination, str) and destination not in named_destinations:
                    invalid_internal += 1
                elif isinstance(destination, ArrayObject) and not destination:
                    invalid_internal += 1
                continue

            if action is None:
                other_count += 1
                continue

            action = action.get_object()
            action_type = str(action.get("/S", ""))
            if action_type == "/GoTo":
                internal_count += 1
                destination = action.get("/D")
                if destination is None:
                    invalid_internal += 1
                else:
                    destination = destination.get_object()
                    if isinstance(destination, str) and destination not in named_destinations:
                        invalid_internal += 1
                    elif isinstance(destination, ArrayObject) and not destination:
                        invalid_internal += 1
            elif action_type == "/GoToR":
                remote_count += 1
                target = action_file(action)
                remote_targets.add(target)
                if target.lower().endswith(".md"):
                    markdown_targets.add(target)
            elif action_type == "/URI":
                uri_count += 1
                target = str(action.get("/URI", ""))
                if ".md" in target.lower():
                    markdown_targets.add(target)
            else:
                other_count += 1

    return {
        "path": str(path),
        "pages": len(reader.pages),
        "named_destinations": len(named_destinations),
        "outline_items": len(outline),
        "invalid_outline_items": invalid_outline,
        "links": link_count,
        "internal_links": internal_count,
        "remote_file_links": remote_count,
        "uri_links": uri_count,
        "other_links": other_count,
        "invalid_internal_links": invalid_internal,
        "markdown_targets": sorted(markdown_targets),
        "remote_targets": sorted(remote_targets),
    }


def main() -> None:
    reports = [inspect(Path(argument)) for argument in sys.argv[1:]]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    if any(
        report["invalid_outline_items"]
        or report["invalid_internal_links"]
        or report["markdown_targets"]
        for report in reports
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
