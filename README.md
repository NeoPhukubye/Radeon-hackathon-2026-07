# TraceBot: Autonomous DevOps & Test Generation Agent

## Overview
TraceBot is an autonomous DevOps agent — paste any public GitHub repository URL and it will:

1. **Scan** the repo for functions that lack test coverage
2. **Generate** the missing tests using Google Gemini AI
3. **Run** the generated tests and **self-correct** failing ones in a debug loop until they pass
4. **Produce** improved versions of source files with better error handling and structure

Supports **Python, JavaScript, TypeScript, Java, Go, Rust, C/C++, C#, Ruby, PHP, Kotlin, and Swift**.

## Live Demo
- **Frontend:** https://neophukubye.github.io/Radeon-hackathon-2026-07/
- **Backend API:** https://radeon-hackathon-2026-07.onrender.com/docs

## How It Works

```
GitHub URL  →  Clone Repo  →  Scan for untested functions
                                        ↓
                              Generate tests (Gemini AI)
                                        ↓
                              Run tests
                                        ↓
                          Pass? ──Yes──→ Report
                            ↓No
                          Fix with Gemini → Re-run (up to 3x)
                                        ↓
                              Generate improved source files
                                        ↓
                                    Report
```

## Architecture

```
GitHub Pages (Frontend)  →  Render.com (FastAPI Backend)  →  Google Gemini API
        ↑                           ↓
   Results displayed         Clone any GitHub repo
                             Scan all source files
                             Generate & run tests
                             Self-correct failures
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run` | Trigger a new analysis run |
| `GET` | `/run/{run_id}` | Get status of a run |
| `GET` | `/runs` | List all runs |
| `GET` | `/health` | Health check |

### POST /run — Request Body
```json
{
  "repo_url": "https://github.com/username/repository",
  "target_files": ["optional/specific/file.py"]
}
```

## Setup (Local Development)

### Prerequisites
- Python 3.10+
- A Google Gemini API key from [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

### Install
```bash
git clone https://github.com/NeoPhukubye/Radeon-hackathon-2026-07.git
cd Radeon-hackathon-2026-07
python3 -m venv venv
source venv/bin/activate
pip install -r tracebot/requirements.txt
pip install -r test-requirements.txt
```

### Configure
```bash
export GEMINI_API_KEY=your_api_key_here
export TRACEBOT_MODEL=gemini-3.6-flash
```

### Run
```bash
uvicorn tracebot.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/docs` for the interactive API.

### Test
```bash
python3 -m pytest tests/ -v
```

## Supported Languages

| Language | Test Framework Generated |
|----------|--------------------------|
| Python | unittest |
| JavaScript / JSX | Jest |
| TypeScript / TSX | Jest |
| Java | JUnit 5 |
| Go | testing (built-in) |
| Rust | built-in `#[test]` |
| C | Unity/assert |
| C++ | Google Test |
| C# | xUnit |
| Ruby | RSpec |
| PHP | PHPUnit |
| Kotlin | JUnit 5 |
| Swift | XCTest |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key (required) | — |
| `TRACEBOT_MODEL` | Gemini model name | `gemini-3.6-flash` |
| `TRACEBOT_MAX_DEBUG` | Max debug loop iterations | `3` |
| `TRACEBOT_REPO_PATH` | Default local repo path | `./watched_repo` |

---
*Developed by NeoDev for Radeon-hackathon-2026-07*

## Overview
TraceBot is an intelligent agent designed to streamline the software development lifecycle by automating code analysis, test generation, and bug fixing. It leverages a local Large Language Model (LLM) powered by Ollama, with acceleration on AMD Radeon GPUs via ROCm, to provide real-time feedback and improvements to your Python codebase.

This tool is particularly useful for hackathons focusing on AI agents and localized AI deployments, such as the Radeon-hackathon-2026-07.

## Features
- **Automated Code Analysis**: Scans Python files in a Git repository to identify functions lacking test coverage.
- **Intelligent Test Generation**: Generates `unittest` compatible test files for identified untested functions using an LLM.
- **Self-Correcting Debug Loop**: Automatically runs generated tests and, if they fail, uses the LLM to iteratively fix the test code until it passes or a maximum debug attempts limit is reached.
- **Automated Solution Generation**: For persistent failures or identified code smells, the LLM proposes and generates improved versions of the original source code, incorporating fixes, better error handling, and structural improvements.
- **AMD Radeon GPU Acceleration**: Optimized to leverage ROCm for accelerated local LLM inference, ensuring fast and efficient AI operations.
- **FastAPI Web Interface**: Provides a RESTful API for triggering and monitoring analysis runs.

## Architecture
TraceBot is built as a FastAPI application, interacting with local Git repositories and an Ollama server.

```
+----------------+       +-------------------+       +-------------------+
|                |       |                   |       |                   |
|  User (API)    |------>|  TraceBot FastAPI |------>|  Git Repository   |
|                |       |  (main.py)        |<------|  (code, tests)    |
+----------------+       |                   |       |                   |
                         +--------+----------+       +---------+---------+
                                  |                            ^
                                  |                            |
                                  |      Run Pipeline          |
                                  v                            |
                         +--------+----------+       +---------+---------+
                         |                   |       |                   |
                         |  Agent Coordinator|------>|  Local LLM (Ollama) |
                         |  (coordinator.py) |<------|  (on AMD GPU/ROCm)|
                         |                   |       |                   |
                         +-------------------+       +-------------------+
```

## Setup

### Prerequisites
- Python 3.9+
- Git
- Docker (optional, for running Ollama)
- An AMD Radeon GPU with ROCm drivers installed (optional, for GPU acceleration)
- Ollama server running locally (see [Ollama installation guide](https://ollama.com/download))

### 1. Clone the repository
```bash
git clone https://github.com/your-username/Radeon-hackathon-2026-07.git
cd Radeon-hackathon-2026-07
```

### 2. Set up a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r tracebot/requirements.txt
```

### 4. Install Ollama and pull a model
Follow the instructions on [ollama.com/download](https://ollama.com/download) to install Ollama.
Then, pull a compatible model. The default model used by TraceBot is `qwen2.5-coder:1.5b`.

```bash
ollama pull qwen2.5-coder:1.5b
```

Ensure your Ollama server is running. You can check its status using `ollama list`.

### 5. Configure TraceBot (Optional)
TraceBot uses environment variables for configuration. You can set these in your shell or create a `.env` file and use a tool like `python-dotenv`.

| Environment Variable          | Description                                                                 | Default Value                    |
| :---------------------------- | :-------------------------------------------------------------------------- | :------------------------------- |
| `TRACEBOT_REPO_PATH`          | Path to the Git repository to be monitored by TraceBot.                     | `./watched_repo`                 |
| `TRACEBOT_OLLAMA_URL`         | URL of the Ollama server.                                                   | `http://localhost:11434`         |
| `TRACEBOT_MODEL`              | Name of the Ollama model to use for AI operations.                          | `qwen2.5-coder:1.5b`             |
| `TRACEBOT_MAX_DEBUG`          | Maximum number of iterations the agent will attempt to fix failing tests.   | `3`                              |
| `TRACEBOT_TEST_DIR`           | Directory where generated tests will be stored.                             | `generated_tests`                |
| `TRACEBOT_SOLUTIONS_DIR`      | Directory where generated solutions (fixed code) will be stored.            | `generated_solutions`            |
| `TRACEBOT_ROCM_ENABLED`       | Enable/disable ROCm acceleration: `auto`, `true`, `false`.                  | `auto`                           |
| `TRACEBOT_GPU_LAYERS`         | Number of LLM layers to offload to GPU (-1 for all).                       | `-1`                             |

Example `.env` file:
```
TRACEBOT_REPO_PATH=/path/to/your/project
TRACEBOT_MODEL=llama3
TRACEBOT_ROCM_ENABLED=true
```

## How to Run

### Start the TraceBot FastAPI application
```bash
uvicorn tracebot.main:app --host 0.0.0.0 --port 8000 --reload
```
The `--reload` flag is useful for development. Remove it for production.

### Accessing the API documentation
Once running, open your browser to `http://localhost:8000/docs` to see the interactive API documentation (Swagger UI).

## API Endpoints

### `GET /`
Returns basic information about the TraceBot application and its status.

### `GET /health`
Returns the health status of the application, including the model in use, repository path, and GPU status.

### `POST /run`
Trigger a new TraceBot analysis, test generation, and solution generation run.
- **Request Body:**
    ```json
    {
        "repo_path": "string",  // Optional: path to the repository, overrides TRACEBOT_REPO_PATH
        "target_files": [       // Optional: list of specific files to analyze. If empty, auto-detects changed files.
            "string"
        ]
    }
    ```
- **Response:**
    ```json
    {
        "run_id": "string",
        "status": "string",    // e.g., "queued", "running", "completed", "failed"
        "current_step": "string",
        "summary": "string"    // Detailed report upon completion
    }
    ```
Example `curl` command:
```bash
curl -X POST "http://localhost:8000/run" -H "Content-Type: application/json" -d '{}'
```
To analyze specific files:
```bash
curl -X POST "http://localhost:8000/run" -H "Content-Type: application/json" -d '{"target_files": ["my_module/my_file.py"]}'
```

### `GET /run/{run_id}`
Get the status of a specific TraceBot run.
- **Path Parameter:** `run_id` (string, the ID returned by a `/run` request)

### `GET /runs`
List all active and completed TraceBot runs.

## Development and Contribution
(Add details on how to contribute, run tests for TraceBot itself, etc., here)

---
*Developed by NeoDev for Radeon-hackathon-2026-07*
