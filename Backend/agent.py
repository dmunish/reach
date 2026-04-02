import json
import os
from typing import Optional
import logging

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from fastapi.middleware.cors import CORSMiddleware

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

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Request Model =====
class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    stream: bool = False

# ===== Stream Formatter =====
def format_stream(event):
    """Extract relevant information from LangGraph events for the frontend."""
    event_type = event["event"]
    
    if event_type == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        if chunk.content:
            return {"type": "content_chunk", "content": chunk.content}
            
    elif event_type == "on_tool_start":
        name = event["name"]
        return {"type": "tool_start", "name": name, "input": event["data"].get("input")}
        
    elif event_type == "on_tool_end":
        name = event["name"]
        output = event["data"].get("output", {})
        
        content = output.get("content") if isinstance(output, dict) else str(output)
        artifact = output.get("artifact") if isinstance(output, dict) else None
        
        # Exclude large dataset artifacts (e.g. from 'query' tool) from stream to avoid bloat
        # Map/Chart artifacts are small enough and required for immediate UI updates
        if name == "query":
            artifact = None
            
        return {"type": "tool_end", "name": name, "content": content, "artifact": artifact}

    return None

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
        
        agent = graph()

        # Streaming response
        if query.stream:
            async def event_generator():
                final_messages = []
                try:
                    async for event in agent.astream_events({"messages": initial_state}, config={"configurable": {"jwt": jwt}}, version='v2'):
                        formatted = format_stream(event)
                        if formatted:
                            yield f"data: {json.dumps(formatted)}\n\n"

                        if event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                            final_messages = event["data"]["output"]["messages"]

                    # Save on completion
                    new_messages = final_messages[len(history):]
                    final_convo_id, response_messages = await manager.save_conversation(query.conversation_id, new_messages)
                    
                    # Yield final messages (conversation_id is inside the messages)
                    yield f"data: {json.dumps({'type': 'done', 'messages': response_messages})}\n\n"
                    logger.info(f"Response streamed and saved successfully for conversation {final_convo_id}")
                    
                except Exception as e:
                    logger.exception("Streaming error")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        # Non-stream response
        else:
            result = await agent.ainvoke(
                {"messages": initial_state},
                config={"configurable": {"jwt": jwt}}
            )

            new_messages = result["messages"][len(history):]
            final_convo_id, response_messages = await manager.save_conversation(query.conversation_id, new_messages)
            logger.info(f"Response saved successfully for conversation {final_convo_id}")
            return response_messages
    
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
