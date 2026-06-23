"""Make the add-on's top-level modules importable from tests.

The app runs with ``/app`` as the working directory (run.sh does ``cd /app``),
so modules are imported by their bare name (``import config_store``). Add the
``app`` directory to ``sys.path`` so tests can do the same.
"""
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)