#!/usr/bin/env python3
"""
Debug script to verify socket binding behavior and identify port conflicts.

This script tests the socket binding mechanism used by workers to ensure
there are no race conditions or port conflicts.
"""

import socket
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_socket_binding_old_way():
    """Test the OLD socket binding approach (bind, close, use port)."""
    print("\n" + "=" * 60)
    print("TEST 1: Old Socket Binding (bind → close → reuse port)")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    print(f"✓ Bound to port {port}")

    sock.close()
    print(f"✗ Socket closed - port {port} is now FREE")

    # Try to bind to the same port immediately
    time.sleep(0.001)  # Tiny delay to simulate race condition window

    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.bind(("127.0.0.1", port))
        print(f"⚠ RACE CONDITION: Another process bound to port {port} before uvicorn!")
        test_sock.close()
        return False
    except OSError as e:
        print(f"✓ Port {port} still in TIME_WAIT (safe for now): {e}")
        return True


def test_socket_binding_new_way():
    """Test the NEW socket binding approach (bind, keep open, pass fd)."""
    print("\n" + "=" * 60)
    print("TEST 2: New Socket Binding (bind → keep open → pass fd)")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    print(f"✓ Bound to port {port} with SO_REUSEADDR")

    # Socket is still OPEN and bound
    print(f"✓ Socket still open - port {port} is CLAIMED")

    # Try to bind to the same port
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.bind(("127.0.0.1", port))
        print(f"⚠ ERROR: Another process bound to port {port} (should not happen!)")
        test_sock.close()
        sock.close()
        return False
    except OSError as e:
        print(f"✓ Port {port} is protected: {e}")
        sock.close()
        return True


def test_port_reuse_timing():
    """Test how quickly ports can be reused after closing."""
    print("\n" + "=" * 60)
    print("TEST 3: Port Reuse Timing Analysis")
    print("=" * 60)

    port_reuse_times = []

    for _ in range(5):
        # Bind and close
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        # Try to reuse immediately
        start_time = time.time()
        while True:
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.bind(("127.0.0.1", port))
                reuse_time = time.time() - start_time
                port_reuse_times.append(reuse_time)
                print(f"  Port {port} reusable after {reuse_time * 1000:.1f}ms")
                test_sock.close()
                break
            except OSError:
                if time.time() - start_time > 5.0:
                    print(f"  Port {port} not reusable after 5s (TIME_WAIT)")
                    break
                time.sleep(0.01)

    if port_reuse_times:
        avg_time = sum(port_reuse_times) / len(port_reuse_times)
        min_time = min(port_reuse_times)
        max_time = max(port_reuse_times)
        print(
            f"\nPort reuse timing: avg={avg_time * 1000:.1f}ms, min={min_time * 1000:.1f}ms, max={max_time * 1000:.1f}ms"
        )
    else:
        print("\n⚠ No ports were reusable (all in TIME_WAIT)")


def test_concurrent_socket_binding():
    """Test if multiple processes can cause port conflicts."""
    print("\n" + "=" * 60)
    print("TEST 4: Concurrent Socket Binding (simulating worker creation)")
    print("=" * 60)

    # Simulate what happens when multiple workers start simultaneously
    sockets = []
    ports = []

    for _ in range(10):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sockets.append(sock)
        ports.append(port)

    print(f"✓ Created {len(sockets)} sockets")
    print(f"  Ports: {ports}")

    # Check for duplicates
    if len(ports) != len(set(ports)):
        print("⚠ ERROR: Duplicate ports detected!")
        return False
    else:
        print("✓ All ports are unique")

    # Clean up
    for sock in sockets:
        sock.close()

    return True


def test_fd_passing():
    """Test if file descriptor passing to uvicorn works correctly."""
    print("\n" + "=" * 60)
    print("TEST 5: File Descriptor Passing to Child Process")
    print("=" * 60)

    # Create and bind socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    fd = sock.fileno()

    print(f"✓ Bound socket to port {port}, fd={fd}")

    # Test that we can pass the fd to a child process
    # We'll just verify the fd is valid for now
    try:
        # Get socket info from fd
        test_sock = socket.socket(fileno=fd)
        test_port = test_sock.getsockname()[1]
        print(f"✓ File descriptor {fd} is valid and points to port {test_port}")

        if test_port != port:
            print(f"⚠ ERROR: FD points to different port! Expected {port}, got {test_port}")
            return False

        return True
    except Exception as e:
        print(f"⚠ ERROR: Failed to use file descriptor: {e}")
        return False
    finally:
        sock.close()


def main():
    """Run all socket binding diagnostics."""
    print("\nSocket Binding Diagnostics")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Old socket binding", test_socket_binding_old_way()))
    results.append(("New socket binding", test_socket_binding_new_way()))
    test_port_reuse_timing()
    results.append(("Concurrent binding", test_concurrent_socket_binding()))
    results.append(("FD passing", test_fd_passing()))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\n{passed_count}/{total_count} tests passed")


if __name__ == "__main__":
    main()
