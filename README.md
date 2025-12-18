
<div align="center">
<h1>pctx-sandbox </h1>

[![Made by](https://img.shields.io/badge/MADE%20BY-Port%20of%20Context-1e40af.svg?style=for-the-badge&labelColor=0c4a6e)](https://portofcontext.com)
    <h3><code>from pctx_sandbox import sandbox</code></h3>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>



A Python decorator that executes untrusted code in isolated sandboxes with defense-in-depth security, designed for safe execution of LLM-generated code on local machines.

## Installation

### macOS

1. Install Lima (required for VM isolation):
```bash
brew install lima
```

2. Install pctx-sandbox:
```bash
pip install pctx-sandbox
```

### Linux & Windows

Linux and Windows support is coming soon. Track progress at [GitHub Issues](https://github.com/portofcontext/python-sandbox/issues).

## Quick Start

```python
from pctx_sandbox import sandbox

@sandbox(dependencies=["pandas"])
def process_data(data: list[dict]) -> dict:
    import pandas as pd
    df = pd.DataFrame(data)
    return {"rows": len(df), "columns": list(df.columns)}

# Just call it normally - runs in isolated microVM
result = process_data([{"name": "Alice", "age": 30}])
```

## How Dependencies Work

The `@sandbox` decorator handles dependencies automatically:

1. **Specify dependencies** using standard pip syntax:
   ```python
   @sandbox(dependencies=["requests==2.31.0", "pandas>=2.0.0"])
   def fetch_and_process(url: str) -> dict:
       import requests
       import pandas as pd
       # Your code here
   ```

2. **Dependency caching** - Dependencies are installed once per unique set and cached:
   - Each unique combination of dependencies creates a persistent VM image
   - Subsequent runs with the same dependencies reuse the cached environment
   - Cache key is based on the sorted list of dependencies

3. **Isolation guarantees**:
   - Dependencies are installed only in the sandbox environment
   - Your host system remains unchanged
   - Different sandboxes can use conflicting dependency versions

4. **No dependencies needed?** Just omit the parameter:
   ```python
   @sandbox()
   def safe_computation(x: int) -> int:
       return x ** 2
   ```

## Development

```bash
# Install dependencies
make install

# Run tests
make test

# Format code
make format

# Lint code
make lint

# Type check
make type-check

# See all available commands
make help
```

<details>
<summary>Direct uv commands (if not using make)</summary>

```bash
# Install with uv
uv sync --all-extras

# Run tests
uv run pytest tests/unit/ -v

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy src/pctx_sandbox
```
</details>

## How It Works

**Defense-in-Depth Security Architecture:**

### macOS (Supported)
```
Host System
  └── Lima VM (Ubuntu)
      └── Firejail Sandbox
          └── Isolated Python Process
```

1. **VM Isolation (Lima)**: Isolated filesystem, environment, and resources
2. **Process Sandboxing (Firejail)**: Syscall filtering, capability dropping, network isolation
3. **Execution**: Functions run with no access to host credentials, files, or processes

### Linux (Coming Soon)
```
Host System
  └── Firejail/Bubblewrap Sandbox
      └── Isolated Python Process
```

Planned: Native process sandboxing with firejail or bubblewrap

### Windows (Coming Soon)

Planned: WSL2-based backend

## Requirements

- **macOS**: Lima (install: `brew install lima`)
- **Linux**: Coming soon 🚧
- **Windows**: Coming soon 🚧

## Security Features

### Security Validation

All security claims are validated by comprehensive tests in [tests/security/test_sandbox_security.py](tests/security/test_sandbox_security.py). The test suite covers:

- **Filesystem Isolation**: Verifies host credentials (SSH keys, AWS/GCP credentials) are inaccessible
- **Environment Isolation**: Ensures host environment variables don't leak into sandbox
- **Network Isolation**: Confirms network access is blocked by default
- **Process Isolation**: Validates sandbox cannot see or interact with host processes
- **Privilege Isolation**: Tests that privilege escalation (root, sudo, chown) is blocked
- **Resource Limits**: Confirms timeouts and memory limits are enforced
- **Syscall Filtering**: Verifies dangerous syscalls (ptrace, mount) are blocked

Run security tests:
```bash
uv run pytest tests/security/ -v
```

## License

MIT
