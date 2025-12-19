#!/usr/bin/env python3
"""
Debug script to see if the pool is actually being used or if we're creating ad-hoc workers.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pctx_sandbox import sandbox

# Enable logging to see pool behavior
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)-25s: %(message)s",
    datefmt="%H:%M:%S",
)

print("=" * 80)
print("CHECKING IF POOL IS ACTUALLY BEING USED")
print("=" * 80)

print("\n1. First execution (pool should be empty initially)")


@sandbox()
def first_func(x: int) -> int:
    return x * 2


try:
    result = first_func(42)
    print(f"✓ First execution succeeded: {result}")
except Exception as e:
    print(f"✗ First execution failed: {e}")

print("\n2. Second execution (should reuse worker from pool)")


@sandbox()
def second_func(x: int) -> int:
    return x * 3


try:
    result = second_func(42)
    print(f"✓ Second execution succeeded: {result}")
except Exception as e:
    print(f"✗ Second execution failed: {e}")

print("\n3. Third execution (should still reuse pool)")


@sandbox()
def third_func(x: int) -> int:
    return x * 4


try:
    result = third_func(42)
    print(f"✓ Third execution succeeded: {result}")
except Exception as e:
    print(f"✗ Third execution failed: {e}")

print("\n" + "=" * 80)
print("Look at the logs above to see:")
print("  - How many workers were created")
print("  - Whether workers were reused from pool or created ad-hoc")
print("=" * 80)
