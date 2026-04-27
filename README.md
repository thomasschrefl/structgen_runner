# StructGen Runner v2 (UML → Python with Verification)

StructGen Runner v2 is an automated **structured code generation** framework. It uses Large Language Models (LLMs) to transform natural language requirements into verified, production-ready scientific Python modules through a formal design-first approach.

The core philosophy of StructGen is that **design precedes code**. By forcing the LLM to create and validate PlantUML diagrams before writing a single line of Python, the runner ensures the model has a consistent mental model of the task's logic and data structures.

---

## Execution Modes

The runner supports two primary ways to interact with LLMs, organized into dedicated directories:

### 1. API Mode (`run_dir_api`)
Uses an OpenAI-compatible web API (local or cloud).
- **Best for**: `llama-server`, `vLLM`, `Ollama`, or OpenAI/Anthropic proxies.
- **Run**:
  ```bash
  cd run_dir_api
  micromamba run -n structgen-v2 python structgen_run_v2.py
  ```

### 2. CLI Mode (`run_dir_cli`)
Invokes a local command-line tool.
- **Best for**: Tools like `gemini-cli`, `claude-code`, or custom shell scripts.
- **Run**:
  ```bash
  cd run_dir_cli
  micromamba run -n structgen-v2 python structgen_run_v2.py
  ```

---

## Configuration (`structgen_config.json`)

The runner behavior is controlled by a JSON configuration file.

### Interface Selection
| Parameter | Description |
| :--- | :--- |
| **`llm_provider`** | Choose between `"openai"` (API-based) or `"cli"` (Command-line based). |
| **`cli_command_template`** | *(CLI only)* The shell command to run. Supports `{system}`, `{user}`, and `{model}` placeholders. |
| **`base_url`** | *(API only)* The endpoint URL (e.g., `http://localhost:8080/v1`). |
| **`api_key`** | *(API only)* Your API key (use `sk-no-key-required` for local servers). |

### LLM Sampling & Control
| Parameter | API Mode (`openai`) | CLI Mode (`cli`) |
| :--- | :--- | :--- |
| **`model`** | Sent to the API. | Injected into `{model}` placeholder. |
| **`temperature`** | Controls creativity. | **Ignored** (set via CLI tool flags). |
| **`top_p`** | Controls diversity. | **Ignored**. |
| **`max_tokens`** | Caps response length. | **Ignored**. |

### Pipeline & Retry Limits (Both Modes)
| Parameter | Description |
| :--- | :--- |
| **`max_code_repairs`** | Number of attempts to fix Python code after verification failure. |
| **`max_design_revisions`** | Number of times to rethink the UML design if code repair fails. |
| **`max_uml_repairs`** | Number of attempts to fix PlantUML syntax errors. |
| **`plantuml_jar_path`** | Path to the `plantuml.jar` executable. |

### Advanced Settings (Both Modes)
*   **`prompt_token_budget`**: Threshold for automatic prompt compression to save context.
*   **`log_prompts`**: If `true`, saves all prompts to `out/<task>/prompts_used/` for debugging.
*   **`fail_on_error_output`**: Fails verification if the code prints `"Error:"` to stderr/stdout.

---

## Using Local LLMs with Ollama

You can use API mode with [Ollama](https://ollama.com/) by utilizing its OpenAI-compatible endpoint.

1.  **Configure Ollama**: Ensure Ollama is running (`ollama serve`).
2.  **Update `structgen_config.json`**:
    ```json
    {
      "llm_provider": "openai",
      "base_url": "http://localhost:11434/v1",
      "api_key": "ollama",
      "model": "qwen2.5-coder:32b"
    }
    ```

---

## The Generation Sequence

1.  **Task Initialization**: Parses tasks from `requirements.txt`.
2.  **Design Phase**: Designer LLM generates Activity and Class UML diagrams.
3.  **UML Validation**: Runner checks UML syntax and auto-repairs if necessary.
4.  **Implementation**: Coder LLM implements the design as a Python module with a `run()` entry point.
5.  **Verification**: Runner executes the code against directives like `@check` and `@params`.
6.  **Success**: Generates a `test_run/` folder with outputs and a reproduction script.

---

## Prerequisites

- **Python 3.10+** (Numpy & Pandas required)
- **Java (OpenJDK)** (for PlantUML)
- **Micromamba** (recommended environment manager)
