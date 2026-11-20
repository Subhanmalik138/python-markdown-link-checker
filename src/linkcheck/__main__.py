"""Entry point for ``python -m linkcheck``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
