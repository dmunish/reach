import os
from typing import List, Optional
import logging

import jwt
from supabase import acreate_client
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
            client = await acreate_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY"))
            # Decode and validate provided JWT
            payload = jwt.decode(token, os.environ.get("SUPABASE_JWT_SECRET"), algorithms=["HS256"], audience="authenticated")
            return cls(client=client, user_id=payload["sub"])
        
        except Exception as e:
            logger.exception("Initialization error: Failed to decode JWT or connect to Supabase")
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
        if not conversation_id:
            # Find the first HumanMessage
            query = next((m for m in messages if isinstance(m, HumanMessage)), None)
            new_title = query.content[:30]
            conversation_id = await self._create_conversation(new_title)

            if not conversation_id:
                logger.error("Failed to generate a valid conversation_id.")
                return []
        
        serialized_messages = messages_to_dict(messages)
        rows = [
            {
                "conversation_id": conversation_id,
                "type": message.get("type"),
                "data": message.get("data")
            } for message in serialized_messages
        ]
        try:
            response = await self.client.table("messages").insert(rows).execute()
            return conversation_id, response.data

        except Exception as e:
            logger.exception("Exception inserting messages")
            return []


    async def load_conversation(self, conversation_id: str):
        try:
            response = await self.client.table("messages").select("type, data").eq("conversations(user_id)", self.user_id).eq("conversation_id", conversation_id).order("created_at", desc=False).execute()            
            messages = response.data or []
            langgraph_messages = messages_from_dict(messages)
            return langgraph_messages
        
        except Exception as e:
            logger.exception("Exception loading conversation")
            return []