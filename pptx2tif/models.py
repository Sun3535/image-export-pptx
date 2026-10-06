"""Data schema for one extracted image (one entry of ``manifest.json``)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

STATUS_OK = "ok"
STATUS_SKIPPED_VECTOR = "skipped_vector"
STATUS_ERROR = "error"


@dataclass
class ImageRecord:
    slide_index: int
    image_index: int
    shape_id: int
    shape_name: str
    group_path: list[str] = field(default_factory=list)
    output_path: str | None = None
    original_path: str | None = None
    source_format: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    mode: str | None = None
    bits_per_sample: int | None = None
    dpi: tuple[float, float] | None = None
    effective_ppi: float | None = None
    crop: dict[str, float] = field(default_factory=dict)
    bbox_emu: dict[str, int] = field(default_factory=dict)
    sha256: str | None = None
    status: str = STATUS_OK
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["dpi"] is not None:
            d["dpi"] = list(d["dpi"])
        return d
