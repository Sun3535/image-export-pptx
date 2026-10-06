"""Double-click / `python pptx2tif_gui.py` launcher for the popup window."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pptx2tif.gui import main  # noqa: E402

main()
