#!/usr/bin/env python3
"""
Debug the very first worker startup to see why it fails.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pctx_sandbox import sandbox

# Enable ALL logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)-25s: %(message)s",
    datefmt="%H:%M:%S",
)

print("=" * 80)


@sandbox()
def first_func(x: int) -> int:
    return x * 2


try:
    result = first_func(42)
    print(f"\n✓ SUCCESS: {result}")
except Exception as e:
    print(f"\n✗ FAILED: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)


@sandbox()
def second_func(x: int) -> int:
    return x * 3


try:
    result = second_func(42)
    print(f"\n✓ SUCCESS: {result}")
except Exception as e:
    print(f"\n✗ FAILED: {e}")
    import traceback

    traceback.print_exc()
