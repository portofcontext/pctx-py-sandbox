"""Basic example of using pctx-sandbox."""

from pctx_sandbox import sandbox


@sandbox()
def add_numbers(a: int, b: int) -> int:
    """A simple function that adds two numbers in a sandbox."""
    return a + b


@sandbox(dependencies=["requests"])
def fetch_example() -> dict:
    """Example with dependencies."""

    # This would normally make a network request
    # For demo purposes, we'll just return a dict
    return {"status": "would fetch data", "library": "requests"}


@sandbox(memory_mb=1024, timeout_sec=60, cpus=2)
def heavy_computation(n: int) -> int:
    """Example with custom resource limits."""
    # Simulate some heavy work
    result = 0
    for i in range(n):
        result += i
    return result


if __name__ == "__main__":
    # Note: These would actually execute in a sandbox if the infrastructure was set up
    # For now, they demonstrate the API

    print("Basic addition example:")
    print("add_numbers(5, 3) would return: 8")

    print("\nWith dependencies:")
    print("fetch_example() would use requests library")

    print("\nWith custom resources:")
    print("heavy_computation(1000) would run with 1GB RAM, 2 CPUs")

    print("\nFunction metadata:")
    print(f"Is sandboxed: {add_numbers._is_sandboxed}")
    print(f"Config: {add_numbers._sandbox_config}")
