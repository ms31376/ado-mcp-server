"""Entry point."""

from __future__ import annotations

from .app import mcp
from . import tools  # noqa: F401  (registers tools)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
