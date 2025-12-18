# Sandbox Agent

The `simple_agent.py` provides defense-in-depth security by combining VM isolation with process-level sandboxing.

## Architecture

**macOS (Lima VM + Firejail):**
```
Host System
  └── Lima VM (Ubuntu)
      └── Firejail Sandbox
          └── Isolated Python Process
```

**Security Layers:**
1. **VM Isolation (Lima)**: Isolated filesystem, environment, and resources
2. **Process Sandboxing (Firejail)**: Syscall filtering, capability dropping, network isolation

## Security Features

- ✅ No access to host credentials (SSH keys, AWS creds, etc.)
- ✅ Environment variable isolation
- ✅ Seccomp-bpf syscall filtering
- ✅ Network blocked by default (`--net=none`)
- ✅ No privilege escalation
- ✅ All capabilities dropped
- ✅ Resource limits (CPU, memory, timeout)

## API Endpoints

### POST /execute
Execute a function in the sandbox with full isolation.

**Request:** msgpack-encoded payload
```python
{
    "fn_pickle": bytes,        # Cloudpickle-serialized function
    "args_pickle": bytes,      # Cloudpickle-serialized args
    "kwargs_pickle": bytes,    # Cloudpickle-serialized kwargs
    "dependencies": list[str], # pip packages to install
    "dep_hash": str,           # Hash of dependencies
    "timeout_sec": int,        # Execution timeout
}
```

**Response:** msgpack-encoded result
```python
{
    "error": bool,
    "result_pickle": bytes,    # If success
    "error_type": str,         # If error
    "error_message": str,      # If error
    "traceback": str,          # If error
}
```

### GET /health
Health check endpoint.

**Response:** `{"status": "ok"}`

### GET /status
View cached virtual environments.

**Response:**
```python
{
    "cached_envs": list[str],  # Dependency hashes
    "cache_dir": str,          # Cache directory path
}
```

## Running the Agent

The agent is automatically started by the Lima backend when you use the `@sandbox` decorator.

### Manual Startup (Development)

```bash
# SSH into Lima VM
limactl shell pctx-sandbox

# Install dependencies
python3 -m venv agent-env
source agent-env/bin/activate
pip install fastapi uvicorn cloudpickle msgpack

# Run the agent
python simple_agent.py
```

## Implementation Details

### Virtual Environment Caching

Dependencies are installed once per unique dependency set and cached:
- Cache key: SHA256 hash of sorted dependency list
- Cache location: `/tmp/pctx-cache/venv-{hash}`
- Reused across executions with same dependencies

### Firejail Security Profile

```bash
firejail \
  --quiet \
  --private-dev      # Minimal /dev
  --noroot           # Prevent root escalation
  --seccomp          # Syscall filtering
  --caps.drop=all    # Drop all capabilities
  --nonewprivs       # Prevent privilege escalation
  --net=none         # No network access
  -- python -c "..."
```

### Async Function Handling

The agent automatically detects and handles async functions:
```python
result = fn(*args, **kwargs)
if asyncio.iscoroutine(result):
    result = asyncio.run(result)
```
