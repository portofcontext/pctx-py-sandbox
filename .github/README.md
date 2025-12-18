# GitHub Actions CI/CD

This directory contains all GitHub Actions workflows for the pctx-sandbox project.

## Quick Summary

✅ **5 Workflows Configured**
✅ **70 Unit Tests**
✅ **9 Platform/Python Combinations**
✅ **All Platforms Tested** (Ubuntu, macOS, Windows)
✅ **Python 3.10, 3.11, 3.12 Support**

## Workflows

### 1. [test.yml](./workflows/test.yml) - Main Test Suite
- **Runs on**: Push to `main`/`develop`, Pull Requests
- **Matrix Testing**: 9 combinations (3 OS × 3 Python versions)
- **Jobs**:
  - `test`: Run all 70 unit tests on each platform
  - `lint`: Code formatting and linting checks
  - `type-check`: Static type checking
  - `coverage`: Test coverage reporting
  - `platform-specific`: Platform-specific validation
  - `build`: Package building

### 2. [pre-commit.yml](./workflows/pre-commit.yml) - Fast Checks
- **Runs on**: Pull Requests, Push to `main`/`develop`
- **Purpose**: Fast quality checks before full test suite
- **Checks**:
  - Format verification (blocking)
  - Linting (blocking)
  - Type checking (non-blocking)
  - Import validation (blocking)
  - Security scanning (non-blocking)

### 3. [publish.yml](./workflows/publish.yml) - PyPI Publishing
- **Runs on**: Release published, Manual trigger
- **Actions**:
  - Run full test suite
  - Build package
  - Publish to Test PyPI or PyPI
  - Upload release artifacts

### 4. [dependencies.yml](./workflows/dependencies.yml) - Dependency Updates
- **Runs on**: Weekly (Monday 9 AM UTC), Manual trigger
- **Actions**:
  - Update `uv.lock` with latest versions
  - Run tests with updated dependencies
  - Create PR if tests pass

### 5. [docs.yml](./workflows/docs.yml) - Documentation
- **Runs on**: Push to `main` with doc changes, Manual trigger
- **Actions**:
  - Validate README files
  - Check for missing docstrings
  - Generate API reference

## Local Validation

Before pushing, run:

```bash
./.github/validate-workflows.sh
```

This runs the same checks that GitHub Actions will run:
- ✅ YAML syntax validation
- ✅ Code formatting check
- ✅ Linting
- ✅ All 70 unit tests
- ✅ Package build
- ✅ Import validation

## Test Matrix

| OS | Python 3.10 | Python 3.11 | Python 3.12 |
|----|------------|------------|------------|
| **Ubuntu** | ✅ | ✅ | ✅ |
| **macOS** | ✅ | ✅ | ✅ |
| **Windows** | ✅ | ✅ | ✅ |

## Platform-Specific Tests

### macOS
- Detects platform as `"darwin"`
- Selects `LimaBackend`
- Checks Lima availability

### Linux
- Detects platform as `"linux"`
- Checks for `/dev/kvm` (not available in CI)
- Verifies `KVMNotAvailableError` is raised correctly

### Windows
- Detects platform as `"win32"`
- Selects `WSL2Backend`

## Required Secrets

Configure these in repository settings:

```
PYPI_API_TOKEN          # For publishing to PyPI
TEST_PYPI_API_TOKEN     # For test publishing (optional)
CODECOV_TOKEN           # For coverage reporting (optional)
```

## Workflow Duration

- **Pre-commit checks**: ~2-3 minutes
- **Single test job**: ~5-10 minutes
- **Full test matrix**: ~10-15 minutes (parallel)
- **Publish**: ~10 minutes

## Success Criteria

All workflows must pass before merging:

- ✅ All 70 tests pass on all platforms
- ✅ Code is properly formatted
- ✅ No linting errors
- ✅ Package builds successfully
- ✅ Platform detection works correctly

## Troubleshooting

### Tests fail on specific platform
1. Check platform-specific code in `src/pctx_sandbox/platform/`
2. Look at the workflow logs for that platform
3. Run tests locally on that platform

### Linting fails
```bash
# Auto-fix
uv run ruff check --fix .
uv run ruff format .
```

### Build fails
1. Verify `pyproject.toml` syntax
2. Check all dependencies are listed
3. Ensure package structure is correct

## Documentation

See [WORKFLOWS.md](./WORKFLOWS.md) for detailed documentation of each workflow.
