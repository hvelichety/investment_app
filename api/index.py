"""
Vercel serverless entrypoint.
Exposes the Flask app from the src package.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.web import app  # noqa: E402

# Vercel's Python runtime looks for a WSGI-compatible `app` variable
