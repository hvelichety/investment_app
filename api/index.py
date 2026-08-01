"""
Vercel serverless entrypoint.
Exposes the Flask app from the project root.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import app  # noqa: E402

# Vercel's Python runtime looks for a WSGI-compatible `app` variable
