import json
import re
from langchain_core.messages import HumanMessage

# Import graph state and LLMs using absolute imports
from agent.state import AgentState
from agent.llms import llm_generator, llm_critic, llm_reporter

# Import core logic using absolute imports
from core.file_handler import (
    extract_functions_from_readme,
    extract_functions_from_python_file,
    extract_code,
    extract_user_functions,
)
from core.framework_detector import detect_framework
from core.pytest_runner import run_pytest_json

# Import RAG logic using absolute imports
from rag.retriever import get_troubleshooting_hints

# --------------------- Agent Nodes -------------------

def function_detector_node(state: AgentState) -> AgentState:
    """Detect functions from README and Python file."""
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "detector",
        "action": "Detecting functions..."
    })
    functions_from_readme = extract_functions_from_readme(state["readme_content"])
    functions_from_code = extract_functions_from_python_file(state["user_functions"])
    framework = detect_framework(state["user_functions"])
    state["framework"] = framework

    if functions_from_readme:
        functions = functions_from_readme
    elif functions_from_code:
        functions = functions_from_code
        state["history"].append({
            "iteration": state["iteration"],
            "agent": "detector",
            "action": f"⚠️ No functions in README, extracted {len(functions)} from Python code"
        })
    else:
        functions = []
        state["history"].append({
            "iteration": state["iteration"],
            "agent": "detector",
            "action": "❌ No functions detected in README or code"
        })
    
    state["detected_functions"] = functions
    state["num_functions"] = len(functions)
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "detector",
        "action": f"Detected {len(functions)} functions ({framework} framework): {', '.join(functions)}"
    })
    return state

def test_generator_node(state: AgentState) -> AgentState:
    """Generator Agent - Creates test code based on README and user functions."""
    feedback_text = state.get("feedback", "Generate comprehensive unit tests based on the README and provided functions.")
    previous_test_preview = f"\n\nPREVIOUS TEST CODE (first 800 chars):\n{state['test_code'][:800]}" if state.get("test_code") else ""
    
    framework = state.get("framework", "generic")
    function_list = ", ".join(state["detected_functions"])
    readme_preview = state['readme_content'][:2500]
    user_functions_preview = state['user_functions'][:2500]

    framework_instructions = ""
    if framework == 'flask':
        framework_instructions = """
FLASK-SPECIFIC REQUIREMENTS:
- Use the `client` fixture for all route tests.
- Test routes using: `response = client.get('/route')`.
- Access response data with: `response.get_json()` or `response.data`.
- Check status codes with: `response.status_code`.
- DO NOT call route handlers directly.
"""
    elif framework == 'fastapi':
        framework_instructions = """
FASTAPI-SPECIFIC REQUIREMENTS:
- Use `TestClient` from `fastapi.testclient`.
- Test endpoints using: `response = client.get('/route')`.
- Check `response.status_code` and `response.json()`.
"""

    prompt = f"""
You are an expert Python test generator.

DETECTED FUNCTIONS ({state['num_functions']}): {function_list}
FRAMEWORK DETECTED: {framework.upper()}
{framework_instructions}

CRITICAL REQUIREMENTS:
1. Generate EXACTLY ONE test function per detected function.
2. Naming convention: `test_originalfunctionname`.
3. Each test must be independent and self-contained.

FEEDBACK FROM PREVIOUS ITERATION: {feedback_text}

README (preview):
{readme_preview}

USER'S FUNCTIONS (preview):
{user_functions_preview}
{previous_test_preview}

Return ONLY Python code wrapped in `<PYTEST_FILE>` tags.
"""
    
    messages = [HumanMessage(content=prompt)]
    response = llm_generator.invoke(messages)
    test_code = extract_code(response.content)
    
    state["test_code"] = test_code
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "generator",
        "action": f"Generated {state['num_functions']} test functions for {framework}"
    })
    return state

def combiner_node(state: AgentState) -> AgentState:
    """Combine user functions with generated tests."""
    framework = state.get("framework", "generic")
    filtered_functions = extract_user_functions(state['user_functions'], state['detected_functions'])
    
    if framework == 'flask':
        filtered_functions = re.sub(r'^(import|from)\s+.*$', '', filtered_functions, flags=re.MULTILINE)
        combined = f"""
import pytest
from flask import Flask, request

app = Flask(__name__)
{filtered_functions}

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# ==================== TESTS ====================
{state['test_code']}
"""
    else:
        filtered_functions = re.sub(r'^(import|from)\s+.*$', '', filtered_functions, flags=re.MULTILINE)
        test_code_cleaned = re.sub(r'^(from|import)\s+[\w.]+\s+.*$', '', state['test_code'], flags=re.MULTILINE)
        combined = f"""
# User's function implementations
{filtered_functions}

# ==================== TESTS ====================
{test_code_cleaned}
"""
    
    state["combined_code"] = combined
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "combiner",
        "action": f"Combined functions for {framework} framework."
    })
    return state

def execution_node(state: AgentState) -> AgentState:
    """Execution Engine - Runs pytest on combined code."""
    with open("test_combined.py", "w", encoding="utf-8") as f:
        f.write(state["combined_code"])
    
    return_code, report, stdout, stderr = run_pytest_json("test_combined.py", 90)
    
    state["return_code"] = return_code
    state["report"] = report or {}
    state["pytest_output"] = stdout
    state["pytest_stderr"] = stderr
    
    summary = report.get("summary", {}) if report else {}
    state["iteration_results"].append({
        "iteration": state["iteration"],
        "collected": summary.get("collected", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "errors": summary.get("errors", 0)
    })
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "executor",
        "action": f"Executed tests - Return code: {return_code}"
    })
    return state

def critic_node(state: AgentState, vectorstore) -> AgentState:
    """Critic Agent - Analyzes results and decides next step."""
    summary = state["report"].get("summary", {})
    passed = summary.get("passed", 0)
    collected = summary.get("collected", 0)

    if collected > 0 and passed == collected and not summary.get("failed") and not summary.get("errors"):
        state["status"] = "success"
        state["feedback"] = "All tests passed successfully."
        state["history"].append({"iteration": state["iteration"], "agent": "critic", "action": f"✅ SUCCESS - {passed}/{collected} tests passed"})
        return state

    failed_tests = [t for t in state["report"].get("tests", []) if t.get("outcome") in ["failed", "error"]]
    rag_hints = get_troubleshooting_hints(failed_tests, state.get("framework"), vectorstore)

    prompt_template = """
Analyze pytest results and provide SPECIFIC, ACTIONABLE feedback.

FRAMEWORK: {framework}
RESULTS:
- Collected: {collected} (Expected: {num_functions})
- Passed: {passed}
- Failed: {failed}
- Errors: {errors}
- Iteration: {iteration} of {max_iterations}

FAILED TESTS (detailed):
{failed_tests_json}

PYTEST OUTPUT:
{pytest_output}

STDERR:
{pytest_stderr}
{rag_hints}

YOUR TASK: Analyze failures and provide SPECIFIC fixes. Use the similar patterns from the knowledge base to guide your diagnosis. Return ONLY valid JSON.

RESPONSE FORMAT (JSON only):
- If tests failed: {{"status": "needs_fix", "feedback": "SPECIFIC ACTIONABLE FIXES: 1) In test_get_item, use client.get('/items/0'). 2) In test_add_item, use client.post('/items', json={{...}})."}}
- If wrong number of tests collected: {{"status": "needs_fix", "feedback": "Expected {num_functions} tests but collected {collected}. Regenerate with correct count."}}
- If max iterations reached: {{"status": "max_iterations", "message": "Maximum iterations reached."}}
"""
    prompt = prompt_template.format(
        framework=state.get('framework', 'generic').upper(),
        collected=collected,
        num_functions=state['num_functions'],
        passed=passed,
        failed=summary.get("failed", 0),
        errors=summary.get("errors", 0),
        iteration=state['iteration'],
        max_iterations=state['max_iterations'],
        failed_tests_json=json.dumps(failed_tests[:3], indent=2),
        pytest_output=state["pytest_output"][-1200:],
        pytest_stderr=state["pytest_stderr"][-800:],
        rag_hints=rag_hints
    )
    
    response = llm_critic.invoke([HumanMessage(content=prompt)])
    
    try:
        result = json.loads(re.search(r'\{.*\}', response.content, re.DOTALL).group())
    except Exception:
        result = {"status": "needs_fix", "feedback": "Error parsing critic response."}
    
    state["status"] = result.get("status", "unknown")
    state["feedback"] = result.get("feedback", result.get("message", ""))
    
    rag_used = " (RAG-assisted)" if rag_hints else ""
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "critic",
        "action": f"Analysis: {state['status']} - {passed}/{collected} passed{rag_used}"
    })

    if state["status"] == "needs_fix":
        state["iteration"] += 1
    return state

def reporter_node(state: AgentState) -> AgentState:
    """Reporting Agent - Formats final output."""
    summary = state.get("report", {}).get("summary", {})
    passed = summary.get("passed", 0)
    collected = summary.get("collected", 0)

    prompt = f"""
Generate a concise final report.

STATUS: {state['status']}
ITERATIONS: {state['iteration']}
FRAMEWORK: {state.get('framework', 'generic').upper()}
FUNCTIONS: {state['num_functions']}
RESULTS: {passed}/{collected} passed

Detected functions: {', '.join(state['detected_functions'][:10])}

{"✅ SUCCESS - All tests passed!" if state['status'] == 'success' else ""}
{"⚠️ INCOMPLETE - Still have failing tests after max iterations." if state['status'] == 'max_iterations' else ""}
{"⚠️ STALLED - No improvement in recent iterations." if state['status'] == 'stalled' else ""}

Provide a brief, clear summary of the results. NO <think> tags.
"""
    
    response = llm_reporter.invoke([HumanMessage(content=prompt)])
    clean_response = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL | re.IGNORECASE).strip()
    
    state["final_message"] = clean_response
    state["history"].append({
        "iteration": state["iteration"],
        "agent": "reporter",
        "action": "Generated final report."
    })
    return state
