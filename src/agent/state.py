from typing import TypedDict

class AgentState(TypedDict):
    readme_content: str
    user_functions: str
    detected_functions: list
    num_functions: int
    iteration_results: list
    test_code: str
    combined_code: str
    pytest_output: str
    pytest_stderr: str
    return_code: int
    iteration: int
    max_iterations: int
    feedback: str
    report: dict
    status: str
    final_message: str
    history: list
    framework: str
    previous_errors: list
