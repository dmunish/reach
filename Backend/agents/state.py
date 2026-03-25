from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from operator import add

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]
    reasoning: Annotated[Sequence[str], add]
    text: Annotated[Sequence[str], add]

    tool_calls: Annotated[Sequence[str], add]
    db_results: dict
    commands: Annotated[Sequence[str], add]

    session_id: str
    user_query: str

    iteration_count: int
    is_complete: bool