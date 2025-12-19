"""Sandbox worker - runs inside nsjail, executes code via stdio protocol."""

import asyncio
import base64
import sys
import traceback

import cloudpickle


def read_exact(n: int) -> bytes:
    """Read exactly n bytes from stdin."""
    data = b""
    while len(data) < n:
        chunk = sys.stdin.buffer.read(n - len(data))
        if not chunk:
            return data  # EOF
        data += chunk
    return data


async def main() -> None:
    """Main worker loop - reads jobs from stdin, executes, writes results to stdout."""
    while True:
        try:
            # Read length-prefixed message from stdin
            length_bytes = await asyncio.get_event_loop().run_in_executor(None, read_exact, 4)

            if len(length_bytes) < 4:
                # EOF - parent closed connection, exit gracefully
                break

            msg_length = int.from_bytes(length_bytes, byteorder="big")

            # Read the message payload
            msg_bytes = await asyncio.get_event_loop().run_in_executor(None, read_exact, msg_length)

            # Decode the job
            job_data = cloudpickle.loads(base64.b64decode(msg_bytes))

            # Execute the function
            try:
                fn = cloudpickle.loads(job_data["fn_pickle"])
                args = cloudpickle.loads(job_data["args_pickle"])
                kwargs = cloudpickle.loads(job_data["kwargs_pickle"])

                result = fn(*args, **kwargs)

                # Handle async functions
                if asyncio.iscoroutine(result):
                    result = await result

                output = {"error": False, "result_pickle": cloudpickle.dumps(result)}

            except Exception as e:
                output = {
                    "error": True,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                }

            # Send result back
            result_bytes = base64.b64encode(cloudpickle.dumps(output))
            result_length = len(result_bytes).to_bytes(4, byteorder="big")

            sys.stdout.buffer.write(result_length)
            sys.stdout.buffer.write(result_bytes)
            sys.stdout.buffer.flush()

        except Exception as e:
            # Worker-level error (not execution error)
            error_output = {
                "error": True,
                "error_type": "WorkerError",
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            }

            result_bytes = base64.b64encode(cloudpickle.dumps(error_output))
            result_length = len(result_bytes).to_bytes(4, byteorder="big")

            sys.stdout.buffer.write(result_length)
            sys.stdout.buffer.write(result_bytes)
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    asyncio.run(main())
