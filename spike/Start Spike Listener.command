#!/bin/bash
# R50 GSPro Spike Listener — macOS launcher (double-clickable).
# Pure-Python stdlib app; needs Python 3 (the python.org build includes Tkinter).
cd "$(dirname "$0")" || exit 1
echo "Starting the R50 GSPro Open Connect Spike Listener..."
echo

# Prefer python3; fall back to the python.org Python Launcher path.
if command -v python3 >/dev/null 2>&1; then
    python3 gspro_spike_listener.py
elif [ -x "/usr/local/bin/python3" ]; then
    /usr/local/bin/python3 gspro_spike_listener.py
else
    echo "============================================================"
    echo "  Python 3 was not found on this Mac."
    echo
    echo "  1. Go to https://www.python.org/downloads/macos/"
    echo "  2. Download the latest macOS installer and run it"
    echo "     (this build includes Tkinter, which the app needs)."
    echo "  3. Finish install, then double-click this file again."
    echo "============================================================"
fi

echo
echo "(You can close this Terminal window when you are done.)"
