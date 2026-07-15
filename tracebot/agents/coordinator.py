"""
TraceBot Agent Coordinator
Orchestrates the multi-agent workflow using LangGraph:
  Monitor -> Analyze -> Generate -> Debug -> Report
"""
from langgraph.graph import StateGraph, END
from models.schemas import AgentState
from agents.analyzer import analyze_node
from agents.generator import generate_node
from agents.debugger import debug_node


def should_generate(state: AgentState) -> str:
    """Route: if there are untested functions, generate tests."""
    has_gaps = any(a.untested_functions for a in state["analysis"])
    return "generate" if has_gaps else "report"


def should_debug(state: AgentState) -> str:
    """Route: if tests were generated, run them through debug loop."""
    return "debug" if state["generated_tests"] else "report"


def report_node(state: AgentState) -> dict:
    """Produce a final summary report."""
    total_tests = len(state.get("generated_tests", []))
    passed = sum(1 for r in state.get("test_results", []) if r.passed)
    failed = sum(1 for r in state.get("test_results", []) if not r.passed)
    debug_fixes = sum(1 for d in state.get("debug_attempts", []) if d.resolved)

    report = (
        f"TraceBot Run Complete\n"
        f"{'='*40}\n"
        f"Files analyzed: {len(state.get('analysis', []))}\n"
        f"Test files generated: {total_tests}\n"
        f"Tests passed: {passed}\n"
        f"Tests failed: {failed}\n"
        f"Debug fixes applied: {debug_fixes}\n"
    )
    return {"final_report": report, "current_step": "complete"}


def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyze_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("debug", debug_node)
    workflow.add_node("report", report_node)

    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges("analyze", should_generate, {"generate": "generate", "report": "report"})
    workflow.add_conditional_edges("generate", should_debug, {"debug": "debug", "report": "report"})
    workflow.add_edge("debug", "report")
    workflow.add_edge("report", END)

    return workflow.compile()


# Singleton compiled graph
graph = build_graph()
