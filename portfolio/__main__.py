"""Entry point: python -m portfolio [--dry-run] [-v]"""

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
