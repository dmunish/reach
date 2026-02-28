from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
import operator

class UIAction(TypedDict):
    """A typed command for the React frontend to execute."""
    action: str      # "map" | "chart"
    payload: dict


class QueryResult(TypedDict):
    """The raw result of the most recent execute_sql call."""
    columns: list[str]
    rows: list[dict]
    row_count: int


class AgentState(TypedDict):
    # ── Conversation history (append-only via operator.add) ──
    messages: Annotated[List[BaseMessage], operator.add]

    # ── UI side-effects collected across tool calls ──
    # operator.add ensures parallel tool calls both write without overwriting
    ui_actions: Annotated[List[UIAction], operator.add]

    # ── Latest SQL result — written by process_results, read by publish_chart ──
    # Stored here so publish_chart can inject data programmatically via
    # InjectedState without the LLM ever reproducing the rows.
    query_results: Optional[QueryResult]

    # ── Conversation context (injected on each request) ──
    conversation_id: Optional[str]
    user_id: Optional[str]
