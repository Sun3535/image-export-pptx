"""Command line interface: ``pptx2tif INPUT... -o OUT``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .extractor import extract_images
from .models import STATUS_ERROR, STATUS_OK
from .tiff import COMPRESSIONS


def _collect(inputs: list[str], recursive: bool) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            pattern = "**/*.pptx" if recursive else "*.pptx"
            files.extend(sorted(f for f in p.glob(pattern) if not f.name.startswith("~$")))
        else:
            files.append(p)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pptx2tif",
        description="Save every image in .pptx files as a separate lossless, full-resolution TIFF.",
    )
    parser.add_argument("inputs", nargs="+", help=".pptx files or folders")
    parser.add_argument("-o", "--output",
                        help="output folder (default: the folder each .pptx is in)")
    parser.add_argument("-r", "--recursive", action="store_true", help="search folders recursively")
    parser.add_argument("--compression", choices=COMPRESSIONS, default="deflate",
                        help="lossless TIFF compression (default: deflate)")
    parser.add_argument("--keep-original", action="store_true",
                        help="also save the original embedded image file")
    parser.add_argument("--min-ppi", type=float, default=150.0,
                        help="warn when an image's on-slide resolution is below this (default: 150)")
    args = parser.parse_args(argv)

    files = _collect(args.inputs, args.recursive)
    if not files:
        print("no .pptx files found", file=sys.stderr)
        return 1

    total_saved = total_warn = total_err = 0
    for f in files:
        if f.suffix.lower() != ".pptx" or not f.is_file():
            print(f"[error] {f}: not a .pptx file", file=sys.stderr)
            total_err += 1
            continue
        try:
            records = extract_images(f, args.output, args.compression,
                                     args.keep_original, args.min_ppi)
        except Exception as exc:
            print(f"[error] {f}: {exc}", file=sys.stderr)
            total_err += 1
            continue

        saved = sum(1 for r in records if r.status == STATUS_OK and r.output_path)
        slides = len({r.slide_index for r in records})
        target = Path(args.output if args.output else f.parent) / f.stem
        print(f"{f.name}: {saved} image(s) from {slides} slide(s) -> {target}")
        for r in records:
            if r.message:
                tag = "error" if r.status == STATUS_ERROR else "warn"
                print(f"  [{tag}] slide {r.slide_index} img {r.image_index} "
                      f"({r.shape_name}): {r.message}")
        total_saved += saved
        total_err += sum(1 for r in records if r.status == STATUS_ERROR)
        total_warn += sum(1 for r in records if r.message and r.status != STATUS_ERROR)

    print(f"done: {total_saved} TIFF saved, {total_warn} warning(s), {total_err} error(s)")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
