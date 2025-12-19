"""Sandbox worker - runs inside Podman container, executes code via HTTP protocol."""

import asyncio
import base64
import sys
import traceback
from typing import Any

import cloudpickle
import uvicorn
from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/execute")
async def execute(request: Request) -> dict[str, Any]:
    """Execute a sandboxed function.

    Request body (JSON):
        {
            "fn_pickle": base64-encoded pickled function,
            "args_pickle": base64-encoded pickled args tuple,
            "kwargs_pickle": base64-encoded pickled kwargs dict,
        }

    Returns:
        {
            "error": false,
            "result_pickle": base64-encoded pickled result
        }
        OR
        {
            "error": true,
            "error_type": "ExceptionName",
            "error_message": "error message",
            "traceback": "full traceback"
        }
    """
    try:
        data = await request.json()

        # Decode and unpickle
        fn = cloudpickle.loads(base64.b64decode(data["fn_pickle"]))
        args = cloudpickle.loads(base64.b64decode(data["args_pickle"]))
        kwargs = cloudpickle.loads(base64.b64decode(data["kwargs_pickle"]))

        # Execute the function
        result = fn(*args, **kwargs)

        # Handle async functions
        if asyncio.iscoroutine(result):
            result = await result

        # Return success response
        return {
            "error": False,
            "result_pickle": base64.b64encode(cloudpickle.dumps(result)).decode("ascii"),
        }

    except Exception as e:
        # Return error response
        return {
            "error": True,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    """Start the worker HTTP server.

    Binds to a free port and signals readiness AFTER the socket is bound
    to eliminate race conditions.
    """
    import socket

    # Create socket and bind to find a free port
    # Keep socket open to prevent port reuse race condition
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    # Signal readiness to parent process via stdout
    # Port is now guaranteed to be ours since socket is bound
    sys.stdout.write(f"READY:{port}\n")
    sys.stdout.flush()

    # Start server using the already-bound socket
    # Pass file descriptor to uvicorn
    uvicorn.run(
        app,
        fd=sock.fileno(),
        log_level="error",
        access_log=False,
    )


if __name__ == "__main__":
    main()
