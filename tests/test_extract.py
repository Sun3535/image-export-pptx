from __future__ import annotations

import io
import json

import numpy as np
import png
import pytest
import tifffile
from PIL import Image

from pptx2tif import extract_images, iter_images
from pptx2tif.cli import main


def decode_source(blob: bytes) -> np.ndarray:
    """Reference decode of the original bytes, at full bit depth."""
    if blob[:8] == b"\x89PNG\r\n\x1a\n" and blob[24] == 16 and blob[25] in (2, 4, 6):
        w, h, rows, info = png.Reader(bytes=blob).asDirect()
        return np.vstack([np.asarray(r, dtype=np.uint16) for r in rows]).reshape(
            h, w, info["planes"]
        )
    img = Image.open(io.BytesIO(blob))
    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
    return np.asarray(img)


def test_every_image_saved_losslessly(sample_pptx, tmp_path):
    pptx, expected = sample_pptx
    out = tmp_path / "out"
    records = extract_images(pptx, out)

    folder = out / "deck"
    tifs = sorted(p.stem for p in folder.glob("*.tif"))
    assert tifs == sorted(expected)
    assert len(records) == len(expected)

    for stem, blob in expected.items():
        saved = tifffile.imread(folder / f"{stem}.tif")
        ref = decode_source(blob)
        assert saved.shape == ref.shape, stem
        assert saved.dtype == ref.dtype, stem
        assert np.array_equal(saved, ref), f"{stem} pixels differ"


def test_bit_depth_preserved(sample_pptx, tmp_path):
    pptx, _ = sample_pptx
    extract_images(pptx, tmp_path)
    assert tifffile.imread(tmp_path / "deck" / "slide002_img03.tif").dtype == np.uint16
    rgb16 = tifffile.imread(tmp_path / "deck" / "slide003_img01.tif")
    assert rgb16.dtype == np.uint16 and rgb16.shape == (20, 40, 3)


def test_crop_keeps_full_original(sample_pptx, tmp_path):
    pptx, _ = sample_pptx
    records = extract_images(pptx, tmp_path)
    rec = next(r for r in records if (r.slide_index, r.image_index) == (3, 3))
    assert (rec.width_px, rec.height_px) == (100, 100)
    assert rec.crop["left"] == pytest.approx(0.25)
    assert rec.crop["right"] == pytest.approx(0.1)
    with Image.open(tmp_path / "deck" / "slide003_img03.tif") as im:
        assert im.size == (100, 100)


def test_group_and_duplicates(sample_pptx, tmp_path):
    pptx, _ = sample_pptx
    records = extract_images(pptx, tmp_path)
    grouped = [r for r in records if r.group_path]
    assert len(grouped) == 2
    dups = [r for r in records if r.slide_index == 4]
    assert len(dups) == 2 and dups[0].sha256 == dups[1].sha256


@pytest.mark.parametrize("compression,tag", [("deflate", 8), ("lzw", 5), ("none", 1)])
def test_lossless_compression_tag(sample_pptx, tmp_path, compression, tag):
    pptx, expected = sample_pptx
    extract_images(pptx, tmp_path, compression=compression)
    with Image.open(tmp_path / "deck" / "slide001_img01.tif") as im:
        assert im.tag_v2[259] == tag
        assert np.array_equal(np.asarray(im), decode_source(expected["slide001_img01"]))


def test_manifest_schema(sample_pptx, tmp_path):
    pptx, expected = sample_pptx
    extract_images(pptx, tmp_path, keep_original=True, min_ppi=150)
    manifest = json.loads((tmp_path / "deck" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_file"] == "deck.pptx"
    assert manifest["slide_count"] == 5
    assert manifest["image_count"] == len(expected)
    keys = {
        "slide_index", "image_index", "shape_id", "shape_name", "group_path",
        "output_path", "original_path", "source_format", "width_px", "height_px",
        "mode", "bits_per_sample", "dpi", "effective_ppi", "crop", "bbox_emu",
        "sha256", "status", "message",
    }
    for img in manifest["images"]:
        assert set(img) == keys
        assert img["status"] == "ok"
        assert (tmp_path / "deck" / img["original_path"]).exists()
    low = next(i for i in manifest["images"] if i["output_path"] == "slide004_img01.tif")
    assert low["effective_ppi"] == pytest.approx(5.0)
    assert "low on-slide resolution" in low["message"]


def test_iter_images_matches_files(sample_pptx):
    pptx, expected = sample_pptx
    got = {f"slide{r.slide_index:03d}_img{r.image_index:02d}": a for r, a in iter_images(pptx)}
    assert set(got) == set(expected)
    for stem, blob in expected.items():
        assert np.array_equal(got[stem], decode_source(blob))


def test_cli(sample_pptx, tmp_path, capsys):
    pptx, expected = sample_pptx
    code = main([str(pptx.parent), "-o", str(tmp_path / "cli_out")])
    assert code == 0
    assert len(list((tmp_path / "cli_out" / "deck").glob("*.tif"))) == len(expected)
    assert f"{len(expected)} TIFF saved" in capsys.readouterr().out


def test_cli_bad_input(tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("hi")
    assert main([str(bad), "-o", str(tmp_path / "o")]) == 1


def test_default_output_is_next_to_pptx(sample_pptx):
    pptx, expected = sample_pptx
    extract_images(pptx)
    folder = pptx.parent / pptx.stem
    assert len(list(folder.glob("*.tif"))) == len(expected)
    assert (folder / "manifest.json").exists()


def test_cli_without_output(sample_pptx, capsys):
    pptx, expected = sample_pptx
    assert main([str(pptx)]) == 0
    assert len(list((pptx.parent / pptx.stem).glob("*.tif"))) == len(expected)
