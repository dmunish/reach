from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from operator import add

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]
    db_results: dict
    iteration_count: int
    is_complete: bool