
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

Install Lima and QEMU (required for VM isolation):
```bash
brew install qemu lima
```

Install pctx-sandbox:
```bash
pip install pctx-sandbox
```

### Linux

Install nsjail (required for process sandboxing):

**Ubuntu/Debian**
```bash
# Use the installation script
curl -fsSL https://raw.githubusercontent.com/portofcontext/python-sandbox/main/scripts/install-linux-deps.sh | bash
```
or have a look at `scripts/install-linux-deps.sh` to install manually

**Other distributions:** See [nsjail installation guide](https://github.com/google/nsjail)

Install pctx-sandbox:
```bash
pip install pctx-sandbox
```

### Windows

Windows support is coming soon.

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

2. **Dependency caching with warm pools** - Dependencies are installed once and reused:
   - Each unique combination of dependencies creates a cached virtual environment
   - A pool of warm workers is maintained per dependency set for instant execution
   - Workers are automatically rotated after 100 jobs or 1 hour
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

## VM Management (macOS)

The Lima VM auto-starts on first use. To manage it manually:

```bash
limactl list                         # Check VM status
limactl delete --force pctx-sandbox  # Delete for fresh start
limactl stop pctx-sandbox            # Stop the VM
```

## Development


# See all available commands
make help
```

## How It Works

**Defense-in-Depth Security Architecture:**

### macOS
```
Host System
  └── Lima VM (Ubuntu)
      └── nsjail Sandbox with Warm Process Pool
          └── Isolated Python Workers
```

1. **VM Isolation (Lima)**: Isolated filesystem, environment, and resources
2. **Process Sandboxing (nsjail)**: Linux namespaces, cgroups, seccomp-bpf syscall filtering
3. **Warm Process Pool**: Pre-initialized workers for fast execution (no cold-start overhead)
4. **Resource Limits**: Enforced CPU and memory limits via cgroups
5. **Execution**: Functions run with no access to host credentials, files, or processes

### Linux
```
Host System
  └── nsjail Sandbox with Warm Process Pool
      └── Isolated Python Workers
```

1. **Process Sandboxing (nsjail)**: Linux namespaces, cgroups, seccomp-bpf syscall filtering
2. **Warm Process Pool**: Pre-initialized workers for fast execution (no cold-start overhead)
3. **Resource Limits**: Enforced CPU and memory limits via cgroups
4. **Execution**: Functions run with no access to host credentials, files, or processes

### Windows (Coming Soon)

Planned: WSL2-based backend

## Requirements

- **macOS**: QEMU + Lima (install: `brew install qemu lima`)
- **Linux**: nsjail (see installation instructions above) + Python 3.10+
- **Windows**: Coming soon

## Security

### Why nsjail Provides Strong Isolation

[nsjail](https://github.com/google/nsjail) is a **lightweight process isolation tool developed by Google** that provides security comparable to Docker containers, but with better performance (20ms subprocess creation vs Docker's slower container startup).

**Core Security Mechanisms:**

1. **Linux Namespaces** - Complete process isolation using 7 namespace types:
   - **PID namespace**: Sandboxed processes cannot see host processes
   - **Mount namespace**: Isolated filesystem, cannot access host files
   - **Network namespace**: Network isolation (configurable)
   - **User namespace**: Root in sandbox maps to unprivileged user on host
   - **IPC namespace**: No shared memory with host processes
   - **UTS namespace**: Separate hostname
   - **Cgroup namespace**: Isolated cgroup view

2. **Seccomp-BPF Syscall Filtering** - Blocks dangerous system calls like `ptrace`, `mount`, `reboot`, etc. using Kafel BPF language for fine-grained control

3. **Cgroups v2** - Enforces resource limits:
   - CPU time limits
   - Memory limits
   - Process count limits
   - Network bandwidth control

4. **Capability Dropping** - Removes Linux capabilities (even from root user in sandbox)

5. **Read-only Filesystem** - Mounts can be configured as read-only to prevent tampering

**Proven in Production:**

- Used by Google for [kCTF](https://google.github.io/kctf/introduction.html) (Kubernetes CTF infrastructure)
- Powers isolation in [Fly.io's sandboxing infrastructure](https://fly.io/blog/sandboxing-and-workload-isolation/)
- Standard tool for CTF (Capture The Flag) security competitions

**Defense-in-Depth on macOS:**

On macOS, pctx-sandbox adds an additional VM layer (Lima) because macOS lacks Linux namespaces.

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

Like Docker containers, nsjail provides [strong isolation but not a perfect security boundary](https://www.helpnetsecurity.com/2025/05/20/containers-namespaces-security/). Linux namespaces were designed for resource partitioning, not security isolation. While they provide excellent defense-in-depth:

- All sandboxed processes share the same Linux kernel
- Kernel vulnerabilities could potentially allow escapes
- Side-channel attacks (Spectre, Meltdown) may leak information

**Best Practices:**
- Keep your kernel updated with security patches
- Use on systems with recent kernels (5.10+) that have namespace security improvements
- Consider the VM-based approach (macOS) for maximum isolation of highly untrusted code
- Monitor for kernel CVEs related to namespaces and containers

## License

MIT
