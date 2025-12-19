"""Sandbox decorator implementation."""

import functools
import hashlib
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

import cloudpickle

from .client import SandboxClient
from .exceptions import SandboxExecutionError
from .platform import get_backend

# Global lazy-initialized client
_client: SandboxClient | None = None

# Type variable for decorator return type
F = TypeVar("F", bound=Callable[..., Any])


def _get_client() -> SandboxClient:
    """Get or create the global sandbox client.

    Returns:
        Initialized and ready SandboxClient
    """
    global _client
    if _client is None:
        backend = get_backend()
        backend.ensure_running()
        _client = SandboxClient(base_url=backend.agent_url, timeout=30)
        _client.wait_for_healthy()
    return _client


def sandbox(
    dependencies: list[str] | None = None,
    memory_mb: int = 1024,
    timeout_sec: int = 30,
    cpus: int = 1,
    allow_network: list[str] | None = None,
    disable_cache: bool = False,
) -> Callable[[F], F]:
    """Decorator that runs a function in an isolated sandbox.

    Args:
        dependencies: pip packages to install (e.g., ["pandas>=2.0", "numpy"])
        memory_mb: Memory limit for the sandbox
        timeout_sec: Maximum execution time
        cpus: Number of CPUs
        allow_network: List of allowed hostnames (None = no network)
        disable_cache: If True, bypass dependency cache (forces fresh install)

    Returns:
        Decorated function that executes in sandbox

    Example:
        >>> @sandbox(dependencies=["pandas"])
        ... def process_data(data: list) -> dict:
        ...     import pandas as pd
        ...     df = pd.DataFrame(data)
        ...     return {"rows": len(df)}
    """
    dependencies = dependencies or []
    allow_network = allow_network or []

    # Hash dependencies for snapshot cache key
    # If cache is disabled, add a unique timestamp to force cache miss
    if disable_cache:
        import time

        cache_buster = str(time.time())
        dep_hash = hashlib.sha256(
            f"{','.join(sorted(dependencies))},{cache_buster}".encode()
        ).hexdigest()[:16]
    else:
        dep_hash = hashlib.sha256(",".join(sorted(dependencies)).encode()).hexdigest()[:16]

    def decorator(fn: F) -> F:
        # Check if function is async
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                client = _get_client()

                # Serialize the function and arguments
                payload = {
                    "fn_pickle": cloudpickle.dumps(fn),
                    "args_pickle": cloudpickle.dumps(args),
                    "kwargs_pickle": cloudpickle.dumps(kwargs),
                    "dependencies": dependencies,
                    "dep_hash": dep_hash,
                    "memory_mb": memory_mb,
                    "timeout_sec": timeout_sec,
                    "cpus": cpus,
                    "allow_network": allow_network,
                }

                # Execute in sandbox asynchronously
                response = await client.execute_async(payload)

                # Handle errors
                if response.get("error"):
                    error_type = response["error_type"]
                    error_msg = response["error_message"]
                    traceback_str = response.get("traceback", "")

                    raise SandboxExecutionError(
                        f"{error_type}: {error_msg}\n{traceback_str}",
                        error_type=error_type,
                        traceback_str=traceback_str,
                    )

                # Deserialize and return result
                return cloudpickle.loads(response["result_pickle"])

            # Mark as sandboxed for introspection
            async_wrapper._is_sandboxed = True  # type: ignore
            async_wrapper._sandbox_config = {  # type: ignore
                "dependencies": dependencies,
                "memory_mb": memory_mb,
                "timeout_sec": timeout_sec,
                "dep_hash": dep_hash,
            }

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                client = _get_client()

                # Serialize the function and arguments
                payload = {
                    "fn_pickle": cloudpickle.dumps(fn),
                    "args_pickle": cloudpickle.dumps(args),
                    "kwargs_pickle": cloudpickle.dumps(kwargs),
                    "dependencies": dependencies,
                    "dep_hash": dep_hash,
                    "memory_mb": memory_mb,
                    "timeout_sec": timeout_sec,
                    "cpus": cpus,
                    "allow_network": allow_network,
                }

                # Execute in sandbox
                response = client.execute(payload)

                # Handle errors
                if response.get("error"):
                    error_type = response["error_type"]
                    error_msg = response["error_message"]
                    traceback_str = response.get("traceback", "")

                    raise SandboxExecutionError(
                        f"{error_type}: {error_msg}\n{traceback_str}",
                        error_type=error_type,
                        traceback_str=traceback_str,
                    )

                # Deserialize and return result
                return cloudpickle.loads(response["result_pickle"])

            # Mark as sandboxed for introspection
            sync_wrapper._is_sandboxed = True  # type: ignore
            sync_wrapper._sandbox_config = {  # type: ignore
                "dependencies": dependencies,
                "memory_mb": memory_mb,
                "timeout_sec": timeout_sec,
                "dep_hash": dep_hash,
            }

            return sync_wrapper  # type: ignore

    return decorator


def sandbox_async(
    dependencies: list[str] | None = None,
    memory_mb: int = 1024,
    timeout_sec: int = 30,
    cpus: int = 1,
    allow_network: list[str] | None = None,
    disable_cache: bool = False,
) -> Callable[[F], F]:
    """Async version of @sandbox decorator.

    Args:
        dependencies: pip packages to install
        memory_mb: Memory limit for the microVM
        timeout_sec: Maximum execution time
        cpus: Number of vCPUs
        allow_network: List of allowed hostnames
        disable_cache: If True, bypass dependency cache (forces fresh install)

    Returns:
        Decorated async function that executes in sandbox
    """
    dependencies = dependencies or []
    allow_network = allow_network or []

    # Hash dependencies for snapshot cache key
    # If cache is disabled, add a unique timestamp to force cache miss
    if disable_cache:
        import time

        cache_buster = str(time.time())
        dep_hash = hashlib.sha256(
            f"{','.join(sorted(dependencies))},{cache_buster}".encode()
        ).hexdigest()[:16]
    else:
        dep_hash = hashlib.sha256(",".join(sorted(dependencies)).encode()).hexdigest()[:16]

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = _get_client()

            payload = {
                "fn_pickle": cloudpickle.dumps(fn),
                "args_pickle": cloudpickle.dumps(args),
                "kwargs_pickle": cloudpickle.dumps(kwargs),
                "dependencies": dependencies,
                "dep_hash": dep_hash,
                "memory_mb": memory_mb,
                "timeout_sec": timeout_sec,
                "cpus": cpus,
                "allow_network": allow_network,
                "is_async": True,
            }

            response = await client.execute_async(payload)

            if response.get("error"):
                raise SandboxExecutionError(response["error_message"])

            return cloudpickle.loads(response["result_pickle"])

        wrapper._is_sandboxed = True  # type: ignore
        wrapper._sandbox_config = {  # type: ignore
            "dependencies": dependencies,
            "memory_mb": memory_mb,
            "timeout_sec": timeout_sec,
            "dep_hash": dep_hash,
        }

        return wrapper  # type: ignore

    return decorator
