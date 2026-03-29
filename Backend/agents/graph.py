from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
import os
import json

from agents.state import State
from agents.prompts import SYSTEM_PROMPT
from agents.tools import examples, query, chart, map
from utils import load_env

TOOLS = [query, chart, map, examples]
load_env()

def create_llm():
    # return ChatOpenAI(
    #     model="gpt-oss-120b",
    #     base_url="https://api.cerebras.ai/v1",
    #     api_key=os.environ.get("CEREBRAS_KEY"),
    #     max_tokens=16000,
    #     temperature=0.7,
    #     top_p=0.95,
    # )
    # return ChatOpenAI(
    #     model="minimax/minimax-m2.7",
    #     base_url="https://api.novita.ai/openai",
    #     api_key=os.environ.get("NOVITA_KEY"),
    #     max_tokens=131072,
    #     temperature=0.7,
    #     top_p=0.95
    # )
    return ChatOpenAI(
        model="@cf/zai-org/glm-4.7-flash",
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID')}/ai/v1",
        api_key=os.environ.get("CLOUDFLARE_API_KEY"),
        max_tokens=16384,
        temperature=0.7,
        top_p=0.95,
        # extra_body={
        #     "thinking": {
        #         "type": "enabled",
        #         "clear_thinking": False
        #     }
        # }
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
        config["configurable"]["db_results"] = state.get("db_results")

        tool_node = ToolNode(TOOLS)
        result = await tool_node.ainvoke(state, config = config)

        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            db_results_update = None
            
            # Allow the loop to finish so we don't accidentally swallow parallel tool calls (like map)
            for msg in messages:
                if msg.type == "tool" and msg.name == "query":
                    try:
                        tool_output = json.loads(msg.content)
                        if "data" in tool_output:
                            db_results_update = tool_output["data"]
                    except json.JSONDecodeError:
                        pass
            
            state_update = {"messages": messages}
            if db_results_update is not None:
                state_update["db_results"] = db_results_update
            return state_update
        
        return result

    def should_continue(state: State) -> str:
        """
        Routing function (not node): Should we continue or end?
        """
        if state.get("iteration_count") >= 15:
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