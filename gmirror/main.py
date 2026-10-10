"""
G-Mirror — Main entry point.

Run with: python -m gmirror
Or:       python gmirror/main.py
"""

import sys
import os

# Ensure the project root is in sys.path when run directly
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from gmirror.app import run

if __name__ == "__main__":
    sys.exit(run())
