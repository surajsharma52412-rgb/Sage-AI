"""
Web runner package for Sage AI (Lunar Engine).
Dual-mode runner using Flask and optional pywebview.
"""
from .web_server import run_web_app

__all__ = ["run_web_app"]
