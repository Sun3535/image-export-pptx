"""Extract images from .pptx files as lossless, full-resolution TIFF."""

__version__ = "0.1.0"

from .extractor import extract_images, iter_images  # noqa: E402
from .models import ImageRecord  # noqa: E402

__all__ = ["extract_images", "iter_images", "ImageRecord", "__version__"]
