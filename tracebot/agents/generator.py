from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config import settings
from models.schemas import AgentState
from tools.file_ops import write_file, read_file

GENERATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python test engineer. Generate comprehensive unittest tests.
Rules:
- Use Python's unittest framework
- Include edge cases and error conditions
- Use descriptive test method names
- Add setUp/tearDown if needed
- Import the module under test correctly
- Output ONLY valid Python code, no markdown fences"""),
    ("human", """Generate unit tests for the following Python source file.

File path: {file_path}
Untested functions: {untested_functions}

Source code:
```
{source_code}
```

Generate a complete test file using unittest."""),
])


def generate_node(state: AgentState) -> dict:
    """Generate unit tests for files with coverage gaps."""
    repo_path = Path(state["repo_path"])
    llm = ChatOllama(model=settings.model_name, base_url=settings.ollama_base_url, temperature=0.2)
    chain = GENERATE_PROMPT | llm
    generated_tests = []

    for file_analysis in state["analysis"]:
        if not file_analysis.untested_functions:
            continue

        source = read_file(repo_path / file_analysis.file_path)
        response = chain.invoke({
            "file_path": file_analysis.file_path,
            "untested_functions": ", ".join(file_analysis.untested_functions),
            "source_code": source,
        })

        test_filename = f"test_{Path(file_analysis.file_path).stem}.py"
        test_path = repo_path / settings.test_output_dir / test_filename
        write_file(test_path, response.content)
        generated_tests.append(str(test_path))

    return {"generated_tests": generated_tests, "current_step": "generation_complete"}
