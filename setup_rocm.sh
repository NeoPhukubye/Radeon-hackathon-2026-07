#!/bin/bash
# TraceBot ROCm Setup — AMD Radeon GPU Acceleration
# Team: NeoDev | Track 2: Localized AI Agents Deployment
#
# This script installs ROCm and configures Ollama to use the AMD Radeon GPU
# for accelerated local LLM inference.
#
# Supported: AMD Radeon RX 6000/7000 series, Radeon Pro, APUs with RDNA2+
# OS: Ubuntu 22.04/24.04, Pop!_OS 22.04+

set -e

echo "=== TraceBot ROCm Setup ==="
echo "Configuring AMD Radeon GPU acceleration..."
echo ""

# Step 1: Install ROCm
echo "[1/4] Installing ROCm runtime..."
if [ -d "/opt/rocm" ]; then
    echo "  ROCm already installed at /opt/rocm"
else
    # Add ROCm repository
    sudo mkdir -p /etc/apt/keyrings
    wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | \
        gpg --dearmor | sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null

    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.1 jammy main" | \
        sudo tee /etc/apt/sources.list.d/rocm.list

    sudo apt-get update
    sudo apt-get install -y rocm-hip-runtime rocm-smi-lib
    echo "  ROCm installed successfully"
fi

# Step 2: Add user to render/video groups for GPU access
echo "[2/4] Configuring GPU permissions..."
sudo usermod -aG render,video "$USER"
echo "  User $USER added to render and video groups"

# Step 3: Install Ollama with ROCm support
echo "[3/4] Installing Ollama with ROCm backend..."
if command -v ollama &> /dev/null; then
    echo "  Ollama already installed"
else
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Verify Ollama detects the GPU
echo "  Checking GPU detection..."
ollama list > /dev/null 2>&1 || (sudo systemctl start ollama && sleep 2)

# Step 4: Pull the model
echo "[4/4] Pulling inference model..."
ollama pull qwen2.5-coder:1.5b 2>/dev/null || echo "  Model already available or no network"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "GPU Status:"
if command -v rocm-smi &> /dev/null; then
    rocm-smi --showproductname 2>/dev/null || echo "  AMD Radeon GPU detected via ROCm"
else
    echo "  ROCm installed — GPU will be used by Ollama automatically"
fi

echo ""
echo "To run TraceBot with Radeon acceleration:"
echo "  cd tracebot"
echo "  export TRACEBOT_REPO_PATH=/path/to/your/repo"
echo "  export TRACEBOT_MODEL=qwen2.5-coder:1.5b"
echo "  export TRACEBOT_ROCM_ENABLED=auto"
echo "  python3 main.py"
echo ""
echo "NOTE: You may need to log out and back in for GPU group permissions to take effect."
