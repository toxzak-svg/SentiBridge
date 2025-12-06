#!/usr/bin/env python3
"""Entry point for running the SentiBridge worker."""

import asyncio
import sys

from src.worker import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        sys.exit(0)
