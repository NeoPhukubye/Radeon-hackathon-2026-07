from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    repo_path: Path = Path("./watched_repo")
    ollama_base_url: str = "http://localhost:11434"
    model_name: str = "llama3"
    max_debug_iterations: int = 3
    poll_interval_seconds: int = 10
    test_output_dir: str = "generated_tests"
    log_level: str = "INFO"

    class Config:
        env_prefix = "TRACEBOT_"


settings = Settings()
