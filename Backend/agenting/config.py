from langchain_openai import ChatOpenAI
import langchain_openai.chat_models.base as openai_base
import os

########################################################################
## PRESERVED THINKING FOR BETTER AGENTIC PERFORMANCE WITH GLM 4.7
########################################################################
# 1. Save the original converter
_original_convert_message_to_dict = openai_base._convert_message_to_dict

# 2. Create a wrapper that injects `reasoning_content` if present
def custom_convert_message_to_dict(message):
    message_dict = _original_convert_message_to_dict(message)
    
    # Check if the message is an AIMessage and has reasoning_content
    # that we need to pass back to the model for Interleaved Thinking
    if hasattr(message, "additional_kwargs") and "reasoning_content" in message.additional_kwargs:
        message_dict["reasoning_content"] = message.additional_kwargs["reasoning_content"]
        
    return message_dict

# 3. Apply the patch globally
openai_base._convert_message_to_dict = custom_convert_message_to_dict

########################################################################
########################################################################

def get_model():
    return ChatOpenAI(
        model="@cf/zai-org/glm-4.7-flash",
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID')}/ai/v1",
        api_key=os.environ.get("CLOUDFLARE_API_KEY"),
        max_tokens=16384,
        temperature=0.7,
        extra_body={
            "thinking": {
                "type": "enabled",
                "clear_thinking": False
            }
        }
    )