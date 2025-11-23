#  Pytest Test Generator with RAG-Powered Feedback Loop

This project is a Streamlit web application that automates the generation of Pytest unit tests for Python code. It uses a multi-agent system built with LangGraph and powered by Groq AI models to create, execute, and automatically fix tests in a feedback loop. A Retrieval-Augmented Generation (RAG) component provides the system with a knowledge base of common error patterns, enabling it to make more intelligent fixes.

##  Features

- **Automated Test Generation**: Upload your Python functions and a README, and the system generates `pytest`-compatible tests.
- **Framework-Aware**: Automatically detects the web framework (`Flask`, `FastAPI`, `Django`, or `generic`) and generates tests using the correct patterns and fixtures.
- **RAG-Powered Feedback Loop**: If tests fail, the system analyzes the errors, consults a knowledge base of similar past problems, and attempts to fix the tests automatically.
- **Iterative Improvement**: The system iterates, refining the tests until they all pass or a maximum number of iterations is reached.
- **Interactive UI**: A Streamlit interface provides a user-friendly way to interact with the system, upload files, and view results.
- **Extensible Knowledge Base**: Easily add new error patterns and solutions by creating simple JSON files in the `examples/` directory.
- **Modular & Scalable**: The codebase is organized into a clean, modular structure, making it easy to understand, maintain, and extend.

##  How It Works

The application uses a graph-based agentic workflow built with LangGraph. Each node in the graph represents a specific agent or tool with a distinct responsibility.

1.  **Detector**: Extracts function names from the uploaded README and Python code. It also detects the framework being used.
2.  **Generator**: Takes the detected functions and generates initial unit tests. It uses framework-specific templates to ensure correctness (e.g., using the `client` fixture for Flask).
3.  **Combiner**: Creates a single, runnable Python script by combining the user's functions with the generated tests and any necessary boilerplate (like a Flask app fixture).
4.  **Executor**: Runs `pytest` on the combined script and captures the results, output, and any errors in a structured JSON format.
5.  **Critic**: Analyzes the test results.
    - If all tests pass, the process is complete.
    - If tests fail, the Critic consults the RAG knowledge base to find similar, previously solved errors. It then generates specific, actionable feedback for the Generator.
6.  **Feedback Loop**: The feedback is passed back to the Generator, which creates a new, improved set of tests. The cycle continues until the tests pass or a configurable number of iterations is met.
7.  **Reporter**: Once the loop finishes, this agent generates a final summary of the entire process, including metrics and the final generated test code.

## Project Structure

```
.
├── .env                  # For storing API keys
├── examples/             # Directory for RAG knowledge base JSON files
│   ├── ...
├── src/
│   ├── __init__.py
│   ├── app.py            # Main Streamlit UI and application entry point
│   ├── agent/            # LangGraph agent components
│   │   ├── __init__.py
│   │   ├── graph.py      # Main graph definition, state, and LLM setup
│   │   ├── nodes.py      # All agent node functions (detector, generator, etc.)
│   │   └── router.py     # Conditional routing logic for the graph
│   ├── core/             # Core helper functions
│   │   ├── __init__.py
│   │   ├── file_handler.py # For extracting functions from files
│   │   ├── framework_detector.py # For detecting the web framework
│   │   └── pytest_runner.py # Wrapper for running pytest
│   └── rag/              # RAG-specific components
│       ├── __init__.py
│       ├── knowledge_base.py # Loading examples and creating the vector store
│       └── retriever.py    # Function for retrieving hints from the knowledge base
├── README.md             # This file
└── requirements.txt      # Python package dependencies
```

##  Setup & Installation

Follow these steps to get the project running locally.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Create a Virtual Environment

It's recommended to use a virtual environment to manage dependencies.

```bash
# For Windows
python -m venv venv
venv\\Scripts\\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install all the required Python packages from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

The application uses Groq for its AI models. You'll need a Groq API key.

1.  Create a file named `.env` in the root of the project directory.
2.  Add your API key to the file:

    ```
    GROQ_API_KEY="your-groq-api-key-here"
    ```

##  Usage

1.  **Run the Streamlit App**:
    Make sure you are in the project's **root directory** (`CS787`), not the `src` directory. Run the following command:

    ```bash
    streamlit run src/app.py
    ```

2.  **Use the Application**:
    -   The application will open in your web browser.
    -   In the sidebar, you can configure the **Max Fix Iterations**.
    -   Upload your `README.md` file using the first uploader.
    -   Upload the Python file containing your functions using the second uploader.
    -   Click the **"🚀 Generate Tests & Run Feedback Loop"** button.
    -   Watch the progress as the system detects functions, generates tests, and runs the feedback loop.
    -   Once complete, the final results, test code, and execution history will be displayed.

##  Extending the Knowledge Base (RAG)

You can improve the agent's ability to fix tests by adding to its knowledge base.

1.  Navigate to the `examples/` directory.
2.  Create a new `.json` file (e.g., `my_new_error.json`).
3.  Use the following template to describe the error pattern and its solution. The more examples you provide, the smarter the Critic agent becomes.

### Example Template (`example_template.json`)

```json
{
  "error_pattern": "A short, descriptive title for the error (e.g., 'fixture not found')",
  "framework": "The framework this applies to: flask | fastapi | django | generic",
  "error_example": "The actual error message from pytest, which will be used for similarity search",
  "solution": "A clear, human-readable explanation of how to fix the error",
  "fix_pattern": "A concise pattern representing the fix (e.g., 'def test_name(client):')",
  "code_before": "A snippet of code that causes the error",
  "code_after": "The corrected code snippet"
}
```
