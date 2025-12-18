#!/bin/bash
# Start the pctx-sandbox agent in Lima VM

set -e

echo "Starting pctx-sandbox Lima VM..."
limactl start pctx-sandbox 2>/dev/null || {
    echo "VM doesn't exist, creating..."
    limactl create --name pctx-sandbox src/pctx_sandbox/platform/lima-config.yaml
    limactl start pctx-sandbox
}

echo "Waiting for VM to be ready..."
sleep 5

echo "Installing pctx-sandbox in VM..."
limactl shell pctx-sandbox bash -c "
    export PATH=\"\$HOME/.cargo/bin:\$PATH\"
    cd /tmp/lima/\$(whoami)/repos/portofcontext/python-sandbox || exit 1
    uv pip install -e '.[agent]'
"

echo "Starting sandbox agent..."
limactl shell pctx-sandbox bash -c "
    export PATH=\"\$HOME/.cargo/bin:\$PATH\"
    cd /tmp/lima/\$(whoami)/repos/portofcontext/python-sandbox
    nohup uv run python -m pctx_sandbox.agent.sandbox_agent > /tmp/agent.log 2>&1 &
    echo \$! > /tmp/agent.pid
"

echo "Agent started. Waiting for it to be ready..."
sleep 3

echo "Checking agent health..."
curl -f http://localhost:9000/health || {
    echo "Agent not responding, check logs with:"
    echo "  limactl shell pctx-sandbox cat /tmp/agent.log"
    exit 1
}

echo "Agent is running and healthy!"
