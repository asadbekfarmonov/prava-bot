"""Minimal rate-limit placeholder for slice 1.

Full per-scope rate limiting (docs/spec/09) is reused/expanded in a later slice.
Provided so tests and future routes can import a stable interface.
"""

from __future__ import annotations


def clear_rate_limits() -> None:
    return None
