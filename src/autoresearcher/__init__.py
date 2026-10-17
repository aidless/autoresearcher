"""A research pipeline whose segments can only reach each other through a ledger.

The package is deliberately thin at the top: the schemas live in ``claim`` and
``artifact``, the pipeline in ``segments``, and the CLI on top of ``pipeline``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
