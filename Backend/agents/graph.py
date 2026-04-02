import os
from operator import add
from typing import TypedDict, Annotated, Sequence

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.prompts import SYSTEM_PROMPT
from agents.tools import examples, query, chart, map
from utils import load_env


TOOLS = [query, chart, map, examples]
load_env()

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]
    iteration_count: int
    is_complete: bool

def create_llm():
    # return ChatOpenAI(
    #     model="openai/gpt-oss-20b",
    #     base_url="https://api.groq.com/openai/v1",
    #     api_key=os.environ.get("GROQ_KEY"),
    #     max_tokens=16384,
    #     temperature=0.7,
    # )
    # return ChatOpenAI(
    #     model="qwen-3-235b-a22b-instruct-2507",
    #     base_url="https://api.cerebras.ai/v1",
    #     api_key=os.environ.get("CEREBRAS_KEY"),
    #     max_tokens=65536,
    #     temperature=0.7,
    #     top_p=0.8,
    # )
    # return ChatOpenAI(
    #     model="minimax/minimax-m2.5-highspeed",
    #     base_url="https://api.novita.ai/openai",
    #     api_key=os.environ.get("NOVITA_KEY"),
    #     max_tokens=65536,
    #     temperature=0.7,
    #     top_p=0.8,
    # )
    return ChatOpenAI(
        model="@cf/zai-org/glm-4.7-flash",
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID')}/ai/v1",
        api_key=os.environ.get("CLOUDFLARE_API_KEY"),
        max_tokens=16384,
        temperature=0.7,
        top_p=0.95,
        extra_body={
            "thinking": {
                "type": "disabled",
                # "clear_thinking": False
            }
        }
    )

def graph():
    # ===== LLM Client =====
    """Build the LangGraph workflow"""
    llm_client = create_llm()
    llm = llm_client.bind_tools(TOOLS)

    # ===== Nodes =====
    async def agent(state: State) -> State:
        """
        Main agent reasoning node.
        LLM decides what tools to call or provides final answer.
        """
        messages = list(state["messages"])

        # Add system prompt
        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))
        
        response = await llm.ainvoke(messages)

        # Check if this is a final answer (no tool calls means completion)
        is_complete = not response.tool_calls

        return {
            "messages": [response],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "is_complete": is_complete
        }
    
    async def tools(state: State, config: RunnableConfig) -> State:
        """
        Execute tools that the agent requested.
        """
        if "configurable" not in config:
            config["configurable"] = {}

        # Find the latest results of `query` execution and inject into config
        dataset = None
        for msg in reversed(state["messages"]):
            if msg.type == "tool" and msg.name == "query":
                dataset = getattr(msg, "artifact", None)
                break
        config["configurable"]["dataset"] = dataset

        tool_node = ToolNode(TOOLS)
        result = await tool_node.ainvoke(state, config = config)        
        return result
    
    def should_continue(state: State) -> str:
        """
        Routing function (not node): Should we continue or end?
        """
        if state.get("iteration_count") >= 10:
            return "end"
        
        messages = state["messages"]
        last = messages[-1]

        # If LLM generated tool calls, we MUST go to tools node
        if last.tool_calls:
            return "continue"
        
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