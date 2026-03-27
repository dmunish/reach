from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from agents.state import State
from agents.graph import graph

import json
from typing import Optional
import traceback

app = FastAPI(title = "REACH Agent")

# ===== Request/Response Models =====
class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class AgentResponse(BaseModel):
    transcript: list[dict]
    session_id: Optional[str] = None
    total_iterations: int
    is_complete: bool

# ===== Helper Functions =====
def serialize_message(msg) -> dict:
    """Convert a single message to clean dict"""
    entry = {}
    
    # Reasoning tokens
    if hasattr(msg, "reasoning_content") and msg.reasoning_content:
        entry["reasoning"] = msg.reasoning_content
    
    # Chat content
    if msg.content:
        entry["content"] = msg.content
        entry["role"] = msg.type  # 'human', 'ai', 'tool', 'system'

    # Tool calls (from AI messages)
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        entry["tool_calls"] = [
            {
                "name": call.get("name", ""),
            }
            for call in msg.tool_calls
        ]
    
    # Tool results (from tool messages)
    if msg.type == "tool":
        entry["tool_name"] = msg.name
        try:
            tool_output = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            entry["tool_output"] = tool_output
        except (json.JSONDecodeError, AttributeError):
            entry["tool_output"] = {"raw": msg.content}
           
    return entry

def serialize_state(state: State) -> dict:
    """Convert entire state into clean transcript"""
    transcript = [serialize_message(msg) for msg in state["messages"]]
    
    return {
        "transcript": transcript,
        "total_iterations": state.get("iteration_count", 0),
        "is_complete": state.get("is_complete", False),
        "db_results": state.get("db_results")
    }

# ===== API Endpoints =====
@app.post("/query", response_model=AgentResponse)
async def run_agent(query: QueryRequest, authorization: str = Header(...)):
    """
    Main endpoint: Send a question to the agent.
    
    Headers:
        Authorization: Bearer <supabase_jwt>
    
    Body:
        {
            "question": "Show me flood alerts in Punjab",
            "session_id": "optional-session-uuid"
        }
    
    Returns:
        Complete transcript of agent's reasoning, tool calls, and responses
    """

    # Extract jwt
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    jwt = authorization.replace("Bearer ", "")

    try:
        # Initialize state
        initial_state: State = {
            "messages": [HumanMessage(content=query.question)],
            "db_results": None,
            "iteration_count": 0,
            "is_complete": False
        }

        # Create graph and execute
        agent_graph = graph()
        final_state = await agent_graph.ainvoke(
            initial_state,
            config={"configurable": {"jwt": jwt}}
        )

        # Serialize
        result = serialize_state(final_state)
        print(json.dumps(result, indent=2, default=str))
        return AgentResponse(
            transcript=result["transcript"],
            session_id=query.session_id,
            total_iterations=result["total_iterations"],
            is_complete=result["is_complete"]
        )
    
    except Exception as e:
        # Log full traceback for debugging
        print(f"Agent execution error: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Agent execution failed",
                "message": str(e),
                "type": type(e).__name__
            }
        )

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "REACH-agent"}

# ===== Main Entry Point =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent:app",
        host="0.0.0.0",
        port=8000,
        reload = True
    )
