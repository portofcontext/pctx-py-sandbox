
<div align="center">
<h1>pctx-sandbox </h1>

[![Made by](https://img.shields.io/badge/MADE%20BY-Port%20of%20Context-1e40af.svg?style=for-the-badge&labelColor=0c4a6e)](https://portofcontext.com)
    <h3><code>from pctx_sandbox import sandbox</code></h3>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>



A Python decorator that executes untrusted code in isolated Podman containers, designed for safe execution of LLM-generated code on local machines.

## Installation

### Prerequisites

Install Podman (required for container isolation):

**macOS**
```bash
brew install podman
podman machine init
podman machine start
```

**Linux (Ubuntu/Debian)**
```bash
sudo apt-get update
sudo apt-get install podman
```

**Linux (Fedora/RHEL)**
```bash
sudo dnf install podman
```

### Install pctx-sandbox

```bash
pip install pctx-sandbox
```

## Quick Start

```python
from pctx_sandbox import sandbox

@sandbox(dependencies=["pandas"])
def process_data(data: list[dict]) -> dict:
    import pandas as pd
    df = pd.DataFrame(data)
    return {"rows": len(df), "columns": list(df.columns)}

# Just call it normally - runs in isolated Podman container
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

2. **Dependency caching with warm pools** - Dependencies are installed once and reused:
   - Each unique combination of dependencies creates a cached virtual environment
   - A pool of warm workers is maintained per dependency set for instant execution
   - Workers are automatically rotated after 100 jobs or 1 hour
   - Cache key is based on the sorted list of dependencies

3. **Isolation guarantees**:
   - Dependencies are installed only in the sandbox environment
   - Your host system remains unchanged
   - Different sandboxes can use conflicting dependency versions

4. **No dependencies** omit the parameter:
   ```python
   @sandbox()
   def safe_computation(x: int) -> int:
       return x ** 2
   ```

## Container Management

The Podman container auto-starts on first use. To manage it manually:

```bash
podman ps                                    # Check container status
podman stop pctx-sandbox-agent              # Stop the container
podman rm -f pctx-sandbox-agent             # Remove container
podman rmi -f pctx-sandbox-agent            # Remove image
```

## Development

```bash
# See all available commands
make help
```

## How It Works

**Container-Based Security Architecture:**

```
Host System
  └── Podman Container (Rootless)
      └── Warm Process Pool
          └── Isolated Python Workers
```

1. **Container Isolation (Podman)**: Rootless containers with isolated filesystem, environment, and resources
2. **Warm Process Pool**: Pre-initialized workers for fast execution (no cold-start overhead)
3. **Resource Limits**: Enforced CPU and memory limits via cgroups
4. **Execution**: Functions run with no access to host credentials, files, or processes

## Requirements

- **Podman** (see installation instructions above)
- **Python 3.10+**

## Security

### Podman Provides Strong Isolation

[Podman](https://podman.io/) is a **daemonless container engine** that provides OCI-standard container isolation with rootless execution by default.

**Core Security Mechanisms:**

1. **OCI Container Isolation** - Complete process isolation using:
   - **PID namespace**: Containerized processes cannot see host processes
   - **Mount namespace**: Isolated filesystem, cannot access host files
   - **Network namespace**: Network isolation (configurable)
   - **User namespace**: Rootless containers map to unprivileged user on host
   - **IPC namespace**: No shared memory with host processes
   - **UTS namespace**: Separate hostname
   - **Cgroup namespace**: Isolated cgroup view

2. **Rootless by Default** - Runs entirely as non-root user, no daemon needed

3. **Cgroups v2** - Enforces resource limits:
   - CPU time limits
   - Memory limits
   - Process count limits
   - I/O bandwidth control

4. **SELinux/AppArmor Integration** - Additional security layers where available

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

### Limitations

**Not a Security Boundary (Same as Docker):**

Like all container solutions, Podman provides [strong isolation but not a perfect security boundary](https://www.helpnetsecurity.com/2025/05/20/containers-namespaces-security/). Linux namespaces were designed for resource partitioning, not security isolation.

## License

MIT
