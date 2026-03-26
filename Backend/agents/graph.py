from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
import os
import json

from agents.state import State
from agents.prompts import SYSTEM_PROMPT
from agents.tools import query, chart, map
from utils import load_env

TOOLS = [query, chart, map]
load_env()

def create_llm():
    return ChatOpenAI(
        model="@cf/zai-org/glm-4.7-flash",
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID')}/ai/v1",
        api_key=os.environ.get("CLOUDFLARE_API_KEY"),
        max_tokens=16384,
        temperature=1.0,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            "thinking": {
                "type": "enabled",
                "clear_thinking": False
            }
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
    
    def tools(state: State, config: RunnableConfig) -> State:
        """
        Execute tools that the agent requested.
        """
        tool_node = ToolNode(TOOLS)
        result = tool_node.invoke(state, config = config)

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
        
        if state["iteration_count"] >= 10:
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