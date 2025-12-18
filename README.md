# pctx-sandbox

<div align="center">

[![Made by](https://img.shields.io/badge/MADE%20BY-Port%20of%20Context-1e40af.svg?style=for-the-badge&labelColor=0c4a6e)](https://portofcontext.com)
    <h2>from pctx_sandbox import sandbox</h1>

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

## Development

```bash
# Install with uv
uv sync

# Run tests
uv run pytest tests/unit/ -v

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy src/pctx_sandbox
```

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

- **macOS**: Lima (install: `brew install lima`) ✅
- **Linux**: Coming soon 🚧
- **Windows**: Coming soon 🚧

## Security Features

✅ Filesystem isolation (no access to ~/.ssh, ~/.aws, etc.)
✅ Environment variable isolation (no credential leakage)
✅ Syscall filtering (seccomp-bpf/firejail)
✅ Network isolation (blocked by default)
✅ Resource limits (CPU, memory, timeout)
✅ No privilege escalation
✅ Safe for untrusted LLM-generated code

## License

MIT
