from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from agenting.config import get_supabase
from agenting.logging_config import get_logger, LogContext
from typing import Optional

logger = get_logger(__name__)


def load_history(conversation_id: str) -> list[BaseMessage]:
    """Load ordered message history for a conversation as LangChain messages."""
    log = LogContext(logger).set(conversation_id=conversation_id)
    
    log.info("📖 Loading conversation history...")
    
    try:
        client = get_supabase()
        rows = (
            client.table("messages")
            .select("role, content, tool_calls, tool_call_id")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
            .data
        )
        
        messages: list[BaseMessage] = []
        for row in rows:
            role = row["role"]
            content = row["content"] or ""
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                tool_calls = row.get("tool_calls") or []
                messages.append(AIMessage(content=content, tool_calls=tool_calls))
            elif role == "tool":
                messages.append(ToolMessage(
                    content=content,
                    tool_call_id=row.get("tool_call_id", "")
                ))
        
        log.info(f"✅ Loaded {len(messages)} messages from history")
        return messages
    
    except Exception as e:
        log.error(f"❌ History Loading Failed: {str(e)}", exc_info=True)
        raise


def save_messages(
    conversation_id: str,
    messages: list[BaseMessage],
    parent_id: Optional[str] = None,
    ui_state: Optional[dict] = None
) -> None:
    """Persist new messages to Supabase."""
    log = LogContext(logger).set(conversation_id=conversation_id)
    
    log.info(f"💾 Saving {len(messages)} message(s)...")
    
    try:
        client = get_supabase()
        records = []
        for msg in messages:
            record: dict = {
                "conversation_id": conversation_id,
                "parent_id": parent_id,
                "ui_state": ui_state,
            }
            if isinstance(msg, HumanMessage):
                record.update({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                record.update({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": msg.tool_calls or None,
                })
            elif isinstance(msg, ToolMessage):
                record.update({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            records.append(record)

        if records:
            client.table("messages").insert(records).execute()
            log.info(f"✅ {len(records)} message(s) persisted")
        else:
            log.debug("   No messages to persist")
    
    except Exception as e:
        log.error(f"❌ Message Persistence Failed: {str(e)}", exc_info=True)
        raise


def ensure_conversation(
    user_id: str,
    conversation_id: Optional[str],
) -> str:
    """
    Create a new conversation (with no title) if needed. Returns the conversation_id.
    The title is set later by the LLM via the set_conversation_title tool.
    """
    log = LogContext(logger).set(user_id=user_id)
    
    if conversation_id:
        log.debug(f"✅ Using existing conversation: {conversation_id}")
        return conversation_id

    try:
        client = get_supabase()
        log.info(f"   Creating new conversation...")
        
        result = (
            client.table("conversations")
            .insert({"user_id": user_id})
            .execute()
        )
        
        new_id = result.data[0]["id"]
        log.info(f"✅ New conversation created: {new_id}")
        return new_id
    
    except Exception as e:
        log.error(f"❌ Conversation Creation Failed: {str(e)}", exc_info=True)
        raise


def list_conversations(user_id: str) -> list[dict]:
    """
    Return all conversations for a user, ordered by most recently updated.
    Used to populate the sidebar conversation list — no message content included.
    """
    log = LogContext(logger).set(user_id=user_id)
    
    log.info("📋 Listing conversations...")
    
    try:
        client = get_supabase()
        rows = (
            client.table("conversations")
            .select("id, title, created_at, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
            .data
        )
        
        log.info(f"✅ Found {len(rows)} conversations")
        return rows or []
    
    except Exception as e:
        log.error(f"❌ List Conversations Failed: {str(e)}", exc_info=True)
        raise


def load_messages_for_display(conversation_id: str, user_id: str) -> list[dict] | None:
    """
    Return all messages in a conversation for frontend rendering.
    Returns None if the conversation does not exist or does not belong to user_id —
    the caller maps this to a 404. Returns raw dicts; the frontend decides what to show.

    Role rendering guide:
      user      → user chat bubble
      assistant, no tool_calls, has content → AI response bubble
      assistant, has tool_calls → collapsed "thinking" step (optional)
      tool, content parses to action=render_chart → ECharts component
                                                     using ui_state config+dataset
      tool, other → hidden or collapsed
    """
    log = LogContext(logger).set(conversation_id=conversation_id, user_id=user_id)
    
    log.info("📖 Loading messages for display...")
    
    try:
        client = get_supabase()

        # Ownership check — prevents enumeration of other users' conversations
        conv = (
            client.table("conversations")
            .select("user_id")
            .eq("id", conversation_id)
            .maybe_single()
            .execute()
        )
        if not conv.data or conv.data["user_id"] != user_id:
            log.warning(f"⚠️  Unauthorized access attempt or conversation not found")
            return None

        rows = (
            client.table("messages")
            .select("id, role, content, tool_calls, tool_call_id, ui_state, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
            .data
        )
        
        log.info(f"✅ Loaded {len(rows)} messages for display")
        return rows or []
    
    except Exception as e:
        log.error(f"❌ Load Messages Failed: {str(e)}", exc_info=True)
        raise


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """
    Delete a conversation and all its messages (cascaded by the DB).
    Returns False if the conversation does not exist or does not belong to user_id.
    The caller maps False to a 404.
    """
    log = LogContext(logger).set(conversation_id=conversation_id, user_id=user_id)
    
    log.info("🗑️  Deleting conversation...")
    
    try:
        client = get_supabase()
        result = (
            client.table("conversations")
            .delete()
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        deleted = len(result.data) > 0
        if deleted:
            log.info(f"✅ Conversation deleted")
        else:
            log.warning(f"⚠️  Conversation not found or not owned by user")
        
        return deleted
    
    except Exception as e:
        log.error(f"❌ Conversation Deletion Failed: {str(e)}", exc_info=True)
        raise
