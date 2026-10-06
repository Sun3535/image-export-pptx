"""Decode embedded image bytes and write them as lossless TIFF.

Two decode paths keep every bit of the source:

* Pillow, for ordinary images (8-bit, 16-bit grayscale, CMYK, ...).
* numpy + tifffile, for 16-bit-per-channel color images, which Pillow
  would silently reduce to 8 bits.

No resizing or resampling ever happens. Only lossless TIFF compression is used.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import png
import tifffile
from PIL import Image

VECTOR_EXTS = {"emf", "wmf", "svg", "eps"}

COMPRESSIONS = ("deflate", "lzw", "none")
_PIL_COMPRESSION = {"deflate": "tiff_adobe_deflate", "lzw": "tiff_lzw", "none": "raw"}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_MODE_BITS = {"1": 1, "I": 32, "F": 32}


@dataclass
class DecodedImage:
    """A decoded image held either as a PIL image or as a numpy array."""

    source_format: str
    width: int
    height: int
    mode: str
    bits_per_sample: int
    dpi: tuple[float, float] | None
    icc_profile: bytes | None
    pil: Image.Image | None = None
    array: np.ndarray | None = None
    note: str | None = None

    def to_array(self) -> np.ndarray:
        """Pixel data as a numpy array, with no loss of bit depth."""
        if self.array is not None:
            return self.array
        return np.asarray(self.pil)


def _bits_for_mode(mode: str) -> int:
    if mode.startswith("I;16"):
        return 16
    return _MODE_BITS.get(mode, 8)


def _is_high_depth_color_png(blob: bytes) -> bool:
    # IHDR: bytes 24 = bit depth, 25 = colour type (2 RGB, 4 gray+alpha, 6 RGBA)
    return (
        blob[:8] == _PNG_SIGNATURE
        and len(blob) > 25
        and blob[24] == 16
        and blob[25] in (2, 4, 6)
    )


def _is_high_depth_color_tiff(pil: Image.Image) -> bool:
    if pil.format != "TIFF":
        return False
    bits = pil.tag_v2.get(258)  # BitsPerSample
    samples = pil.tag_v2.get(277, 1)  # SamplesPerPixel
    if bits is None:
        return False
    max_bits = max(bits) if isinstance(bits, tuple) else bits
    return max_bits > 8 and samples > 1


def _dpi_from_pil(pil: Image.Image) -> tuple[float, float] | None:
    dpi = pil.info.get("dpi")
    if not dpi:
        return None
    return (float(dpi[0]), float(dpi[1]))


def _normalize_pil(pil: Image.Image) -> Image.Image:
    """Expand palette images to plain pixels. Pixel values are unchanged."""
    if pil.mode == "P":
        return pil.convert("RGBA" if "transparency" in pil.info else "RGB")
    if pil.mode == "PA":
        return pil.convert("RGBA")
    return pil


def decode(blob: bytes) -> DecodedImage:
    pil = Image.open(io.BytesIO(blob))
    fmt = (pil.format or "unknown").lower()
    dpi = _dpi_from_pil(pil)
    icc = pil.info.get("icc_profile")

    if _is_high_depth_color_png(blob):
        width, height, rows, info = png.Reader(bytes=blob).asDirect()
        planes = info["planes"]
        arr = np.vstack([np.asarray(r, dtype=np.uint16) for r in rows])
        arr = arr.reshape(height, width, planes)
        mode = {2: "LA;16", 3: "RGB;16", 4: "RGBA;16"}[planes]
        return DecodedImage(fmt, width, height, mode, 16, dpi, icc, array=arr)

    note = None
    if _is_high_depth_color_tiff(pil):
        try:
            arr = tifffile.imread(io.BytesIO(blob))
            bits = arr.dtype.itemsize * 8
            planes = arr.shape[-1] if arr.ndim == 3 else 1
            mode = {2: "LA", 3: "RGB", 4: "RGBA"}.get(planes, f"{planes}ch") + f";{bits}"
            return DecodedImage(
                fmt, arr.shape[1], arr.shape[0], mode, bits, dpi, icc, array=arr
            )
        except Exception as exc:  # e.g. a codec tifffile cannot decode
            note = f"high bit-depth TIFF decoded by Pillow (may lose depth): {exc}"

    pil.load()
    if getattr(pil, "n_frames", 1) > 1:
        frames_note = f"multi-frame image ({pil.n_frames} frames); all frames saved"
        note = f"{note}; {frames_note}" if note else frames_note
    out = _normalize_pil(pil)
    return DecodedImage(
        fmt,
        out.width,
        out.height,
        out.mode,
        _bits_for_mode(out.mode),
        dpi,
        icc,
        pil=out,
        note=note,
    )


def _save_pil(img: DecodedImage, path: Path, compression: str) -> None:
    params: dict = {"compression": _PIL_COMPRESSION[compression]}
    if img.dpi:
        params["dpi"] = img.dpi
    if img.icc_profile:
        params["icc_profile"] = img.icc_profile
    pil = img.pil
    if getattr(pil, "n_frames", 1) > 1:
        frames = []
        for i in range(pil.n_frames):
            pil.seek(i)
            frames.append(_normalize_pil(pil.copy()))
        frames[0].save(path, format="TIFF", save_all=True, append_images=frames[1:], **params)
    else:
        pil.save(path, format="TIFF", **params)


def _save_array(img: DecodedImage, path: Path, compression: str) -> str | None:
    arr = img.array
    planes = arr.shape[-1] if arr.ndim == 3 else 1
    kwargs: dict = {}
    if planes in (3, 4):
        kwargs["photometric"] = "rgb"
        if planes == 4:
            kwargs["extrasamples"] = ["unassalpha"]
    else:
        kwargs["photometric"] = "minisblack"
        if planes == 2:
            kwargs["extrasamples"] = ["unassalpha"]
            kwargs["planarconfig"] = "contig"
    if img.dpi:
        kwargs["resolution"] = img.dpi
        kwargs["resolutionunit"] = "INCH"
    if img.icc_profile:
        kwargs["iccprofile"] = img.icc_profile

    codec = {"deflate": "zlib", "lzw": "lzw", "none": None}[compression]
    try:
        tifffile.imwrite(path, arr, compression=codec, **kwargs)
        return None
    except Exception:
        if codec != "lzw":
            raise
        # LZW encoding in tifffile needs the optional imagecodecs package.
        tifffile.imwrite(path, arr, compression="zlib", **kwargs)
        return "lzw unavailable for 16-bit color image; saved with deflate"


def save_tiff(img: DecodedImage, path: Path, compression: str = "deflate") -> str | None:
    """Write ``img`` losslessly to ``path``. Returns a note if anything was adjusted."""
    if compression not in COMPRESSIONS:
        raise ValueError(f"compression must be one of {COMPRESSIONS}, got {compression!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.array is not None:
        return _save_array(img, path, compression)
    _save_pil(img, path, compression)
    return None
