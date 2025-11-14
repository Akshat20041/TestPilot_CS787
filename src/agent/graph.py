import functools
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Import agent components using absolute imports
from agent.state import AgentState
from agent.nodes import function_detector_node, test_generator_node, combiner_node, execution_node, critic_node, reporter_node
from agent.router import should_continue

# --------------------- Build Graph -------------------
def build_graph(vectorstore):
    """Build the LangGraph workflow."""
    
    workflow = StateGraph(AgentState)
    
    # The critic_node needs access to the vectorstore, so we use functools.partial
    # to "pre-fill" that argument.
    critic_with_rag = functools.partial(critic_node, vectorstore=vectorstore)
    
    workflow.add_node("detect", function_detector_node)
    workflow.add_node("generate", test_generator_node)
    workflow.add_node("combine", combiner_node)
    workflow.add_node("execute", execution_node)
    workflow.add_node("critic", critic_with_rag)
    workflow.add_node("reporter", reporter_node)
    
    workflow.set_entry_point("detect")
    workflow.add_edge("detect", "generate")
    workflow.add_edge("generate", "combine")
    workflow.add_edge("combine", "execute")
    workflow.add_edge("execute", "critic")
    workflow.add_conditional_edges(
        "critic",
        should_continue,
        {
            "generate": "generate",
            "reporter": "reporter"
        }
    )
    workflow.add_edge("reporter", END)
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app