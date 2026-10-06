#!/bin/bash
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null; then
  echo "Python is not installed. Install it from https://www.python.org/downloads/"
  read -r -p "Press Enter to close"; exit 1
fi
# Install packages only when something is missing (first run).
if ! python3 -c "import pptx, PIL, numpy, tifffile, png" 2>/dev/null; then
  echo "Installing required packages - first run only..."
  python3 -m pip install --disable-pip-version-check --no-warn-script-location \
    --no-cache-dir -q -r requirements.txt || {
    read -r -p "Package install failed. Press Enter to close"; exit 1; }
fi
python3 pptx2tif_gui.py
