# GitHub Actions Workflows

This project uses GitHub Actions for continuous integration and deployment across all platforms.

## Workflows Overview

### 1. Tests (`test.yml`)

**Trigger**: Push to `main`/`develop`, Pull Requests

**Jobs**:

- **test**: Run tests on all platforms and Python versions
  - **Matrix**:
    - OS: Ubuntu, macOS, Windows
    - Python: 3.10, 3.11, 3.12
  - **Steps**:
    - Install dependencies with `uv`
    - Run pytest with all 70 unit tests
    - Verify package can be imported
  - **Duration**: ~5-10 minutes per matrix job

- **lint**: Code quality checks
  - Format checking with `ruff format --check`
  - Linting with `ruff check`
  - **Fails if**: Code is not formatted or has lint errors

- **type-check**: Static type checking
  - Type checking with `mypy`
  - **Non-blocking**: Currently set to `continue-on-error`

- **coverage**: Test coverage reporting
  - Run tests with coverage tracking
  - Upload to Codecov
  - Generate coverage reports

- **platform-specific**: Platform-specific tests
  - **macOS**: Test Lima backend availability
  - **Linux**: Test KVM detection (expects no KVM in GitHub Actions)
  - **Windows**: Test WSL2 backend stub
  - Verify platform detection works correctly

- **build**: Package building
  - Build wheel and source distribution
  - Upload artifacts for 7 days
  - Verify both `.whl` and `.tar.gz` are created

**Success Criteria**:
- ✅ All 70 tests pass on all platforms
- ✅ Code passes format and lint checks
- ✅ Package builds successfully

### 2. Pre-commit Checks (`pre-commit.yml`)

**Trigger**: Pull Requests, Push to `main`/`develop`

**Jobs**:

- **pre-commit**: Fast quality checks
  - Format verification (must pass)
  - Linting (must pass)
  - Type checking (non-blocking)
  - Import validation (must pass)
  - Security scanning with `bandit` (non-blocking)
  - TODO/FIXME detection (informational)

**Purpose**: Catch issues early before full test suite runs

**Duration**: ~2-3 minutes

### 3. Publish to PyPI (`publish.yml`)

**Trigger**:
- Release published
- Manual workflow dispatch

**Jobs**:

- **build-and-publish**:
  - Run full test suite
  - Build package
  - Publish to Test PyPI (if manual trigger)
  - Publish to PyPI (if release)
  - Upload artifacts to GitHub release

**Requirements**:
- `PYPI_API_TOKEN` secret configured
- `TEST_PYPI_API_TOKEN` for test publishes

**Usage**:
```bash
# Create a release
git tag v0.1.0
git push origin v0.1.0

# Or manually trigger from GitHub UI
# Actions -> Publish to PyPI -> Run workflow
```

### 4. Dependency Updates (`dependencies.yml`)

**Trigger**:
- Weekly (Monday 9 AM UTC)
- Manual workflow dispatch

**Jobs**:

- **update-dependencies**:
  - Update `uv.lock` with latest versions
  - Run full test suite with updated dependencies
  - Create PR if tests pass

**Purpose**: Keep dependencies up-to-date automatically

**Review**: PRs are automatically created but require manual review

### 5. Documentation (`docs.yml`)

**Trigger**:
- Push to `main` with doc changes
- Manual workflow dispatch

**Jobs**:

- **build-docs**:
  - Validate README, DEVELOPMENT.md, QUICKSTART.md
  - Check for missing docstrings
  - Generate API reference with `pdoc`
  - Upload documentation artifacts

**Duration**: ~1-2 minutes

## Platform Testing Strategy

### macOS (macos-latest)
- ✅ Tests platform detection returns `"darwin"`
- ✅ Tests `LimaBackend` is selected
- ✅ Tests Lima availability detection
- ⚠️  Cannot test actual Lima VM (not installed in CI)

### Linux (ubuntu-latest)
- ✅ Tests platform detection returns `"linux"`
- ✅ Tests KVM detection (expects `/dev/kvm` to NOT exist in CI)
- ✅ Tests `KVMNotAvailableError` is raised correctly
- ⚠️  Cannot test actual Firecracker (requires KVM)

### Windows (windows-latest)
- ✅ Tests platform detection returns `"win32"`
- ✅ Tests `WSL2Backend` is selected
- ⚠️  Cannot test actual WSL2 integration

## Test Matrix

```
Python 3.10 x Ubuntu   ✅
Python 3.10 x macOS    ✅
Python 3.10 x Windows  ✅
Python 3.11 x Ubuntu   ✅
Python 3.11 x macOS    ✅
Python 3.11 x Windows  ✅
Python 3.12 x Ubuntu   ✅
Python 3.12 x macOS    ✅
Python 3.12 x Windows  ✅
```

**Total**: 9 matrix combinations (27 jobs including lint, type-check, coverage)

## Secrets Configuration

Required secrets in repository settings:

```
PYPI_API_TOKEN           - PyPI publishing token
TEST_PYPI_API_TOKEN      - Test PyPI token (optional)
CODECOV_TOKEN           - Codecov.io token (optional)
```

## Badge Status

Add these badges to README.md:

```markdown
![Tests](https://github.com/portofcontext/pctx-sandbox/workflows/Tests/badge.svg)
![Pre-commit](https://github.com/portofcontext/pctx-sandbox/workflows/Pre-commit%20Checks/badge.svg)
[![codecov](https://codecov.io/gh/portofcontext/pctx-sandbox/branch/main/graph/badge.svg)](https://codecov.io/gh/portofcontext/pctx-sandbox)
[![PyPI version](https://badge.fury.io/py/pctx-sandbox.svg)](https://badge.fury.io/py/pctx-sandbox)
```

## Workflow Optimization

### Caching Strategy
- ✅ UV cache enabled in all workflows
- ✅ Python installations cached by `astral-sh/setup-uv`
- ✅ Dependencies cached between runs

### Parallel Execution
- ✅ Test matrix runs in parallel (9 jobs)
- ✅ Lint, type-check, coverage run in parallel
- ⚡ Total CI time: ~10-15 minutes for full suite

### Fail-Fast
- ❌ `fail-fast: false` in test matrix
  - Tests all platforms even if one fails
  - Provides complete failure information

## Local Testing

Run the same checks locally before pushing:

```bash
# Run all tests (like CI)
uv run pytest tests/unit/ -v

# Check formatting
uv run ruff format --check .

# Check linting
uv run ruff check .

# Type check
uv run mypy src/pctx_sandbox --ignore-missing-imports

# Build package
uv build

# Test import
uv run python -c "from pctx_sandbox import sandbox"
```

## Troubleshooting

### Tests fail on specific platform
1. Check platform-specific code in `src/pctx_sandbox/platform/`
2. Verify platform detection logic
3. Check for OS-specific path issues

### Build fails
1. Verify `pyproject.toml` is valid
2. Check all dependencies are specified
3. Ensure `src/` layout is correct

### Publishing fails
1. Verify PyPI token is configured
2. Check version number is incremented
3. Ensure package name is available on PyPI

### Coverage upload fails
1. Check Codecov token is configured
2. Verify coverage.xml is generated
3. Set `continue-on-error: true` if optional

## Future Enhancements

- [ ] Add integration tests when agent is implemented
- [ ] Add performance benchmarks
- [ ] Add security scanning (SAST)
- [ ] Add dependency vulnerability scanning
- [ ] Set up GitHub Pages for documentation
- [ ] Add release automation (changelog generation)
- [ ] Add Docker image building for agent
