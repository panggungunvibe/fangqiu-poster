#!/usr/bin/env python3
"""Make two numbered 4 × 3 JPEG proof sheets, or extract a selected preview.

Each route accepts twelve numbered poster files (01–12, A01–A12 or B01–B12)
or one unlabelled square image with twelve edge-to-edge cells in row-major
order. A shared folder can contain both A- and B-prefixed sets. Visually
check a generated grid for twelve distinct, aligned panels before using it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont, ImageOps


COLUMNS, ROWS = 4, 3
NUMBERS = range(1, COLUMNS * ROWS + 1)
FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
NUMBER_PREFIX = re.compile(r"^([AB]?)(0[1-9]|1[0-2])(?!\d)", re.IGNORECASE)
PAPER, INK = "#f7f7f5", "#232725"
ROUTE_TITLES = {"A": "Full Color", "B": "60 / 30 / 10"}
TILE = (540, 720)


def numbered_files(directory: Path, route: str) -> dict[int, Path]:
    files = {}
    for file in sorted(directory.iterdir()):
        if not file.is_file() or file.suffix.lower() not in FORMATS:
            continue
        match = NUMBER_PREFIX.match(file.stem)
        if not match:
            continue
        prefix, digits = match.groups()
        if prefix and prefix.upper() != route:
            continue
        # A finished set may also contain numbered comparison/overview sheets.
        if re.search(r"总览|新旧对照|overview|contact[-_ ]?sheet|before[-_ ]?after",
                     file.stem, re.IGNORECASE):
            continue
        number = int(digits)
        if number in files:
            raise ValueError(f"Duplicate {number:02d} in {directory}: "
                             f"{files[number].name} and {file.name}")
        files[number] = file
    missing = [f"{n:02d}" for n in NUMBERS if n not in files]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)} in {directory}")
    return files


def open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")


def read_cells(source: Path, route: str, numbers=NUMBERS):
    if source.is_dir():
        files = numbered_files(source, route)
        for n in numbers:
            cell = open_rgb(files[n])
            if abs((cell.width / cell.height) / (3 / 4) - 1) > 0.08:
                raise ValueError(f"Expected a near-3:4 portrait in {files[n]}, "
                                 f"got {cell.width} × {cell.height}")
            yield n, cell
    else:
        board = open_rgb(source)
        w, h = board.size
        if w < COLUMNS or h < ROWS or abs(w / h - 1) > 0.01:
            raise ValueError(f"Expected a square 4 × 3 raw grid in {source}, "
                             f"got {w} × {h}")
        for n in numbers:
            row, col = divmod(n - 1, COLUMNS)
            # Shared rounded boundaries include every pixel even for 1024 × 1024.
            box = (round(col * w / COLUMNS), round(row * h / ROWS),
                   round((col + 1) * w / COLUMNS), round((row + 1) * h / ROWS))
            yield n, board.crop(box)


def label(board: Image.Image, xy: tuple[int, int], text: str, size: int) -> None:
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            # Pillow 10.0 has a fixed-size built-in font. Scale its ASCII mask.
            font = ImageFont.load_default()
            left, top, right, bottom = font.getbbox(text)
            mask = Image.new("L", (right - left, bottom - top))
            ImageDraw.Draw(mask).text((-left, -top), text, font=font, fill=255)
            mask = mask.resize((round(mask.width * size / mask.height), size),
                               Image.Resampling.NEAREST)
            board.paste(INK, xy, mask)
            return
    ImageDraw.Draw(board).text(xy, text, font=font, fill=INK, anchor="lt")


def render_board(route: str, source: Path, output: Path) -> None:
    margin, gap, header, caption = 46, 24, 92, 58
    tw, th = TILE
    width = 2 * margin + COLUMNS * tw + (COLUMNS - 1) * gap
    height = 2 * margin + header + ROWS * (th + caption) + (ROWS - 1) * gap
    board = Image.new("RGB", (width, height), PAPER)
    label(board, (margin, margin), f"{route}   {ROUTE_TITLES[route]}", 44)
    for n, cell in read_cells(source, route):
        row, col = divmod(n - 1, COLUMNS)
        x = margin + col * (tw + gap)
        y = margin + header + row * (th + caption + gap)
        # Fit without cutting off a glyph or hiding the original edges.
        preview = ImageOps.contain(cell, TILE, method=Image.Resampling.LANCZOS)
        board.paste(preview, (x + (tw - preview.width) // 2,
                              y + (th - preview.height) // 2))
        label(board, (x, y + th + 12), f"{route}{n:02d}", 30)
    board.save(output, format="JPEG", quality=93, subsampling=0, optimize=True)


def create_boards(a: Path, b: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    names = ["A-preview.jpg", "B-preview.jpg"]
    for name in names:
        if (out / name).resolve() in (a.resolve(), b.resolve()):
            raise ValueError(f"Output would overwrite a raw source board: {out / name}")
        if (out / name).is_dir():
            raise ValueError(f"Output is a directory: {out / name}")
    # Finish both routes before replacing any previously completed sheets.
    with TemporaryDirectory(dir=out) as temporary:
        stage = Path(temporary)
        for route, source, name in zip(("A", "B"), (a, b), names):
            render_board(route, source, stage / name)
        for name in names:
            (stage / name).replace(out / name)
            print(out / name)


def extract(source: Path, route: str, number: int, output: Path) -> None:
    if output.suffix.lower() != ".png":
        raise ValueError("Use a .png output path for the extracted reference")
    if source.is_dir() and output.resolve().parent == source.resolve() and NUMBER_PREFIX.match(output.stem):
        raise ValueError("Save the numbered extract outside its input folder to keep its source set unique")
    if output.resolve() == source.resolve():
        raise ValueError(f"Output would overwrite a source image: {output}")
    _, cell = next(read_cells(source, route, [number]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temporary:
        result = Path(temporary) / "cell.png"
        cell.save(result, format="PNG")
        result.replace(output)
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    boards = commands.add_parser("boards", help="Export A-preview.jpg and B-preview.jpg")
    pick = commands.add_parser("extract", help="Export one unlabelled cell at source resolution")
    for command in (boards, pick):
        for route in ("a", "b"):
            command.add_argument(f"--{route}", type=Path, required=command is boards,
                                 help=f"Route {route.upper()} input: numbered folder (with optional "
                                      f"{route.upper()} prefix) or raw square grid")
    boards.add_argument("--out-dir", type=Path, required=True)
    pick.add_argument("--pick", type=str.upper, required=True, metavar="ID",
                      choices=[f"{route}{n:02d}" for route in ROUTE_TITLES for n in NUMBERS])
    pick.add_argument("--out", type=Path, required=True, help="Output .png for the selected reference")
    args = parser.parse_args()
    try:
        if args.command == "boards":
            create_boards(args.a, args.b, args.out_dir)
        else:
            route = args.pick[0].lower()
            source = getattr(args, route)
            if source is None:
                parser.error(f"{args.pick} requires --{route}")
            extract(source, route.upper(), int(args.pick[1:]), args.out)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"preview_boards: {exc}\n")


if __name__ == "__main__":
    main()
