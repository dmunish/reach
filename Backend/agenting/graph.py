from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from agenting.state import AgentState
from agenting.tools import execute_sql, summarize_data, publish_chart, control_map, set_conversation_title
from agenting.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from agenting.config import get_model
from agenting.logging_config import get_logger, LogContext
import json

logger = get_logger(__name__)

TOOLS = [execute_sql, summarize_data, publish_chart, control_map, set_conversation_title]


def build_graph():
    llm = get_model().bind_tools(TOOLS)

    # ── Node 1: Reasoner ────────────────────────────────────────────────
    def reasoner(state: AgentState) -> dict:
        """LLM decides: call tools or produce final response."""
        log = LogContext(logger).set(
            conversation_id=state.get("conversation_id", "unknown"),
            user_id=state.get("user_id", "unknown")
        )
        
        log.info("🧠 REASONER NODE: Starting LLM reasoning")
        
        try:
            prompt = [SystemMessage(content=SYSTEM_PROMPT)] + FEW_SHOT_EXAMPLES + state["messages"]
            response = llm.invoke(prompt)
            
            # Log thinking content if present
            if hasattr(response, "additional_kwargs") and "reasoning_content" in response.additional_kwargs:
                thinking = response.additional_kwargs["reasoning_content"]
                if thinking:
                    log.info("💭 LLM THINKING OUTPUT")
                    # Print full thinking to console for visibility
                    print(f"\n{'='*80}")
                    print("AGENT THINKING:")
                    print(f"{'='*80}")
                    print(thinking)
                    print(f"{'='*80}\n")
            
            # Log response content if present
            if response.content:
                log.debug(f"📝 LLM Response Content: {response.content[:100]}...")
            
            # Log tool calls if present
            if hasattr(response, "tool_calls") and response.tool_calls:
                log.info(f"🔧 Tool Calls Requested: {len(response.tool_calls)}")
                for i, tool_call in enumerate(response.tool_calls, 1):
                    tool_name = tool_call.get("name", "unknown")
                    tool_args = tool_call.get("args", {})
                    log.info(f"   Tool {i}: {tool_name}")
                    log.debug(f"      Args: {json.dumps(tool_args, indent=2)}")
            
            return {"messages": [response]}
        
        except Exception as e:
            log.error(f"❌ Reasoner Error: {str(e)}", exc_info=True)
            raise

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
        log = LogContext(logger).set(
            conversation_id=state.get("conversation_id", "unknown"),
            user_id=state.get("user_id", "unknown")
        )
        
        log.info("📊 PROCESS NODE: Extracting tool results and UI actions")
        
        ui_actions = []
        query_results = None
        tool_results_logged = 0

        for msg in reversed(state["messages"]):
            if not isinstance(msg, ToolMessage):
                break  # Stop at the most recent tool call batch
            
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError) as e:
                log.warning(f"⚠️  Failed to parse tool message: {str(e)}")
                continue

            if not isinstance(content, dict):
                log.debug(f"   Skipping non-dict tool content: {type(content)}")
                continue

            # Log tool result
            tool_id = msg.tool_call_id
            log.info(f"   Tool Result [{tool_id}]")
            log.debug(f"      Content: {json.dumps(content, indent=2)[:200]}...")
            tool_results_logged += 1

            # Capture the latest SQL result for programmatic data injection
            if "row_count" in content and query_results is None:
                query_results = content
                log.info(f"   ✅ Captured SQL Result: {content.get('row_count')} rows, columns: {content.get('columns', [])}")

            action = content.get("action")
            if action == "render_chart":
                ui_actions.append({
                    "action": "render_chart",
                    "config": content.get("config", {}),
                    "dataset": content.get("dataset", {}),
                    "description": content.get("description", "")
                })
                log.info(f"   📈 Chart Action: {content.get('description', 'unnamed')}")
            elif action == "map_update":
                ui_actions.append({"action": action, "payload": content})
                log.info(f"   🗺️  Map Update Action")
        
        log.info(f"✅ Process Complete: {tool_results_logged} results, {len(ui_actions)} UI actions")
        return {"ui_actions": ui_actions, "query_results": query_results}

    # ── Routing ──────────────────────────────────────────────────────────
    def should_continue(state: AgentState) -> str:
        log = LogContext(logger).set(
            conversation_id=state.get("conversation_id", "unknown"),
            user_id=state.get("user_id", "unknown")
        )
        
        last = state["messages"][-1]
        
        # Check iteration limit
        iteration_count = sum(1 for msg in state["messages"] if isinstance(msg, AIMessage))
        
        # Check if last message has tool calls
        has_tool_calls = hasattr(last, "tool_calls") and last.tool_calls
        
        if iteration_count >= 10:  # reasonable max turns to prevent infinite loops
            log.warning(f"⛔ MAX ITERATIONS REACHED ({iteration_count}). Forcing END.")
            return "end"
        
        route = "tools" if has_tool_calls else "end"
        log.info(f"🔄 ROUTING DECISION: Turn {iteration_count} → {route.upper()}")
        if has_tool_calls:
            log.debug(f"   Last message has tool calls: {len(last.tool_calls)} tool(s) to execute")
        
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
