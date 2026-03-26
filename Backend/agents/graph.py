from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
import os
import json

from agents.state import State
from agents.prompts import SYSTEM_PROMPT
from agents.tools import query, chart, map

TOOLS = [query, chart, map]

def create_llm():
    return ChatOpenAI(
        model="zai-org/glm-4.7-flash",
        base_url="https://api.novita.ai/openai",
        api_key=os.environ.get("NOVITA_KEY"),
        max_tokens=128000,
        temperature=1.0,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            "enable_thinking": True,
            "clear_thinking": False
        }
    )

def graph():
    # ===== LLM Client =====
    """Build the LangGraph workflow"""
    llm_client = create_llm()
    llm = llm_client.bind_tools(TOOLS)

    # ===== Nodes =====
    def agent(state: State) -> State:
        """
        Main agent reasoning node.
        LLM decides what tools to call or provides final answer.
        """
        messages = state["messages"]

        # Add system prompt if only 1 message i.e. user message
        if len(messages) == 1:
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        
        response = llm.invoke(messages)

        return {
            "messages": [response],
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    def tools(state: State) -> State:
        """
        Execute tools that the agent requested.
        """
        tool_node = ToolNode(TOOLS)
        result = tool_node.invoke(state)

        if hasattr(result, "messages")    :
            messages = getattr(result, "messages")
            for msg in messages:
                if msg.type == "tool" and msg.name == "query":
                    try:
                        tool_output = json.loads(msg.content)
                        if "data" in tool_output:
                            return {
                                "messages": messages,
                                "db_results": tool_output["data"]
                            }
                    except json.JSONDecodeError:
                        pass
        return result

    def should_continue(state: State) -> str:
        """
        Routing function (not node): Should we continue or end?
        """
        messages = state["messages"]
        last = messages[-1]

        # If LLM generated tool calls, we MUST go to tools node
        if last.tool_calls:
            return "continue"
        
        if state["iteration_count"] >= 25:
            return "end"
        
        state["is_complete"] = True
        return "end"
    
    # ===== Graph =====
    workflow = StateGraph(State)
    workflow.add_node("agent", agent)
    workflow.add_node("tools", tools)
    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END
        }
    )

    # After tools, always go back to agent
    workflow.add_edge("tools", "agent")
    app = workflow.compile()
    return app