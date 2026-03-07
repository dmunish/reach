from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agenting.graph import agent
from agenting.persistence import load_history, save_messages, ensure_conversation, list_conversations, load_messages_for_display
from agenting.state import AgentState
import json
from typing import Optional

app = FastAPI(title="REACH Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to your frontend domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request / Response schemas ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    parent_id: Optional[str] = None   # For branching: ID of message being edited
    user_id: str                       # Passed by authenticated frontend


# ── SSE helpers ──────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


STATUS_MAP = {
    "execute_sql":              "Querying database…",
    "summarize_data":           "Analyzing data structure…",
    "publish_chart":            "Rendering visualization…",
    "control_map":              "Updating map view…",
    "set_conversation_title":   "Saving conversation…",
}


# ── Core streaming generator ─────────────────────────────────────────────────

async def stream_agent(request: ChatRequest):
    # 1. Ensure conversation exists (title set later by LLM tool)
    conversation_id = ensure_conversation(
        request.user_id, request.conversation_id
    )

    # 2. Load history and prepend to new message
    history = load_history(conversation_id) if request.conversation_id else []
    user_message = HumanMessage(content=request.message)

    initial_state: AgentState = {
        "messages": history + [user_message],
        "ui_actions": [],
        "query_results": None,
        "conversation_id": conversation_id,
        "user_id": request.user_id,
    }

    # 3. Collect generated messages for persistence after stream
    new_messages: list = [user_message]
    final_ui_state: dict = {}

    try:
        async for event in agent.astream_events(initial_state, version="v2"):
            kind = event["event"]

            # ── LLM text tokens ──────────────────────────────────────────
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield _sse("chunk", {"content": chunk.content})

            # ── Tool starts ──────────────────────────────────────────────
            elif kind == "on_tool_start":
                tool_name = event["name"]
                yield _sse("status", {
                    "tool": tool_name,
                    "content": STATUS_MAP.get(tool_name, "Processing…")
                })

            # ── Tool ends ────────────────────────────────────────────────
            elif kind == "on_tool_end":
                tool_name = event["name"]
                raw = event["data"].get("output", "")

                try:
                    output = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    output = raw

                if not isinstance(output, dict):
                    continue

                # Data preview (execute_sql result)
                if "row_count" in output:
                    yield _sse("data_preview", {
                        "row_count": output["row_count"],
                        "columns": output.get("columns", [])
                    })

                # UI actions (chart, map)
                action = output.get("action")
                if action == "render_chart":
                    # Pass config and dataset as separate keys — the frontend
                    # merges them for first render and can update dataset-only later.
                    payload = {
                        "action": "render_chart",
                        "config": output.get("config", {}),
                        "dataset": output.get("dataset", {}),
                        "description": output.get("description", "")
                    }
                    yield _sse("ui_action", payload)
                    final_ui_state = payload

                elif action == "map_update":
                    yield _sse("ui_action", output)
                    final_ui_state = output

            # ── Node ends: collect final messages for persistence ─────────
            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                output_state = event["data"].get("output", {})
                generated = output_state.get("messages", [])
                # Only the messages after the history we loaded
                new_messages.extend(generated[len(history):])

    except Exception as e:
        yield _sse("error", {"content": str(e)})

    finally:
        # 4. Persist all new messages
        save_messages(
            conversation_id=conversation_id,
            messages=new_messages,
            parent_id=request.parent_id,
            ui_state=final_ui_state if final_ui_state else None,
        )
        yield f"data: [DONE]\n\n"


# ── Endpoint ─────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    return StreamingResponse(
        stream_agent(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Prevent nginx from buffering SSE
        },
    )


@app.get("/api/conversations")
async def get_conversations(user_id: str):
    """
    Return the conversation list for the sidebar.
    Ordered by most recently updated — no message content included.

    Response: [ { id, title, created_at, updated_at }, … ]
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    return list_conversations(user_id)


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    """
    Return all messages in a conversation for rendering a full chat history.

    Response: [ { id, role, content, tool_calls, tool_call_id, ui_state, created_at }, … ]

    Frontend rendering guide:
      role=user                              → user bubble
      role=assistant, content, no tool_calls → AI response bubble
      role=assistant, tool_calls             → optional collapsed "thinking" step
      role=tool, action=render_chart         → ECharts component
                                               (use ui_state.config + ui_state.dataset)
      role=tool, other                       → hidden or collapsed
    """
    return load_messages_for_display(conversation_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
