import json
from typing import Optional
import logging

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from agents.graph import graph
from agents.persistence import ConversationManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("supabase").setLevel(logging.WARNING)
logger = logging.getLogger("reach_agent")
logger.setLevel(logging.INFO)

app = FastAPI(title = "REACH Agent")

# ===== Request/Response Models =====
class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None

# ===== API Endpoints =====
@app.post("/query")
async def run_agent(query: QueryRequest, authorization: str = Header(...)):
    """
    Main endpoint: Send a question to the agent.
    
    Headers:
        Authorization: Bearer <supabase_jwt>
    
    Body:
        {
            "question": "Show me flood alerts in Punjab",
            "conversation_id": "optional-conversation-uuid"
        }
    
    Returns:
        Complete transcript of agent's tool calls and responses
    """

    # Extract jwt
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    jwt = authorization.replace("Bearer ", "")

    if len(query.question) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Request length too large"
        )
    
    try:
        manager = await ConversationManager.create(jwt)
        if not manager:
            raise HTTPException(status_code=500, detail="Failed to initialize persistence manager")

        # Load conversation history and append the new query
        history = await manager.load_conversation(query.conversation_id) if query.conversation_id else []
        user_message = HumanMessage(content=query.question)
        initial_state = history + [user_message]
        
        # Create graph and execute
        agent = graph()
        result = await agent.ainvoke(
            {"messages": initial_state},
            config={"configurable": {"jwt": jwt}}
        )

        new_messages = result["messages"][len(history):]
        final_convo_id, respone_message = await manager.save_conversation(query.conversation_id, new_messages)
        logger.info(f"Response saved successfully for conversation {final_convo_id}")
        print(json.dumps(respone_message, indent=2, default=str))
        return respone_message
    
    except HTTPException:
        raise
    except Exception as e:
        # Log full traceback for debugging
        logger.exception("Agent execution error")
        
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
