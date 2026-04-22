import os
from typing import List, Optional
import logging
from datetime import datetime, timezone, timedelta

import jwt
from supabase import acreate_client, ClientOptions
from utils import load_env
from langchain_core.messages import BaseMessage, HumanMessage, messages_to_dict, messages_from_dict

load_env()

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, client, user_id):
        # Store already-initialized components
        self.client = client
        self.user_id = user_id
    
    @classmethod
    async def create(cls, token: str):
        try:
            client = await acreate_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY"), options = ClientOptions(postgrest_client_timeout=15))
            # Decode and validate provided JWT
            payload = jwt.decode(token, os.environ.get("SUPABASE_JWT_SECRET"), algorithms=["HS256"], audience="authenticated")
            return cls(client=client, user_id=payload["sub"])
        
        except Exception as e:
            logger.exception(f"Initialization error: {str(e)}")
            return None
    

    async def _create_conversation(self, title: str):
        try: 
            response = await self.client.table("conversations").insert({
                "user_id": self.user_id,
                "title": title
            }).execute()

            return response.data[0].get("id")
        
        except Exception as e:
            logger.exception(f"Exception during conversation creation: {e}")
            return None

    async def save_conversation(self, conversation_id: Optional[str], messages: List[BaseMessage]):
        new_title = None

        if not conversation_id:
            # 1. Get the first human message
            query = next((m for m in messages if isinstance(m, HumanMessage)), None)
            user_text = query.content if query else ""
            
            # 2. Fire a quick, separate LLM call to create the title
            try:
                from agents.graph import create_llm
                from langchain_core.messages import SystemMessage
                
                llm = create_llm()
                prompt = f"Write a short, 3-5 word title for a chat session starting with this message: '{user_text}'. Output ONLY the title."
                
                response = await llm.ainvoke([SystemMessage(content=prompt)])
                new_title = response.content.strip(' "\'')
            except Exception as e:
                logger.warning(f"Failed to generate title: {e}")
                new_title = user_text[:60] if user_text else "New Conversation"

            # Create new conversation
            conversation_id = await self._create_conversation(new_title)

            if not conversation_id:
                logger.error("Failed to generate a valid conversation_id.")
                return None, [], None
        

        serialized_messages = messages_to_dict(messages)

        # Pop unnecessary keys
        keys_to_remove = ["response_metadata", "usage_metadata", "additional_kwargs", "id", "invalid_tool_calls", "status"]
        for message in serialized_messages:
            for key in keys_to_remove:
                message.get("data", {}).pop(key, None)
        
        base_time = datetime.now(timezone.utc)
        
        rows = [
            {
                "conversation_id": conversation_id,
                "type": message.get("type"),
                "data": message.get("data"),
                "created_at": (base_time + timedelta(milliseconds=i)).isoformat()
            } for i, message in enumerate(serialized_messages)
        ]
        try:
            response = await self.client.table("messages").insert(rows).execute()

            # Clean up messages for frontend
            frontend_messages = []
            for msg in response.data:
                clean_msg = {
                    "id": msg.get("id"),
                    "type": msg.get("type"),
                    "data": {}
                }
                
                data_dict = msg.get("data", {})
                msg_type = msg.get("type")

                if data_dict.get("content"):
                    clean_msg["data"]["content"] = data_dict.get("content")

                if msg_type == "ai":
                    tool_calls = data_dict.get("tool_calls", [])
                    for tc in tool_calls: 
                        tc.pop("args", None)

                    if tool_calls:
                        clean_msg["data"]["tool_calls"] = tool_calls

                elif msg_type == "tool":
                    clean_msg["data"]["name"] = data_dict.get("name")
                    clean_msg["data"].pop("content", None)

                    if data_dict.get("name") in ["chart", "map"]:
                        clean_msg["data"]["artifact"] = data_dict.get("artifact")

                frontend_messages.append(clean_msg)   
                                     
            return conversation_id, frontend_messages, new_title

        except Exception as e:
            logger.exception("Exception inserting messages")
            return None, [], None


    async def load_conversation(self, conversation_id: str):
        try:
            # First enforce conversation ownership explicitly to avoid join/filter leaks
            conv_check = await self.client.table("conversations").select("id").eq("id", conversation_id).eq("user_id", self.user_id).execute()
            if not conv_check.data:
                logger.warning(f"Unauthorized or missing conversation {conversation_id} access attempt by user {self.user_id}")
                return []

            response = await self.client.table("messages").select("type, data").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()            
            messages = response.data or []
            langgraph_messages = messages_from_dict(messages)
            return langgraph_messages
        
        except Exception as e:
            logger.exception("Exception loading conversation")
            return []