# REACH Analytics Agent — Integration Plan

> **Objective:** Integrate a stateful, streaming QA and analytics agent into the REACH platform, transforming it from a passive visualization dashboard into an interactive decision-support system.

---

## 1. Overview

The agent is a **LangGraph-based, provider-agnostic AI pipeline** that lives inside a new `agenting/` module. It exposes a single **FastAPI** endpoint that streams Server-Sent Events (SSE) to the frontend. Each event carries a typed payload that the React client can route to the correct component — chat bubble, Mapbox camera, or Apache ECharts renderer.

### Design principles applied

| Principle | Application |
|---|---|
| **Single Responsibility** | Each file has one job: state, tools, prompts, graph, LLM factory, persistence, server |
| **Open/Closed** | New tools and LLM providers can be added without touching existing logic |
| **Dependency Inversion** | The graph depends on abstract `BaseChatModel`; any provider slots in |
| **Separation of Concerns** | Tools return raw data; a dedicated `process` node promotes UI commands |
| **Don't Repeat Yourself** | The schema description lives once (in `prompts.py`); everything else references it |

---

## 2. Folder Structure

```
agenting/
├── agent.py              # FastAPI app — the only public interface
├── graph.py              # LangGraph graph definition and compilation
├── state.py              # AgentState TypedDict (single source of truth)
├── tools.py              # All tool definitions (@tool decorated functions)
├── prompts.py            # SYSTEM_PROMPT + FEW_SHOT_EXAMPLES
├── llm_factory.py        # Provider-agnostic LLM factory
├── persistence.py        # Supabase conversation & message persistence
├── supabase_client.py    # Supabase singleton client
└── config.py             # Pydantic settings (env vars, model defaults)
```

The `agenting/` folder is a self-contained Python package. Nothing outside it should be imported — it connects to the existing Supabase instance via environment variables.

---

## 3. Database Additions (Supabase)

Two new tables must be created in Supabase to support persistent, branching conversations. These do **not** modify any existing tables.

### 3.1 `conversations`

```sql
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title       TEXT,                     -- Auto-generated from first message
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

### 3.2 `messages`

```sql
CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID REFERENCES conversations(id) ON DELETE CASCADE NOT NULL,
    parent_id        UUID REFERENCES messages(id) ON DELETE SET NULL,  -- Enables branching
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content          TEXT,
    tool_calls       JSONB,          -- Tool name + args if role = 'assistant'
    tool_call_id     TEXT,           -- Correlates tool result to tool call
    ui_state         JSONB,          -- Snapshot of map position / chart at this turn
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX idx_messages_parent ON messages(parent_id);
```

> **Branching:** When a user edits a past message, the frontend sends the `parent_id` of the message being edited. The agent writes new messages under that parent, creating a fork. Old branches are preserved.

### 3.3 Read-Only Database Role

Create a dedicated Postgres role for the agent. This is the primary SQL injection safeguard — no amount of prompt injection can bypass a role with no write grants.

```sql
CREATE ROLE agent_readonly NOLOGIN;

GRANT USAGE ON SCHEMA public TO agent_readonly;
GRANT SELECT ON
    documents,
    alerts,
    alert_areas,
    places,
    alert_search_index
TO agent_readonly;

-- Grant execute on the helper RPC only
GRANT EXECUTE ON FUNCTION execute_readonly_sql(TEXT) TO agent_readonly;
```

### 3.4 `execute_readonly_sql` RPC

A Postgres function that the agent calls instead of a raw connection. This enforces `SET TRANSACTION READ ONLY` at the session level.

```sql
CREATE OR REPLACE FUNCTION execute_readonly_sql(query_text TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    SET LOCAL TRANSACTION READ ONLY;
    EXECUTE 'SELECT jsonb_agg(row_to_json(t)) FROM (' || query_text || ') t' INTO result;
    RETURN COALESCE(result, '[]'::JSONB);
END;
$$;
```

---

## 4. Agent State

`state.py` defines the **single source of truth** that flows through every node in the graph.

```python
# agenting/state.py

from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
import operator


class UIAction(TypedDict):
    """A typed command for the React frontend to execute."""
    action: str      # "fly_to" | "highlight" | "render_chart"
    payload: dict


class AgentState(TypedDict):
    # ── Conversation history (append-only via operator.add) ──
    messages: Annotated[List[BaseMessage], operator.add]

    # ── UI side-effects collected across tool calls ──
    # operator.add ensures parallel tool calls both write without overwriting
    ui_actions: Annotated[List[UIAction], operator.add]

    # ── Conversation context (injected on each request) ──
    conversation_id: Optional[str]
    user_id: Optional[str]
```

**Why `operator.add` on `ui_actions`?** LangGraph merges state updates from parallel tool calls by applying the reducer. Using `operator.add` (list append) means two simultaneous tools — say `execute_sql` and `control_map` — can both write UI actions without a race condition.

---

## 5. Tool Definitions

`tools.py` defines the four tools. All are pure functions decorated with `@tool`. They only return data; side-effects (like adding to `ui_actions`) happen in the `process` node downstream.

### 5.1 `execute_sql`

Runs a read-only SQL query via the `execute_readonly_sql` RPC. A secondary keyword blocklist acts as a defense-in-depth layer on top of the DB role.

```python
# agenting/tools.py (excerpt)

from langchain_core.tools import tool
from .supabase_client import get_supabase

FORBIDDEN_KEYWORDS = frozenset({
    "drop", "delete", "update", "insert",
    "alter", "truncate", "grant", "revoke", "create"
})


@tool
def execute_sql(query: str) -> dict:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.

    Returns: { "columns": [...], "rows": [...], "row_count": int }

    Schema available:
      - documents(id, source, posted_date, title, url, filename, processed_at, scraped_at)
      - alerts(id, document_id, category, event, urgency, severity, description,
               instruction, effective_from, effective_until)
      - alert_areas(id, alert_id, place_id, specific_effective_from,
                    specific_effective_until, specific_urgency, specific_severity)
      - places(id, name, parent_id, parent_name, hierarchy_level, polygon)
      - alert_search_index(alert_id, centroid, bbox, unioned_polygon, search_text,
                           category, severity, urgency, event, description, instruction,
                           source, url, posted_date, effective_from, effective_until,
                           affected_places, place_ids)

    Useful patterns:
      - ST_AsGeoJSON(polygon) → GeoJSON for map highlighting
      - ST_X(centroid), ST_Y(centroid) → lon, lat
      - Use alert_search_index for fast analytical queries (pre-joined, indexed)
      - severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'
      - urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'
      - category values: 'Geo','Met','Safety','Security','Rescue','Fire',
                         'Health','Env','Transport','Infra','CBRNE','Other'
    """
    normalized = query.lower()
    if any(kw in normalized for kw in FORBIDDEN_KEYWORDS):
        return {"error": "Write operations are not permitted."}

    try:
        client = get_supabase()
        result = client.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        columns = list(rows[0].keys()) if rows else []
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e)}
```

### 5.2 `summarize_data`

Compresses query results into a statistical profile so the LLM can design a chart without consuming its context window on raw rows.

```python
@tool
def summarize_data(columns: list[str], rows: list[dict]) -> dict:
    """
    Compute a statistical summary of query results.
    Returns min, max, mean, unique counts, and sample values per column.
    ALWAYS call this after execute_sql before writing ECharts JSON.
    """
    import statistics

    summary = {}
    for col in columns:
        values = [r[col] for r in rows if r.get(col) is not None]
        info: dict = {"count": len(values), "nulls": len(rows) - len(values)}

        if values and isinstance(values[0], (int, float)):
            info["min"] = min(values)
            info["max"] = max(values)
            info["mean"] = round(statistics.mean(values), 2)
        else:
            unique = list(dict.fromkeys(values))  # Preserves order, deduplicates
            info["unique_count"] = len(unique)
            info["unique_values"] = unique[:15]    # Cap at 15 to avoid token bloat
            info["sample"] = values[:3]

        summary[col] = info

    return summary
```

### 5.3 `publish_chart`

Validates and publishes a fully-constructed Apache ECharts `option` object. Making this a tool (rather than an inline JSON field in the response) gives three benefits: JSON validation before it reaches the frontend, an unambiguous `on_tool_end` event the streamer can route as a `ui_action`, and a stored `ToolMessage` audit trail.

```python
@tool
def publish_chart(echart_options_json: str, description: str) -> dict:
    """
    Publish a complete Apache ECharts options object to the frontend.

    'echart_options_json': A COMPLETE, valid ECharts option object as a JSON string.
    All series[].data arrays must contain REAL data from query results — no placeholders.

    'description': Short human-readable label (e.g. "Monthly flood alerts in Sindh, 2025")
    """
    import json

    try:
        options = json.loads(echart_options_json)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid ECharts JSON: {e}"}

    return {
        "action": "render_chart",
        "payload": options,
        "description": description
    }
```

### 5.4 `control_map`

Sends a camera command and/or fetches a geometry to highlight. Can be called **in parallel** with `execute_sql` — the LLM should always issue both in the same `tool_calls` array when a location is involved.

```python
@tool
def control_map(
    action: str,
    lat: float | None = None,
    lon: float | None = None,
    zoom: float | None = None,
    bbox: list[float] | None = None,   # [west, south, east, north]
    geometry_sql: str | None = None    # SELECT returning ST_AsGeoJSON(...)
) -> dict:
    """
    Control the Mapbox camera and/or highlight a geometry.

    action: "fly_to" | "highlight"
    lat, lon, zoom: Camera target (WGS84)
    bbox: [west, south, east, north] for fitBounds
    geometry_sql: A SELECT query returning { geojson: <GeoJSON string> } rows.
                  Example: SELECT ST_AsGeoJSON(polygon) AS geojson
                           FROM places WHERE name = 'Sindh' AND hierarchy_level = 1

    Call in PARALLEL with execute_sql to save latency — emit both in one tool_calls array.
    """
    result: dict = {"action": action}

    if lat is not None and lon is not None:
        result["center"] = [lon, lat]
        result["zoom"] = zoom or 7

    if bbox:
        result["bbox"] = bbox

    if geometry_sql:
        try:
            client = get_supabase()
            geom = client.rpc("execute_readonly_sql", {"query_text": geometry_sql}).execute()
            result["geometry"] = geom.data
        except Exception as e:
            result["geometry_error"] = str(e)

    return result
```

---

## 6. LLM Factory

`llm_factory.py` decouples the graph from any specific provider. Adding a new provider is a one-line addition to the `elif` chain.

```python
# agenting/llm_factory.py

import os
from langchain_core.language_models.chat_models import BaseChatModel


def get_model(provider: str, model_name: str, temperature: float = 0) -> BaseChatModel:
    """
    Return a LangChain-compatible chat model for the given provider.
    All returned models support .bind_tools() and streaming.
    """

    if provider in ("novita", "together", "deepseek", "modal", "openai-compat"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            openai_api_key=os.environ[f"{provider.upper()}_API_KEY"],
            openai_api_base=os.environ[f"{provider.upper()}_BASE_URL"],
            temperature=temperature,
            streaming=True,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ["GOOGLE_API_KEY"],
            temperature=temperature,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=True,
        )

    elif provider == "litellm":
        # Universal bridge — handles 100+ providers via LiteLLM
        from langchain_community.chat_models import ChatLiteLLM
        return ChatLiteLLM(model=model_name, temperature=temperature)

    raise ValueError(f"Unsupported provider: '{provider}'")
```

**Provider configuration** lives in `.env`:

```dotenv
# Active model (change these two lines to swap providers)
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash

# Provider credentials
GOOGLE_API_KEY=...
NOVITA_API_KEY=...
NOVITA_BASE_URL=https://api.novita.ai/v3/openai
MODAL_API_KEY=...
MODAL_BASE_URL=https://your-modal-endpoint/v1
```

`config.py` loads these via Pydantic `BaseSettings`:

```python
# agenting/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.0

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 7. Prompts & Few-Shot Examples

`prompts.py` contains the system prompt and few-shot examples that steer the LLM's behaviour. The system prompt embeds the **actual REACH schema** and ECharts design rules. Few-shot examples demonstrate the `execute_sql → summarize_data → publish_chart` pipeline alongside parallel `control_map` calls.

### 7.1 System Prompt (key sections)

```python
# agenting/prompts.py (excerpt)

SYSTEM_PROMPT = """You are the REACH Analytics Agent — an expert data analyst and
visualization designer for Pakistan's disaster management platform. You help users
explore disaster alerts and geographic patterns through data, maps, and charts.

## YOUR WORKFLOW

1. PLAN — Reason whether the user needs a chart even if they haven't asked for one.
   Pick the chart type that best represents the data:
   - time series → line chart
   - category comparison → bar chart (stacked if multi-series)
   - distribution → scatter or histogram
   - composition → pie / stacked bar
   - geographic density → map highlight + bar side-by-side

2. QUERY — Write SQL using alert_search_index for analytics (pre-joined, fast).
   You may write TWO queries: one aggregated for the chart, one for textual insight.

3. INSPECT — ALWAYS call summarize_data after execute_sql. Never skip.

4. DESIGN — Call publish_chart with a COMPLETE ECharts option JSON string.
   Embed REAL data into series[].data. No placeholders.

5. MAP — If a location is mentioned, call control_map IN PARALLEL with execute_sql.
   Provide geometry_sql to highlight the boundary.

6. RESPOND — Write a concise textual answer. Reference the chart. Highlight key insights.

## DATABASE SCHEMA

  alert_search_index (primary analytics table — use this for most queries):
    alert_id UUID, centroid GEOMETRY, bbox GEOMETRY, unioned_polygon GEOMETRY,
    search_text TEXT, category TEXT, severity TEXT, urgency TEXT, event TEXT,
    description TEXT, instruction TEXT, source TEXT, url TEXT, posted_date DATE,
    effective_from TIMESTAMPTZ, effective_until TIMESTAMPTZ,
    affected_places TEXT[], place_ids UUID[]

  places:
    id UUID, name TEXT, parent_id UUID, parent_name TEXT,
    hierarchy_level INT, polygon GEOMETRY
    (hierarchy_level: 1=province, 2=district, 3=tehsil)

  Useful PostGIS functions:
    ST_AsGeoJSON(polygon) → GeoJSON string for map highlighting
    ST_X(centroid), ST_Y(centroid) → longitude, latitude
    ST_Centroid(unioned_polygon) → centroid of alert coverage area

  Severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'
  Urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'
  Category values: 'Geo','Met','Safety','Security','Rescue','Fire',
                   'Health','Env','Transport','Infra','CBRNE','Other'

## ECHARTS DESIGN RULES

- Severity color palette: ["#52c41a","#faad14","#ff7a45","#f5222d"]
  maps to: Minor → Moderate → Severe → Extreme
- General series palette: ["#5470c6","#91cc75","#fac858","#ee6666","#73c0de","#3ba272"]
- Always set tooltip.trigger: "axis" for cartesian, "item" for pie/scatter
- For stacked charts: set stack: "total" on each series
- For responsive layout: include grid: { containLabel: true }
- For >12 x-axis points: add dataZoom: [{ type: "inside" }, { type: "slider" }]
- For many categories: xAxis.axisLabel.rotate: 45
- Date format: "MMM YYYY" or "YYYY-MM" on axes

## CONSTRAINTS

- NEVER fabricate data. Every number must come from execute_sql results.
- NEVER call publish_chart without first calling summarize_data.
- ALWAYS call control_map in PARALLEL with execute_sql when a location is involved.
- If a query returns 0 rows, tell the user — do not generate an empty chart.
- Keep prose concise. Let the chart do the heavy lifting.
"""
```

### 7.2 Few-Shot Examples

One complete worked example is sufficient to establish the tool-call pattern. Additional examples for chart types (pie, scatter, heatmap) can be appended as needed.

```python
FEW_SHOT_EXAMPLES: list = [
    HumanMessage(content="Show me the breakdown of alert severity in Sindh this year."),

    AIMessage(
        content="I'll query the alert data for Sindh and prepare a visualization.",
        tool_calls=[
            {
                "id": "call_sql_1", "name": "execute_sql",
                "args": {
                    "query": (
                        "SELECT severity, COUNT(*) AS count "
                        "FROM alert_search_index "
                        "WHERE 'Sindh' = ANY(affected_places) "
                        "  AND posted_date >= date_trunc('year', CURRENT_DATE) "
                        "GROUP BY severity "
                        "ORDER BY CASE severity "
                        "  WHEN 'Extreme' THEN 1 WHEN 'Severe' THEN 2 "
                        "  WHEN 'Moderate' THEN 3 WHEN 'Minor' THEN 4 ELSE 5 END"
                    )
                }
            },
            {
                "id": "call_map_1", "name": "control_map",
                "args": {
                    "action": "highlight",
                    "lat": 26.0, "lon": 68.5, "zoom": 7,
                    "geometry_sql": (
                        "SELECT ST_AsGeoJSON(polygon) AS geojson "
                        "FROM places WHERE name = 'Sindh' AND hierarchy_level = 1"
                    )
                }
            }
        ]
    ),

    ToolMessage(
        content='{"columns":["severity","count"],"rows":[{"severity":"Extreme","count":8},{"severity":"Severe","count":22},{"severity":"Moderate","count":35},{"severity":"Minor","count":14}],"row_count":4}',
        tool_call_id="call_sql_1"
    ),
    ToolMessage(
        content='{"action":"highlight","center":[68.5,26.0],"zoom":7}',
        tool_call_id="call_map_1"
    ),

    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_sum_1", "name": "summarize_data",
            "args": {
                "columns": ["severity", "count"],
                "rows": [
                    {"severity": "Extreme", "count": 8},
                    {"severity": "Severe", "count": 22},
                    {"severity": "Moderate", "count": 35},
                    {"severity": "Minor", "count": 14}
                ]
            }
        }]
    ),
    ToolMessage(
        content='{"severity":{"unique_count":4,"unique_values":["Extreme","Severe","Moderate","Minor"]},"count":{"min":8,"max":35,"mean":19.75}}',
        tool_call_id="call_sum_1"
    ),

    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1", "name": "publish_chart",
            "args": {
                "description": "Alert severity distribution in Sindh (current year)",
                "echart_options_json": '{"title":{"text":"Alert Severity in Sindh","subtext":"Current year","left":"center"},"tooltip":{"trigger":"item"},"legend":{"bottom":0},"color":["#f5222d","#ff7a45","#faad14","#52c41a"],"series":[{"type":"pie","radius":["40%","70%"],"data":[{"name":"Extreme","value":8},{"name":"Severe","value":22},{"name":"Moderate","value":35},{"name":"Minor","value":14}],"emphasis":{"itemStyle":{"shadowBlur":10}}}]}'
            }
        }]
    ),
    ToolMessage(
        content='{"action":"render_chart","description":"Alert severity distribution in Sindh (current year)"}',
        tool_call_id="call_chart_1"
    ),

    AIMessage(content=(
        "Sindh currently has **79 alerts** active this year. "
        "Moderate-severity alerts dominate (44%), while Extreme alerts "
        "represent a concerning 10% of all active incidents. "
        "The map shows the Sindh boundary highlighted, and the donut chart "
        "above breaks down the severity distribution in full."
    )),
]
```

---

## 8. Graph Definition

`graph.py` assembles the LangGraph state machine. It follows the `reasoner → tools (parallel) → process → reasoner` loop, terminating when the LLM produces a response with no tool calls.

```
         ┌────────────┐
         │  reasoner  │◄──────────────────┐
         └─────┬──────┘                   │
               │                          │
         has tool_calls?                  │
          ┌────┴────┐                     │
         yes        no                    │
          │         │                     │
          ▼         ▼                     │
     ┌─────────┐  [END]                  │
     │  tools  │  (ToolNode,             │
     │         │   parallel exec)        │
     └────┬────┘                         │
          │                              │
          ▼                              │
     ┌──────────┐                        │
     │ process  │────────────────────────┘
     │ results  │  (promote UI actions)
     └──────────┘
```

```python
# agenting/graph.py

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage
from .state import AgentState
from .tools import execute_sql, summarize_data, publish_chart, control_map
from .prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from .llm_factory import get_model
from .config import settings
import json

ALL_TOOLS = [execute_sql, summarize_data, publish_chart, control_map]


def build_graph():
    llm = get_model(
        settings.llm_provider,
        settings.llm_model,
        settings.llm_temperature
    ).bind_tools(ALL_TOOLS)

    # ── Node 1: Reasoner ────────────────────────────────────────────────
    def reasoner(state: AgentState) -> dict:
        """LLM decides: call tools or produce final response."""
        prompt = [SystemMessage(content=SYSTEM_PROMPT)] + FEW_SHOT_EXAMPLES + state["messages"]
        response = llm.invoke(prompt)
        return {"messages": [response]}

    # ── Node 2: Tool Executor ────────────────────────────────────────────
    # ToolNode automatically parallelises multiple tool_calls in a
    # single AIMessage via asyncio.gather — no extra code required.
    tool_node = ToolNode(ALL_TOOLS)

    # ── Node 3: Post-Tool Processing ─────────────────────────────────────
    def process_results(state: AgentState) -> dict:
        """
        Inspect the latest ToolMessages and promote structured payloads
        (render_chart, fly_to, highlight) into ui_actions.
        Keeps tools pure (data-only returns) and graph routing clean.
        """
        ui_actions = []
        for msg in reversed(state["messages"]):
            if not isinstance(msg, ToolMessage):
                break  # Stop at the most recent tool call batch
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(content, dict):
                continue

            action = content.get("action")
            if action == "render_chart":
                ui_actions.append({
                    "action": "render_chart",
                    "payload": content.get("payload", {}),
                    "description": content.get("description", "")
                })
            elif action in ("fly_to", "highlight"):
                ui_actions.append({"action": action, "payload": content})

        return {"ui_actions": ui_actions}

    # ── Routing ──────────────────────────────────────────────────────────
    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    # ── Assemble Graph ───────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    graph.add_node("reasoner", reasoner)
    graph.add_node("tools", tool_node)
    graph.add_node("process", process_results)

    graph.set_entry_point("reasoner")

    graph.add_conditional_edges(
        "reasoner", should_continue,
        {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "process")
    graph.add_edge("process", "reasoner")

    return graph.compile()


# Module-level singleton — compiled once at startup
agent = build_graph()
```

---

## 9. Persistence Layer

`persistence.py` handles reading conversation history from Supabase and writing messages back after each turn. It is called by the API endpoint, not by the graph — keeping the graph stateless and testable.

```python
# agenting/persistence.py

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from .supabase_client import get_supabase
import json
from typing import Optional


def load_history(conversation_id: str) -> list[BaseMessage]:
    """Load ordered message history for a conversation as LangChain messages."""
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
    return messages


def save_messages(
    conversation_id: str,
    messages: list[BaseMessage],
    parent_id: Optional[str] = None,
    ui_state: Optional[dict] = None
) -> None:
    """Persist new messages to Supabase."""
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


def ensure_conversation(
    user_id: str,
    conversation_id: Optional[str],
    first_message: str
) -> str:
    """Create a new conversation if needed. Returns the conversation_id."""
    client = get_supabase()
    if conversation_id:
        return conversation_id

    title = first_message[:60] + ("…" if len(first_message) > 60 else "")
    result = (
        client.table("conversations")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    return result.data[0]["id"]
```

---

## 10. Streaming Protocol

Every chunk sent over SSE follows a single discriminated-union schema. The React client switches on `event` to decide where to route the payload.

### 10.1 Event types

| `event` | When emitted | Frontend action |
|---|---|---|
| `status` | Tool call starts | Update "Agent is..." badge |
| `chunk` | LLM text token arrives | Append to chat bubble |
| `data_preview` | `execute_sql` completes | Show "N rows retrieved" indicator |
| `ui_action` | `publish_chart` or `control_map` completes | Trigger ECharts render or `map.flyTo()` |
| `error` | Any exception | Show error state |
| `[DONE]` | Stream complete | Unlock input |

### 10.2 Wire format

```json
{ "event": "chunk",      "data": { "content": "I found 22 severe alerts…" } }
{ "event": "status",     "data": { "tool": "execute_sql", "content": "Querying database…" } }
{ "event": "data_preview","data": { "row_count": 79, "columns": ["severity","count"] } }
{ "event": "ui_action",  "data": { "action": "render_chart", "payload": {…}, "description": "…" } }
{ "event": "ui_action",  "data": { "action": "highlight", "center": [68.5, 26.0], "zoom": 7, "geometry": […] } }
{ "event": "error",      "data": { "content": "Database error: …" } }
```

---

## 11. FastAPI Endpoint

`agent.py` is the **only public file** in `agenting/`. It:

1. Validates the request with Pydantic.
2. Loads conversation history from Supabase.
3. Runs the graph with `astream_events`.
4. Translates LangGraph events into the typed SSE protocol above.
5. Persists new messages after the stream completes.

```python
# agenting/agent.py

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from .graph import agent
from .persistence import load_history, save_messages, ensure_conversation
from .state import AgentState
import json
from typing import Optional

app = FastAPI(title="REACH Analytics Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to your frontend domain in production
    allow_methods=["POST"],
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
    "execute_sql":    "Querying database…",
    "summarize_data": "Analyzing data structure…",
    "publish_chart":  "Rendering visualization…",
    "control_map":    "Updating map view…",
}


# ── Core streaming generator ─────────────────────────────────────────────────

async def stream_agent(request: ChatRequest):
    # 1. Ensure conversation exists
    conversation_id = ensure_conversation(
        request.user_id, request.conversation_id, request.message
    )

    # 2. Load history and prepend to new message
    history = load_history(conversation_id) if request.conversation_id else []
    user_message = HumanMessage(content=request.message)

    initial_state: AgentState = {
        "messages": history + [user_message],
        "ui_actions": [],
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
                    payload = {
                        "action": "render_chart",
                        "payload": output.get("payload", {}),
                        "description": output.get("description", "")
                    }
                    yield _sse("ui_action", payload)
                    final_ui_state = payload

                elif action in ("fly_to", "highlight"):
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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 12. Deployment

### 12.1 Dependencies (`requirements.txt`)

```
langgraph>=0.2
langchain-core>=0.3
langchain-google-genai>=2.0
langchain-openai>=0.2
langchain-community>=0.3
fastapi>=0.115
uvicorn[standard]>=0.30
supabase>=2.9
pydantic-settings>=2.0
```

### 12.2 Modal (recommended)

The agent runs on Modal as a persistent FastAPI container, matching how REACH's other Python services are deployed.

```python
# modal_app.py (in project root, outside agenting/)

import modal

image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
)

app = modal.App("reach-agent")

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("reach-secrets")],
    keep_warm=1,           # Avoids cold-start latency on first request
    timeout=300,           # 5 min max per stream
    allow_concurrent_inputs=20,
)
@modal.asgi_app()
def serve():
    from agenting.agent import app as fastapi_app
    return fastapi_app
```

```bash
modal deploy modal_app.py
```

### 12.3 Local development

```bash
cd agenting
uvicorn agent:app --reload --port 8001
```

---

## 13. Frontend Integration (React — summary)

The React client consumes the SSE stream with the `EventSource` API (or `fetch` with a `ReadableStream` for POST requests). The event loop is a `useReducer` that maps incoming events to state updates:

| Event | State update |
|---|---|
| `chunk` | Append `content` to `currentMessage` string |
| `status` | Set `agentStatus` label |
| `data_preview` | Show row count badge inside the chat bubble |
| `ui_action { action: "render_chart" }` | Update `chartOptions` state → `<ReactECharts option={chartOptions} />` renders inside the bubble |
| `ui_action { action: "highlight" \| "fly_to" }` | Call `map.flyTo()` / add GeoJSON source layer in Mapbox |
| `[DONE]` | Clear `agentStatus`, unlock input, flush `currentMessage` to history |

Branching is handled by passing `parent_id` (the `id` of the message being edited) with the new request, then replacing the subsequent messages in local state.

---

## 14. Summary

```
User message
    │
    ▼
FastAPI /api/chat
    │  loads history from Supabase
    │  builds AgentState
    ▼
LangGraph (agent)
    │
    ├─► reasoner (LLM with bound tools)
    │        │ tool_calls?
    │        ▼
    │   tools (ToolNode — parallel)
    │    ├─ execute_sql ──► Supabase RPC (read-only role)
    │    ├─ summarize_data ──► statistical summary
    │    ├─ publish_chart ──► validates ECharts JSON
    │    └─ control_map ──► fetches GeoJSON + camera params
    │        │
    │        ▼
    │   process_results (promotes ui_actions)
    │        │
    │        └──────────────► back to reasoner
    │
    └─► final AIMessage (no tool_calls) → stream ends
    │
SSE stream → React client
    ├─ chunk events → chat bubble text
    ├─ status events → "Querying database…" badge
    ├─ ui_action render_chart → ECharts component
    └─ ui_action highlight/fly_to → Mapbox camera
    │
FastAPI (after stream)
    └─ save_messages → Supabase messages table
```

Every component has a single responsibility. The graph is stateless and independently testable. Adding a new tool requires only editing `tools.py` and the `ALL_TOOLS` list in `graph.py`. Swapping the LLM is a two-line change to `.env`.
