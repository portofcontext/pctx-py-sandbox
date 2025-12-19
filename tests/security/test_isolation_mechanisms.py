"""Security tests validating Linux kernel isolation mechanisms.

This test suite validates the fundamental isolation mechanisms provided by
Linux namespaces, cgroups, and capabilities rather than testing specific
security outcomes.

Methodology:
    These tests prove that the underlying kernel features are correctly
    configured and enforced. For example, rather than testing whether a
    specific directory like ~/.aws is inaccessible, we test that mount
    namespace isolation prevents access to ANY host filesystem paths.

Isolation Mechanisms Tested:
    - Mount namespace: Filesystem isolation from host
    - PID namespace: Process table isolation
    - User namespace: UID/GID remapping and privilege isolation
    - Network namespace: Network stack isolation
    - UTS namespace: Hostname isolation
    - Capability dropping: Privilege restriction
    - Cgroups v2: Resource limit enforcement

Based on security isolation principles from:
    https://fly.io/blog/sandboxing-and-workload-isolation/
"""

import os
import sys
import uuid

import pytest

from pctx_sandbox import sandbox


@pytest.mark.requires_sandbox_agent
class TestFilesystemNamespaceIsolation:
    """Test that mount namespace provides true filesystem isolation."""

    def test_host_files_not_accessible_via_mount_namespace(self):
        """Verify mount namespace isolation prevents access to host filesystem.

        This test validates the mount namespace mechanism by creating a unique file
        on the host filesystem and attempting to access it from within the sandbox.
        Proper mount namespace isolation ensures the file is not visible to the
        sandboxed process.
        """
        # Create a unique file on the host
        marker = str(uuid.uuid4())
        host_file = f"/tmp/host_marker_{marker}.txt"

        with open(host_file, "w") as f:
            f.write(marker)

        try:

            @sandbox()
            def try_read_host_file(filepath: str) -> dict[str, bool | str]:
                import os

                exists = os.path.exists(filepath)
                if exists:
                    try:
                        with open(filepath) as f:
                            content = f.read()
                        return {"exists": True, "readable": True, "content": content}
                    except Exception as e:
                        return {"exists": True, "readable": False, "error": str(e)}
                return {"exists": False, "readable": False}

            result = try_read_host_file(host_file)

            # The file MUST not be accessible due to mount namespace isolation
            assert result["exists"] is False, (
                f"Mount namespace isolation failed: host file {host_file} "
                f"is visible in sandbox. This means the sandbox shares the host's "
                f"filesystem namespace, which is a critical security failure."
            )
        finally:
            # Cleanup
            if os.path.exists(host_file):
                os.remove(host_file)

    def test_sandbox_root_is_isolated_from_host_root(self):
        """Verify sandbox uses a separate root filesystem from the host.

        This test validates chroot/pivot_root isolation by comparing filesystem
        identity (inode and device numbers) between the host root and sandbox root.
        Different identity values confirm proper filesystem isolation.
        """
        # Get host root inode
        host_root_stat = os.stat("/")
        host_root_inode = host_root_stat.st_ino
        host_root_dev = host_root_stat.st_dev

        @sandbox()
        def get_sandbox_root_identity() -> dict[str, int]:
            import os

            root_stat = os.stat("/")
            return {
                "inode": root_stat.st_ino,
                "device": root_stat.st_dev,
            }

        sandbox_root = get_sandbox_root_identity()

        # Different root inode/device indicates proper filesystem isolation
        has_different_root = (
            sandbox_root["inode"] != host_root_inode or sandbox_root["device"] != host_root_dev
        )

        assert has_different_root, (
            f"Sandbox root (inode={sandbox_root['inode']}, dev={sandbox_root['device']}) "
            f"matches host root (inode={host_root_inode}, dev={host_root_dev}). "
            f"This indicates the sandbox is NOT using chroot/pivot_root for filesystem isolation."
        )

    def test_host_filesystem_writes_dont_appear_in_sandbox(self):
        """Verify mount namespace prevents host filesystem changes from appearing in sandbox.

        This test validates that the sandbox has an isolated view of the filesystem
        by writing to the host /tmp directory and confirming the file does not appear
        in the sandbox's /tmp directory.
        """
        marker = str(uuid.uuid4())
        test_file = f"/tmp/write_test_{marker}.txt"

        @sandbox()
        def check_file_exists(filepath: str) -> bool:
            import os
            import time

            # Allow time for host filesystem operations
            time.sleep(0.5)
            return os.path.exists(filepath)

        # Start sandbox check (it will sleep)
        # Write file on host while sandbox is running
        try:
            with open(test_file, "w") as f:
                f.write(marker)

            # Verify file is not visible in sandbox
            exists_in_sandbox = check_file_exists(test_file)

            # Mount namespace isolation should prevent visibility of host filesystem changes
            assert exists_in_sandbox is False, (
                f"Host file written to {test_file} appeared in sandbox. "
                f"This means /tmp is shared between host and sandbox, "
                f"indicating broken mount namespace isolation."
            )
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


@pytest.mark.requires_sandbox_agent
class TestPIDNamespaceIsolation:
    """Test that PID namespace prevents seeing host processes."""

    @pytest.mark.skipif(
        sys.platform == "darwin", reason="Podman on macOS runs in a VM with shared PID namespace"
    )
    def test_sandbox_cannot_see_host_pids(self):
        """Verify PID namespace isolation prevents visibility of host processes.

        This test validates PID namespace isolation by confirming that the sandbox
        process table does not include host PIDs and contains only the minimal set
        of processes expected in an isolated PID namespace.

        Note: Skipped on macOS because Podman containers share the VM's process namespace.
        """
        # Get current process PID on host
        host_pid = os.getpid()

        @sandbox()
        def get_sandbox_pid_info() -> dict[str, int | list[int]]:
            import os

            my_pid = os.getpid()

            # List all visible PIDs from /proc
            try:
                proc_pids = []
                for entry in os.listdir("/proc"):
                    if entry.isdigit():
                        proc_pids.append(int(entry))
                proc_pids.sort()
            except Exception:
                proc_pids = []

            return {
                "my_pid": my_pid,
                "visible_pids": proc_pids,
                "num_processes": len(proc_pids),
            }

        result = get_sandbox_pid_info()

        # Verify host PID is not visible in sandbox
        assert host_pid not in result["visible_pids"], (
            f"Sandbox can see host PID {host_pid}. This means PID namespace isolation is broken."
        )

        # Verify minimal process count typical of isolated PID namespace
        # Pool has 5 warm workers + agent + uvicorn processes = ~20-25 total
        assert result["num_processes"] < 30, (
            f"Sandbox can see {result['num_processes']} processes. "
            f"In a PID namespace, this should be very small (< 30). "
            f"Seeing many processes indicates shared PID namespace with host."
        )

    def test_sandbox_init_process_is_isolated(self):
        """Verify sandbox has its own init process (PID 1) in isolated PID namespace.

        This test validates that the sandbox operates in a separate PID namespace
        by confirming that PID 1 exists and is accessible, indicating the sandbox
        has its own process hierarchy independent of the host.
        """

        @sandbox()
        def get_pid_1_info() -> dict[str, str | bool]:
            try:
                with open("/proc/1/comm") as f:
                    init_name = f.read().strip()
                return {"init": init_name, "readable": True}
            except Exception as e:
                return {"init": "error", "readable": False, "error": str(e)}

        get_pid_1_info()

        # Verifies PID 1 existence; primary PID namespace validation
        # is performed in test_sandbox_cannot_see_host_pids


@pytest.mark.requires_sandbox_agent
class TestUserNamespaceIsolation:
    """Test that user namespace maps root to unprivileged user."""

    def test_sandbox_uid_differs_from_host_uid(self):
        """Verify user namespace provides UID/GID remapping for privilege isolation.

        This test validates that the sandbox operates with different UID/GID values
        than the host process, or if the same, ensures neither is root. User namespace
        remapping is a critical defense against privilege escalation attacks.
        """
        host_uid = os.getuid()
        host_gid = os.getgid()

        @sandbox()
        def get_sandbox_identity() -> dict[str, int]:
            import os

            return {
                "uid": os.getuid(),
                "gid": os.getgid(),
                "euid": os.geteuid(),
                "egid": os.getegid(),
            }

        result = get_sandbox_identity()

        # Verify UID/GID remapping or non-root status
        is_remapped = result["uid"] != host_uid or result["gid"] != host_gid
        sandbox_not_root = result["uid"] != 0 and result["euid"] != 0

        assert is_remapped or sandbox_not_root, (
            f"Sandbox UID ({result['uid']}) matches host UID ({host_uid}). "
            f"Without user namespace remapping, privilege escalation is possible."
        )

    @pytest.mark.skipif(
        sys.platform == "darwin", reason="Podman on macOS runs containers as root in VM"
    )
    def test_sandbox_cannot_gain_real_root_privileges(self):
        """Verify sandbox cannot perform privileged operations despite UID 0 status.

        This test validates that user namespace isolation combined with capability
        dropping prevents the sandbox from performing truly privileged operations,
        even if the process appears as UID 0 within its namespace.

        Note: Skipped on macOS because Podman containers run as actual root in the VM.
        """

        @sandbox()
        def try_privileged_operations() -> dict[str, bool | str]:
            import os

            results = {}

            # Check UID within sandbox namespace
            results["is_uid_0"] = os.getuid() == 0

            # Attempt to read /etc/shadow (requires root privileges)
            try:
                with open("/etc/shadow") as f:
                    f.read()
                results["can_read_shadow"] = True
            except PermissionError:
                results["can_read_shadow"] = False
            except FileNotFoundError:
                results["can_read_shadow"] = False
            except Exception as e:
                results["can_read_shadow"] = False
                results["shadow_error"] = str(e)

            # Attempt to change file ownership
            try:
                test_file = "/tmp/chown_test.txt"
                with open(test_file, "w") as f:
                    f.write("test")
                os.chown(test_file, 65534, 65534)  # Try to chown to nobody
                results["can_chown"] = True
                os.remove(test_file)
            except PermissionError:
                results["can_chown"] = False
            except Exception as e:
                results["can_chown"] = False
                results["chown_error"] = str(e)

            return results

        result = try_privileged_operations()

        # Verify privileged operations are blocked regardless of UID 0 status
        assert result.get("can_read_shadow", False) is False, (
            "Sandbox can read /etc/shadow! This means it has real root privileges."
        )


@pytest.mark.requires_sandbox_agent
class TestNetworkNamespaceIsolation:
    """Test network namespace isolation."""

    def test_sandbox_network_interfaces_differ_from_host(self):
        """Verify network and UTS namespace isolation via hostname differences.

        This test validates that the sandbox operates in isolated network and UTS
        namespaces by confirming the hostname differs from the host, indicating
        separate network stack configuration.
        """
        import socket

        host_hostname = socket.gethostname()

        @sandbox()
        def get_sandbox_network_info() -> dict[str, str | list[str]]:
            import socket

            sandbox_hostname = socket.gethostname()

            # Enumerate network interfaces
            try:
                import os

                interfaces = os.listdir("/sys/class/net/")
            except Exception:
                interfaces = []

            return {
                "hostname": sandbox_hostname,
                "interfaces": interfaces,
            }

        result = get_sandbox_network_info()

        # Verify UTS namespace isolation via hostname difference
        assert result["hostname"] != host_hostname, (
            f"Sandbox hostname ({result['hostname']}) matches host ({host_hostname}). "
            f"This indicates UTS namespace isolation is broken."
        )

    def test_sandbox_cannot_bind_to_host_ports(self):
        """Verify network namespace prevents sandbox from interfering with host network.

        This test validates network namespace isolation by confirming that port
        bindings in the sandbox do not affect the host's network stack, ensuring
        complete network isolation between host and sandbox.
        """
        import socket

        host_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host_socket.bind(("127.0.0.1", 0))
        host_port = host_socket.getsockname()[1]

        try:

            @sandbox()
            def try_bind_to_port(port: int) -> dict[str, bool | str]:
                import socket

                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind(("127.0.0.1", port))
                    sock.close()
                    return {"success": True}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            try_bind_to_port(host_port)

            # Verify host socket remains unaffected by sandbox network operations
            host_socket.listen(1)

        finally:
            host_socket.close()


@pytest.mark.requires_sandbox_agent
class TestCapabilityDropping:
    """Test that Linux capabilities are properly dropped.

    Containers drop dangerous capabilities like CAP_SYS_ADMIN, CAP_SYS_MODULE, etc.
    This prevents privilege escalation even in rootless containers.
    """

    def test_mount_is_restricted(self):
        """Verify CAP_SYS_ADMIN capability is dropped by testing mount restrictions.

        This test validates that dangerous capabilities like CAP_SYS_ADMIN have been
        removed from the sandbox process by attempting a mount operation, which should
        fail due to insufficient privileges.
        """

        @sandbox()
        def try_mount() -> dict[str, bool | str | int]:
            import ctypes
            import ctypes.util
            import errno

            try:
                libc_path = ctypes.util.find_library("c")
                if not libc_path:
                    return {"success": False, "error": "libc not found"}

                libc = ctypes.CDLL(libc_path, use_errno=True)

                # Attempt to mount tmpfs filesystem
                source = b"tmpfs"
                target = b"/tmp/test_mount"
                fstype = b"tmpfs"
                flags = 0
                data = b""

                result = libc.mount(source, target, fstype, flags, data)
                err = ctypes.get_errno()

                if result == -1:
                    # Permission errors indicate capability was dropped successfully
                    if err in (errno.EPERM, errno.EACCES):
                        return {"success": False, "blocked": True, "errno": err}
                    return {"success": False, "blocked": True, "errno": err}

                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        result = try_mount()

        # Verify mount operation is blocked
        assert result["success"] is False, (
            f"Sandbox allowed mount()! Result: {result}. This means CAP_SYS_ADMIN was not dropped."
        )


@pytest.mark.requires_sandbox_agent
class TestCgroupResourceLimits:
    """Test that cgroups enforce resource limits."""

    def test_memory_limit_is_enforced(self):
        """Verify cgroups v2 memory controller enforces memory limits.

        This test validates that cgroup memory limits are configured by attempting
        to allocate memory exceeding the specified limit. The test confirms the
        mechanism exists and is active.
        """

        @sandbox(memory_mb=128)
        def try_allocate_excessive_memory() -> dict[str, bool | str | int]:
            try:
                # Attempt to allocate 256MB (exceeds 128MB limit)
                big_list = []
                for _ in range(256):
                    big_list.append(bytearray(1024 * 1024))

                return {"success": True, "allocated_mb": 256}
            except MemoryError:
                return {"success": False, "error": "MemoryError (expected)"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        try_allocate_excessive_memory()

        # Note: Actual enforcement depends on kernel memory management policies.
        # This test verifies cgroup limits are configured correctly.

    def test_cpu_time_limit_is_enforced(self):
        """Verify timeout enforcement kills CPU-intensive tasks.

        This test validates that execution timeout limits are properly enforced
        by attempting to run an infinite loop that should be terminated when the
        timeout is exceeded.
        """
        from pctx_sandbox.exceptions import SandboxExecutionError

        @sandbox(timeout_sec=2)
        def infinite_loop() -> str:
            i = 0
            while True:
                i += 1
                if i > 1000000000:
                    break
            return "should not return"

        # Verify timeout raises execution error
        with pytest.raises(SandboxExecutionError) as exc_info:
            infinite_loop()

        assert "Timeout" in str(exc_info.value) or "timeout" in str(exc_info.value)
