#!/bin/bash
set -euo pipefail

# Install nsjail on Linux (Ubuntu/Debian)
# This script is used by GitHub Actions and can be used by users as well

echo "Installing nsjail build dependencies..."
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  autoconf \
  bison \
  flex \
  gcc \
  g++ \
  protobuf-compiler \
  libprotobuf-dev \
  libnl-route-3-dev \
  libtool \
  pkg-config

echo "Building nsjail from source..."
NSJAIL_DIR=$(mktemp -d)
git clone https://github.com/google/nsjail.git "$NSJAIL_DIR"
cd "$NSJAIL_DIR"
make
sudo cp nsjail /usr/local/bin/
cd /
rm -rf "$NSJAIL_DIR"

echo "Verifying nsjail installation..."
nsjail --help > /dev/null 2>&1 || {
    echo "Error: nsjail installation failed"
    exit 1
}

echo "nsjail installed successfully!"
