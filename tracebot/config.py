import os
from pathlib import Path

REPO_PATH = Path(os.environ.get("TRACEBOT_REPO_PATH", "./watched_repo"))
OLLAMA_BASE_URL = os.environ.get("TRACEBOT_OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("TRACEBOT_MODEL", "qwen2.5-coder:1.5b")
MAX_DEBUG_ITERATIONS = int(os.environ.get("TRACEBOT_MAX_DEBUG", "3"))
TEST_OUTPUT_DIR = os.environ.get("TRACEBOT_TEST_DIR", "generated_tests")
SOLUTIONS_OUTPUT_DIR = os.environ.get("TRACEBOT_SOLUTIONS_DIR", "generated_solutions")

# ROCm GPU acceleration config
ROCM_ENABLED = os.environ.get("TRACEBOT_ROCM_ENABLED", "auto")  # auto, true, false
GPU_LAYERS = int(os.environ.get("TRACEBOT_GPU_LAYERS", "-1"))  # -1 = offload all layers to GPU


def detect_rocm() -> bool:
    """Detect if ROCm is available for Radeon GPU acceleration."""
    rocm_path = Path("/opt/rocm")
    if rocm_path.exists():
        return True
    hip_visible = os.environ.get("HIP_VISIBLE_DEVICES")
    if hip_visible is not None:
        return True
    try:
        import subprocess
        result = subprocess.run(["rocminfo"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_gpu_status() -> dict:
    """Return GPU acceleration status."""
    if ROCM_ENABLED == "false":
        return {"accelerated": False, "backend": "cpu", "reason": "disabled by config"}

    rocm_available = detect_rocm()
    if rocm_available:
        return {"accelerated": True, "backend": "rocm", "device": "AMD Radeon GPU"}

    if ROCM_ENABLED == "true":
        return {"accelerated": False, "backend": "cpu", "reason": "ROCm not found but requested"}

    return {"accelerated": False, "backend": "cpu", "reason": "ROCm not installed"}

# System Prompts
SYSTEM_PROMPT_GENERATE = (
    "You are an expert Python test engineer. You write thorough, correct "
    "unittest test files. Output ONLY valid Python code — no markdown fences, "
    "no explanations, no comments outside the code."
)

SYSTEM_PROMPT_FIX = (
    "You are a Python debugging expert. You fix failing test files so they pass. "
    "Output ONLY the corrected Python file — no markdown fences, no explanations."
)

SYSTEM_PROMPT_SOLUTION = (
    "You are a senior Python engineer. You analyze failing code and produce "
    "a corrected, production-ready version. You also suggest improvements for "
    "reliability, performance, and readability. Output ONLY valid Python code."
)

