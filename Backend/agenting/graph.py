from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from agenting.state import AgentState
from agenting.tools import execute_sql, summarize_data, publish_chart, control_map, set_conversation_title
from agenting.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from agenting.config import get_model
import json

TOOLS = [execute_sql, summarize_data, publish_chart, control_map, set_conversation_title]


def build_graph():
    llm = get_model().bind_tools(TOOLS)

    # ── Node 1: Reasoner ────────────────────────────────────────────────
    def reasoner(state: AgentState) -> dict:
        """LLM decides: call tools or produce final response."""
        prompt = [SystemMessage(content=SYSTEM_PROMPT)] + FEW_SHOT_EXAMPLES + state["messages"]
        response = llm.invoke(prompt)
        return {"messages": [response]}

    # ── Node 2: Tool Executor ────────────────────────────────────────────
    # ToolNode automatically parallelises multiple tool_calls in a
    # single AIMessage via asyncio.gather — no extra code required.
    tool_node = ToolNode(TOOLS)

    # ── Node 3: Post-Tool Processing ─────────────────────────────────────
    def process_results(state: AgentState) -> dict:
        """
        Inspect the latest ToolMessages and:
          1. Promote structured UI payloads (render_chart, map_update)
             into ui_actions so the streamer can route them cleanly.
          2. Capture the latest execute_sql result into state["query_results"]
             so publish_chart can read it via InjectedState without the LLM
             ever reproducing the rows.
        """
        ui_actions = []
        query_results = None

        for msg in reversed(state["messages"]):
            if not isinstance(msg, ToolMessage):
                break  # Stop at the most recent tool call batch
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(content, dict):
                continue

            # Capture the latest SQL result for programmatic data injection
            if "row_count" in content and query_results is None:
                query_results = content

            action = content.get("action")
            if action == "render_chart":
                ui_actions.append({
                    "action": "render_chart",
                    "config": content.get("config", {}),
                    "dataset": content.get("dataset", {}),
                    "description": content.get("description", "")
                })
            elif action == "map_update":
                ui_actions.append({"action": action, "payload": content})

        return {"ui_actions": ui_actions, "query_results": query_results}

    # ── Routing ──────────────────────────────────────────────────────────
    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        
        # Check iteration limit
        iteration_count = sum(1 for msg in state["messages"] if isinstance(msg, AIMessage))
        
        # Check if last message has tool calls
        has_tool_calls = hasattr(last, "tool_calls") and last.tool_calls
        
        if iteration_count >= 10: # reasonable max turns to prevent infinite loops
            print(f"[DEBUG GRAPH] 🛑 MAX ITERATIONS REACHED ({iteration_count}). Force ending.")
            return "end"
            
        route = "tools" if has_tool_calls else "end"
        print(f"[DEBUG GRAPH] 🔄 Turn {iteration_count}: routing to -> {route}")
        return route

    # ── Assemble Graph ───────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    graph.add_node("reasoner", reasoner)
    graph.add_node("tools", tool_node)
    graph.add_node("process", process_results)

    graph.set_entry_point("reasoner")

    graph.add_conditional_edges(
        "reasoner", should_continue,
        {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "process")
    graph.add_edge("process", "reasoner")

    return graph.compile()


# Module-level singleton — compiled once at startup
agent = build_graph()
