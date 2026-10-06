"""Check that pptx2tif saves the images of a real deck pixel-for-pixel.

Usage:
    python samples/verify.py path/to/deck.pptx [originals_dir]

Extracts every image from the deck, then matches each TIFF to an original
image in ``originals_dir`` (default: samples/originals) by pixel size and
reports whether the pixels are identical.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from pptx2tif import extract_images


def load(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im)


def main() -> int:
    pptx = Path(sys.argv[1])
    originals_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "originals"
    originals = {p.name: load(p) for p in sorted(originals_dir.glob("*.png"))}

    with tempfile.TemporaryDirectory() as tmp:
        records = extract_images(pptx, tmp)
        print(f"{pptx.name}: {len(records)} image(s) found\n")
        failed = 0
        for r in records:
            label = f"slide {r.slide_index} img {r.image_index} ({r.source_format}, {r.mode}, {r.width_px}x{r.height_px})"
            if not r.output_path:
                print(f"[FAIL] {label}: {r.status} {r.message}")
                failed += 1
                continue
            saved = load(Path(tmp) / pptx.stem / r.output_path)
            same_size = [n for n, a in originals.items() if a.shape[:2] == saved.shape[:2]]
            if not same_size:
                print(f"[FAIL] {label}: no original with this pixel size (resized on export?)")
                failed += 1
                continue
            exact = [n for n in same_size if originals[n].shape == saved.shape
                     and np.array_equal(originals[n], saved)]
            if exact:
                print(f"[ OK ] {label} == {exact[0]} (pixel-identical)")
                continue
            name = same_size[0]
            orig = originals[name]
            if orig.shape != saved.shape:
                print(f"[FAIL] {label}: size matches {name} but channels differ "
                      f"{orig.shape} vs {saved.shape}")
            else:
                diff = np.abs(orig.astype(int) - saved.astype(int))
                print(f"[FAIL] {label}: size matches {name} but pixels differ "
                      f"(max diff {diff.max()}, {np.count_nonzero(diff)} values)")
            failed += 1

    print(f"\n{'ALL OK' if not failed else f'{failed} problem(s)'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
