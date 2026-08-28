from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--width", type=int, default=300)
    args = parser.parse_args()

    paths = sorted(args.source.glob("*.png"))
    if not paths:
        raise ValueError(f"no PNG files found in {args.source}")

    label_height = 28
    margin = 12
    font = ImageFont.load_default()
    thumbnails: list[tuple[Path, Image.Image]] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        height = round(image.height * args.width / image.width)
        thumbnails.append((path, image.resize((args.width, height))))

    cell_height = max(image.height for _, image in thumbnails) + label_height
    rows = (len(thumbnails) + args.columns - 1) // args.columns
    sheet = Image.new(
        "RGB",
        (
            args.columns * args.width + (args.columns + 1) * margin,
            rows * cell_height + (rows + 1) * margin,
        ),
        "#d9dee3",
    )
    draw = ImageDraw.Draw(sheet)
    for index, (path, image) in enumerate(thumbnails):
        row, column = divmod(index, args.columns)
        x = margin + column * (args.width + margin)
        y = margin + row * (cell_height + margin)
        sheet.paste(image, (x, y + label_height))
        draw.text((x + 4, y + 7), path.stem, fill="#17212b", font=font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)


if __name__ == "__main__":
    main()
