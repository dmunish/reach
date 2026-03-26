from fastapi import FastAPI
from langchain_core.messages import HumanMessage

from agents.state import State
from agents.graph import graph
import json

def serialize_state(state: State) -> dict:
    """Convert state into clean dict"""
    transcript = []

    for msg in state["messages"]:
        entry = {}
        
        # Reasoning
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            entry["reasoning"] = msg.reasoning_content
        
        # Chat content
        if msg.content:
            entry["content"] = msg.content

        # Tool calls
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            entry["tool_calls"] = [{"name": call.name} for call in msg.tool_calls]
        
        # Tool results
        if msg.type == "tool":
            try:
                tool_output = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                if isinstance(tool_output, dict) and "action" in tool_output:
                    entry["tool_name"] = msg.name
                    entry["tool_output"] = tool_output
            except json.JSONDecodeError:
                pass
           
        transcript.append(entry)

    return transcript

def run_agent(question: str, jwt):
    """Execute agent and return clean output"""
    state: State = {
        "messages": [HumanMessage(content=question)],
        "db_results": None,
        "iteration_count": 0,
        "is_complete": False
    }

    agent_graph = graph()
    final_state = agent_graph.invoke(state, config={"configurable": {"jwt": jwt}})
    return serialize_state(final_state)