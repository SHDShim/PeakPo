"""PyInstaller entry point for the standalone PeakPo application."""

from peakpo.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
