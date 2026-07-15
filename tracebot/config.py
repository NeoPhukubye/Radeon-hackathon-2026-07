import os
from pathlib import Path

REPO_PATH = Path(os.environ.get("TRACEBOT_REPO_PATH", "./watched_repo"))
OLLAMA_BASE_URL = os.environ.get("TRACEBOT_OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("TRACEBOT_MODEL", "llama3")
MAX_DEBUG_ITERATIONS = int(os.environ.get("TRACEBOT_MAX_DEBUG", "3"))
POLL_INTERVAL = int(os.environ.get("TRACEBOT_POLL_INTERVAL", "10"))
TEST_OUTPUT_DIR = os.environ.get("TRACEBOT_TEST_DIR", "generated_tests")
