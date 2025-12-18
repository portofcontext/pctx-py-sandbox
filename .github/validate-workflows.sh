#!/bin/bash
# Script to validate GitHub Actions workflows locally

set -e

echo "=== Validating GitHub Actions Workflows ==="
echo ""

# Check if we're in the right directory
if [ ! -d ".github/workflows" ]; then
    echo "❌ Error: .github/workflows directory not found"
    echo "Please run this script from the repository root"
    exit 1
fi

echo "✅ Found .github/workflows directory"
echo ""

# List all workflow files
echo "📋 Workflow files:"
ls -1 .github/workflows/*.yml
echo ""

# Validate YAML syntax (requires yq or python)
echo "🔍 Validating YAML syntax..."
for workflow in .github/workflows/*.yml; do
    echo "  Checking: $workflow"

    # Try with Python (most portable)
    if command -v python3 &> /dev/null; then
        python3 -c "import yaml; yaml.safe_load(open('$workflow'))" 2>&1 && \
            echo "    ✅ Valid YAML" || \
            echo "    ❌ Invalid YAML"
    elif command -v yq &> /dev/null; then
        yq eval '.' "$workflow" > /dev/null 2>&1 && \
            echo "    ✅ Valid YAML" || \
            echo "    ❌ Invalid YAML"
    else
        echo "    ⚠️  Cannot validate (install python3 or yq)"
    fi
done
echo ""

# Run the same checks that CI will run
echo "🧪 Running local CI checks..."
echo ""

# 1. Format check
echo "1️⃣  Checking code formatting..."
if uv run ruff format --check . > /dev/null 2>&1; then
    echo "   ✅ Code is properly formatted"
else
    echo "   ❌ Code formatting issues found"
    echo "   Run: uv run ruff format ."
    exit 1
fi
echo ""

# 2. Lint check
echo "2️⃣  Checking linting..."
if uv run ruff check . > /dev/null 2>&1; then
    echo "   ✅ No linting issues"
else
    echo "   ❌ Linting issues found"
    echo "   Run: uv run ruff check --fix ."
    exit 1
fi
echo ""

# 3. Run tests
echo "3️⃣  Running tests..."
if uv run pytest tests/unit/ -v --tb=short > /tmp/test-output.txt 2>&1; then
    TEST_COUNT=$(grep -o "[0-9]* passed" /tmp/test-output.txt | awk '{print $1}')
    echo "   ✅ All $TEST_COUNT tests passed"
else
    echo "   ❌ Tests failed"
    cat /tmp/test-output.txt
    exit 1
fi
echo ""

# 4. Build check
echo "4️⃣  Checking package build..."
if uv build > /dev/null 2>&1; then
    echo "   ✅ Package builds successfully"
    ls -lh dist/ | tail -n +2
else
    echo "   ❌ Build failed"
    exit 1
fi
echo ""

# 5. Import check
echo "5️⃣  Checking imports..."
if uv run python -c "from pctx_sandbox import sandbox, sandbox_async; print('✅ Imports work')" 2>&1; then
    :
else
    echo "   ❌ Import failed"
    exit 1
fi
echo ""

# Summary
echo "================================"
echo "✅ All local CI checks passed!"
echo "================================"
echo ""
echo "Your code is ready to push. The GitHub Actions workflows will:"
echo "  • Run tests on Ubuntu, macOS, and Windows"
echo "  • Test with Python 3.10, 3.11, and 3.12"
echo "  • Check formatting and linting"
echo "  • Build the package"
echo "  • Run platform-specific tests"
echo ""
echo "To push and trigger CI:"
echo "  git add ."
echo "  git commit -m 'your message'"
echo "  git push"
