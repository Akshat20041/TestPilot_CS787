def should_continue(state) -> str:
    """Decide whether to continue iteration or end."""
    
    status = state.get("status", "")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if status == "success":
        return "reporter"
    
    # Stop if no improvement for 2 consecutive iterations
    if len(state["iteration_results"]) >= 3:
        last_three = state["iteration_results"][-3:]
        if last_three[0]["passed"] == last_three[1]["passed"] == last_three[2]["passed"]:
            state["status"] = "stalled"
            state["feedback"] = "No improvement in last 2 iterations"
            return "reporter"
    
    if iteration > max_iterations:
        state["status"] = "max_iterations"
        state["feedback"] = f"Reached maximum iterations ({max_iterations})"
        return "reporter"
    
    if status == "needs_fix":
        return "generate"
    
    return "reporter"
