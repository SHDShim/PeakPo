import sys


def main():
    if "--version" in sys.argv[1:]:
        from .version import __version__

        print(__version__)
        return 0

    # Importing this module launches the Qt application.
    from . import peakpo  # noqa: F401
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
