"""Tests for sandbox decorator."""

import hashlib
from unittest.mock import Mock, patch

import cloudpickle
import pytest

from pctx_sandbox.decorator import _get_client, sandbox, sandbox_async
from pctx_sandbox.exceptions import SandboxExecutionError


class TestGetClient:
    """Tests for _get_client function."""

    def test_creates_client_lazily(self):
        """Should create client on first call."""
        # Reset global client
        import pctx_sandbox.decorator

        pctx_sandbox.decorator._client = None

        with (
            patch("pctx_sandbox.decorator.get_backend") as mock_backend_fn,
            patch("pctx_sandbox.decorator.SandboxClient") as mock_client_class,
        ):
            mock_backend = Mock()
            mock_backend.agent_url = "http://localhost:9000"
            mock_backend_fn.return_value = mock_backend

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            client = _get_client()

            # Backend should be created and ensure_running called
            mock_backend_fn.assert_called_once()
            mock_backend.ensure_running.assert_called_once()

            # Client should be created
            mock_client_class.assert_called_once_with(base_url="http://localhost:9000", timeout=30)
            mock_client.wait_for_healthy.assert_called_once()

            assert client == mock_client

    def test_reuses_existing_client(self):
        """Should reuse client on subsequent calls."""
        import pctx_sandbox.decorator

        # Set up an existing client
        mock_client = Mock()
        pctx_sandbox.decorator._client = mock_client

        with patch("pctx_sandbox.decorator.get_backend") as mock_backend_fn:
            client = _get_client()

            # Should not create new backend
            mock_backend_fn.assert_not_called()

            # Should return existing client
            assert client == mock_client


class TestSandboxDecorator:
    """Tests for @sandbox decorator."""

    def setup_method(self):
        """Reset global client before each test."""
        import pctx_sandbox.decorator

        pctx_sandbox.decorator._client = None

    def test_decorator_without_arguments(self):
        """Should work with default arguments."""

        @sandbox()
        def add(a: int, b: int) -> int:
            return a + b

        assert callable(add)
        assert hasattr(add, "_is_sandboxed")
        assert add._is_sandboxed is True

    def test_decorator_with_dependencies(self):
        """Should store dependencies in config."""

        @sandbox(dependencies=["pandas", "numpy"])
        def process_data(data: list) -> int:
            return len(data)

        assert process_data._sandbox_config["dependencies"] == ["pandas", "numpy"]

    def test_decorator_with_memory_limit(self):
        """Should store memory limit in config."""

        @sandbox(memory_mb=1024)
        def heavy_task() -> None:
            pass

        assert heavy_task._sandbox_config["memory_mb"] == 1024

    def test_decorator_with_timeout(self):
        """Should store timeout in config."""

        @sandbox(timeout_sec=60)
        def long_task() -> None:
            pass

        assert long_task._sandbox_config["timeout_sec"] == 60

    def test_function_execution_calls_client(self):
        """Should call client.execute with correct payload."""
        mock_client = Mock()
        mock_client.execute.return_value = {
            "success": True,
            "result_pickle": cloudpickle.dumps(42),
        }

        with patch("pctx_sandbox.decorator._get_client", return_value=mock_client):

            @sandbox()
            def add(a: int, b: int) -> int:
                return a + b

            result = add(1, 2)

            # Client execute should be called
            mock_client.execute.assert_called_once()

            # Check payload structure
            payload = mock_client.execute.call_args[0][0]
            assert "fn_pickle" in payload
            assert "args_pickle" in payload
            assert "kwargs_pickle" in payload
            assert "dependencies" in payload
            assert "dep_hash" in payload

            # Result should be deserialized
            assert result == 42

    def test_function_execution_with_kwargs(self):
        """Should handle keyword arguments correctly."""
        mock_client = Mock()
        mock_client.execute.return_value = {
            "success": True,
            "result_pickle": cloudpickle.dumps("hello world"),
        }

        with patch("pctx_sandbox.decorator._get_client", return_value=mock_client):

            @sandbox()
            def greet(name: str, greeting: str = "Hello") -> str:
                return f"{greeting} {name}"

            _ = greet("Alice", greeting="Hi")

            payload = mock_client.execute.call_args[0][0]
            kwargs = cloudpickle.loads(payload["kwargs_pickle"])
            assert kwargs == {"greeting": "Hi"}

    def test_dependency_hash_generation(self):
        """Should generate consistent dependency hash."""

        @sandbox(dependencies=["pandas", "numpy"])
        def func1() -> None:
            pass

        @sandbox(dependencies=["numpy", "pandas"])  # Different order
        def func2() -> None:
            pass

        # Hash should be the same (sorted)
        expected_hash = hashlib.sha256(b"numpy,pandas").hexdigest()[:16]
        assert func1._sandbox_config["dep_hash"] == expected_hash
        assert func2._sandbox_config["dep_hash"] == expected_hash

    def test_error_handling_raises_sandbox_execution_error(self):
        """Should raise SandboxExecutionError on remote errors."""
        mock_client = Mock()
        mock_client.execute.return_value = {
            "error": True,
            "error_type": "ValueError",
            "error_message": "Invalid input",
            "traceback": "Traceback...",
        }

        with patch("pctx_sandbox.decorator._get_client", return_value=mock_client):

            @sandbox()
            def failing_func() -> None:
                raise ValueError("Invalid input")

            with pytest.raises(SandboxExecutionError) as exc_info:
                failing_func()

            assert "ValueError" in str(exc_info.value)
            assert "Invalid input" in str(exc_info.value)

    def test_preserves_function_metadata(self):
        """Should preserve original function name and docstring."""

        @sandbox()
        def my_function(x: int) -> int:
            """This is my function."""
            return x * 2

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."

    def test_memory_cpu_config_in_payload(self):
        """Should include memory and CPU config in payload."""
        mock_client = Mock()
        mock_client.execute.return_value = {
            "success": True,
            "result_pickle": cloudpickle.dumps(None),
        }

        with patch("pctx_sandbox.decorator._get_client", return_value=mock_client):

            @sandbox(memory_mb=2048, cpus=4)
            def task() -> None:
                pass

            task()

            payload = mock_client.execute.call_args[0][0]
            assert payload["memory_mb"] == 2048
            assert payload["cpus"] == 4


class TestSandboxAsyncDecorator:
    """Tests for @sandbox_async decorator."""

    def setup_method(self):
        """Reset global client before each test."""
        import pctx_sandbox.decorator

        pctx_sandbox.decorator._client = None

    @pytest.mark.asyncio
    async def test_async_decorator_basic(self):
        """Should work with async functions."""
        mock_client = Mock()

        async def mock_execute_async(payload):
            return {"success": True, "result_pickle": cloudpickle.dumps(42)}

        mock_client.execute_async = mock_execute_async

        with patch("pctx_sandbox.decorator._get_client", return_value=mock_client):

            @sandbox_async()
            async def add_async(a: int, b: int) -> int:
                return a + b

            result = await add_async(1, 2)
            assert result == 42

    @pytest.mark.asyncio
    async def test_async_payload_includes_flag(self):
        """Should set is_async flag in payload."""
        mock_client = Mock()
        payload_captured = None

        async def mock_execute_async(payload):
            nonlocal payload_captured
            payload_captured = payload
            return {"success": True, "result_pickle": cloudpickle.dumps(None)}

        mock_client.execute_async = mock_execute_async

        with patch("pctx_sandbox.decorator._get_client", return_value=mock_client):

            @sandbox_async()
            async def async_task() -> None:
                pass

            await async_task()

            assert payload_captured is not None
            assert payload_captured["is_async"] is True
