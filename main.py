"""
G-Mirror — Top-level launcher.
Run from the G-Mirror directory: python main.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gmirror.app import run

if __name__ == "__main__":
    sys.exit(run())
