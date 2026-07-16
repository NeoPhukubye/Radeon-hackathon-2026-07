#!/bin/bash
# TraceBot ROCm Setup — AMD Radeon GPU Acceleration
# Team: NeoDev | Track 2: Localized AI Agents Deployment
set -e

echo "=== TraceBot ROCm Setup ==="
echo "Configuring AMD Radeon GPU acceleration..."
echo ""

# Step 1: Pin ROCm repo packages to take priority
echo "[1/5] Configuring ROCm package priority..."
sudo mkdir -p /etc/apt/keyrings
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | \
    gpg --dearmor | sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.1 jammy main" | \
    sudo tee /etc/apt/sources.list.d/rocm.list

# Pin ROCm repo higher so its rocminfo wins over universe
cat <<PINEOF | sudo tee /etc/apt/preferences.d/rocm-pin-600
Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600
PINEOF

sudo apt-get update 2>/dev/null

# Step 2: Force install rocminfo from ROCm repo
echo "[2/5] Installing ROCm runtime..."
sudo apt-get install -y --allow-downgrades rocminfo=1.0.0.60100-82~22.04 2>/dev/null || \
    sudo apt-get install -y rocminfo 2>/dev/null || true
sudo apt-get install -y --fix-broken rocm-hip-runtime rocm-smi-lib 2>/dev/null || \
    echo "  Falling back to minimal ROCm install..."

# If full install failed, try just the essentials
if [ ! -d "/opt/rocm" ]; then
    sudo apt-get install -y rocm-hip-runtime 2>/dev/null || \
    sudo apt-get install -y hip-runtime-amd 2>/dev/null || \
    echo "  Could not install full ROCm — using Ollama GPU detection instead"
fi

# Step 3: Add user to render/video groups
echo "[3/5] Configuring GPU permissions..."
sudo usermod -aG render,video "$USER"
echo "  User $USER added to render and video groups"

# Step 4: Ensure Ollama uses GPU
echo "[4/5] Configuring Ollama for Radeon GPU..."
# Ollama auto-detects ROCm GPUs. Set env to force GPU usage.
sudo mkdir -p /etc/systemd/system/ollama.service.d
cat <<SVCEOF | sudo tee /etc/systemd/system/ollama.service.d/gpu.conf
[Service]
Environment="HSA_OVERRIDE_GFX_VERSION=10.3.0"
Environment="HIP_VISIBLE_DEVICES=0"
SVCEOF
sudo systemctl daemon-reload
sudo systemctl restart ollama 2>/dev/null || true
echo "  Ollama configured for AMD GPU"

# Step 5: Verify
echo "[5/5] Verifying GPU setup..."
if [ -d "/opt/rocm" ]; then
    echo "  ROCm installed at /opt/rocm"
    /opt/rocm/bin/rocminfo 2>/dev/null | grep -i "marketing" | head -3 || true
fi

# Check if Ollama sees the GPU
sleep 2
ollama ps 2>/dev/null || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Even without full ROCm packages, Ollama can use the Radeon GPU"
echo "if HSA_OVERRIDE_GFX_VERSION is set correctly for your APU."
echo ""
echo "To run TraceBot:"
echo "  cd tracebot"
echo "  export TRACEBOT_REPO_PATH=/path/to/your/repo"
echo "  export TRACEBOT_MODEL=qwen2.5-coder:1.5b"
echo "  export HSA_OVERRIDE_GFX_VERSION=10.3.0"
echo "  python3 main.py"
