from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agenting.auth import UserContext, get_current_user, require_authenticated
from agenting.graph import agent
from agenting.persistence import delete_conversation, ensure_conversation, list_conversations, load_history, load_messages_for_display, save_messages
from agenting.state import AgentState
from agenting.logging_config import get_logger, LogContext, configure_logging
import json
from typing import Optional

# Configure logging at startup
configure_logging("INFO")

logger = get_logger(__name__)

app = FastAPI(title="REACH Analytics Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                        # Restrict to your frontend domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Request schemas ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    parent_id: Optional[str] = None            # For branching: ID of the message being edited
    # user_id is intentionally absent — always sourced from the verified JWT


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


STATUS_MAP = {
    "execute_sql":            "Querying database…",
    "summarize_data":         "Analyzing data structure…",
    "publish_chart":          "Rendering visualization…",
    "control_map":            "Updating map view…",
    "set_conversation_title": "Saving conversation…",
}


# ── Core streaming generator ──────────────────────────────────────────────────

async def stream_agent(request: ChatRequest, user: UserContext):
    log = LogContext(logger).set(
        user_id=user.user_id,
        is_anonymous=user.is_anonymous,
        chat_message_len=len(request.message)
    )
    
    log.info("📨 STREAM START: Incoming chat request")
    log.debug(f"   Message (first 100 chars): {request.message[:100]}...")
    log.debug(f"   Conversation ID: {request.conversation_id or 'NEW'}")
    
    # 1. Ensure conversation exists (title set later by LLM tool)
    try:
        conversation_id = ensure_conversation(user.user_id, request.conversation_id)
        log.info(f"✅ Conversation prepared: {conversation_id}")
    except Exception as e:
        log.error(f"❌ Conversation Setup Failed: {str(e)}", exc_info=True)
        yield _sse("error", {"content": "Failed to set up conversation."})
        return

    # 2. Load history and build initial state
    try:
        history = load_history(conversation_id) if request.conversation_id else []
        log.info(f"✅ Loaded history: {len(history)} previous messages")
    except Exception as e:
        log.error(f"❌ History Loading Failed: {str(e)}", exc_info=True)
        history = []
    
    user_message = HumanMessage(content=request.message)

    initial_state: AgentState = {
        "messages": history + [user_message],
        "ui_actions": [],
        "query_results": None,
        "conversation_id": conversation_id,
        "user_id": user.user_id,
    }

    # 3. Collect generated messages for persistence after stream
    new_messages: list = [user_message]
    final_ui_state: dict = {}
    
    # Track streaming stats
    has_emitted_thinking = False
    chunk_count = 0
    tool_execution_count = 0
    ui_action_count = 0

    try:
        log.info("🚀 Starting agent stream...")
        async for event in agent.astream_events(initial_state, version="v2"):
            kind = event["event"]

            # ── LLM text tokens (thinking + response) ────────────────────
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                
                # Stream thinking content separately (from reasoning_content in additional_kwargs)
                if hasattr(chunk, "additional_kwargs") and "reasoning_content" in chunk.additional_kwargs:
                    thinking_content = chunk.additional_kwargs["reasoning_content"]
                    if thinking_content:
                        if not has_emitted_thinking:
                            log.info("💭 Thinking content detected, starting stream")
                            yield _sse("thinking_start", {"content": ""})
                            has_emitted_thinking = True
                        yield _sse("thinking", {"content": thinking_content})
                
                # Stream regular response content
                if chunk.content:
                    chunk_count += 1
                    yield _sse("chunk", {"content": chunk.content})

            # ── Tool starts ──────────────────────────────────────────────
            elif kind == "on_tool_start":
                tool_name = event["name"]
                tool_execution_count += 1
                log.info(f"🔧 Tool Start: {tool_name} (#{tool_execution_count})")
                yield _sse("status", {
                    "tool": tool_name,
                    "content": STATUS_MAP.get(tool_name, "Processing…"),
                })

            # ── Tool ends ────────────────────────────────────────────────
            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                raw = event["data"].get("output", "")
                try:
                    output = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    output = raw

                if not isinstance(output, dict):
                    log.debug(f"   Tool output not a dict, skipping processing")
                    continue

                log.info(f"✅ Tool End: {tool_name}")
                log.debug(f"   Output (first 200 chars): {json.dumps(output)[:200]}...")

                # Data preview after execute_sql
                if "row_count" in output:
                    yield _sse("data_preview", {
                        "row_count": output["row_count"],
                        "columns": output.get("columns", []),
                    })
                    log.info(f"   📊 SQL Result: {output.get('row_count')} rows")

                # UI actions — chart and map
                action = output.get("action")
                if action == "render_chart":
                    ui_action_count += 1
                    payload = {
                        "action": "render_chart",
                        "config": output.get("config", {}),
                        "dataset": output.get("dataset", {}),
                        "description": output.get("description", ""),
                    }
                    yield _sse("ui_action", payload)
                    final_ui_state = payload
                    log.info(f"   📈 Chart Action: {output.get('description', 'unnamed')}")

                elif action == "map_update":
                    ui_action_count += 1
                    yield _sse("ui_action", output)
                    final_ui_state = output
                    log.info(f"   🗺️  Map Action")

            # ── Graph end: collect messages for persistence ───────────────
            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                output_state = event["data"].get("output", {})
                if isinstance(output_state, dict) and "messages" in output_state:
                    generated = output_state.get("messages", [])
                    new_messages.extend(generated[len(history):])
                    log.info(f"✅ Graph Complete: {len(generated)} messages generated")

    except Exception as e:
        log.error(f"❌ Stream Error: {str(e)}", exc_info=True)
        yield _sse("error", {"content": "An internal error occurred."})

    finally:
        # 4. Persist all new messages regardless of success/failure
        try:
            log.info(f"💾 Persisting {len(new_messages)} messages...")
            save_messages(
                conversation_id=conversation_id,
                messages=new_messages,
                parent_id=request.parent_id,
                ui_state=final_ui_state if final_ui_state else None,
            )
            log.info(f"✅ Messages persisted successfully")
        except Exception as e:
            log.error(f"❌ Persistence Failed: {str(e)}", exc_info=True)
        
        log.info(f"📊 STREAM COMPLETE: {chunk_count} chunks, {tool_execution_count} tools, {ui_action_count} UI actions")
        yield "data: [DONE]\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Start or continue a conversation. Available to all users (anonymous and authenticated).
    Returns an SSE stream.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    return StreamingResponse(
        stream_agent(request, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # Prevent nginx from buffering SSE
        },
    )


@app.get("/api/conversations")
async def get_conversations(
    user: UserContext = Depends(get_current_user),
):
    """
    List all conversations for the authenticated user, ordered by most recently updated.
    Anonymous users receive 403.

    Response: [ { id, title, created_at, updated_at }, … ]
    """
    require_authenticated(user)
    return list_conversations(user.user_id)


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Load full message history for a conversation.
    Anonymous users receive 403. A conversation belonging to a different user returns 404.

    Response: [ { id, role, content, tool_calls, tool_call_id, ui_state, created_at }, … ]

    Frontend rendering guide:
      role=user                              → user bubble
      role=assistant, content, no tool_calls → AI response bubble
      role=assistant, tool_calls             → optional collapsed "thinking" step
      role=tool, action=render_chart         → ECharts component (use ui_state.config + dataset)
      role=tool, other                       → hidden or collapsed
    """
    require_authenticated(user)
    messages = load_messages_for_display(conversation_id, user.user_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return messages


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Permanently delete a conversation and all its messages.
    Anonymous users receive 403. A conversation belonging to a different user returns 404.
    """
    require_authenticated(user)
    deleted = delete_conversation(conversation_id, user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
