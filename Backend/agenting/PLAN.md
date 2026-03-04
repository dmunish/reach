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
    title       TEXT,                     -- Set by the LLM via set_conversation_title tool (NULL until first turn completes)
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
```

**Why `operator.add` on `ui_actions`?** LangGraph merges state updates from parallel tool calls by applying the reducer. Using `operator.add` (list append) means two simultaneous tools — say `execute_sql` and `control_map` — can both write UI actions without a race condition.

**Why `query_results` on state?** The LLM should design the chart structure but never transcribe data. Storing rows in state lets `publish_chart` read them via `InjectedState` — a LangGraph mechanism that populates tool parameters from state at runtime, invisibly to the LLM's tool schema.

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

Compresses query results into a pandas-style statistical profile. The LLM uses this to understand data shape and design the chart. It also uses the returned `sample` rows to compose a markdown table in its textual response. The actual data injection into ECharts happens programmatically in `publish_chart` — the LLM never needs to reproduce individual values.

```python
@tool
def summarize_data(columns: list[str], rows: list[dict]) -> dict:
    """
    Compute a pandas-style statistical summary of query results.
    Returns describe() and dtype info per column, plus a 5-row sample.
    ALWAYS call this after execute_sql before writing any chart JSON.

    Use the returned summary and sample to:
      - Understand the data shape for chart design
      - Write a markdown table in your textual response
    Do NOT reproduce data values in publish_chart — they are injected automatically.
    """
    import pandas as pd

    if not rows:
        return {"error": "No data to summarize."}

    df = pd.DataFrame(rows, columns=columns)

    return {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "dtypes": df.dtypes.astype(str).to_dict(),
        "describe": df.describe(include="all").fillna("").astype(str).to_dict(),
        "sample": df.head(5).to_dict(orient="records"),
    }
```

### 5.3 `publish_chart`

The LLM writes the chart **config** — structure, styling, axis labels, series names, chart type, and `encode` mappings. It never touches the data. The tool builds the `dataset` programmatically from `state["query_results"]` using pandas and returns `config` and `dataset` as **separate keys**.

This separation means the frontend can update data independently of chart structure — ECharts supports merging a new `dataset` into an existing instance without reinitialising the chart, which enables data-only re-renders when the user changes a filter or time range without changing the chart shape.

The `encode` pattern replaces the previous `series_mappings` and `x_axis_column` parameters entirely. The LLM already knows the column names because it wrote the SQL — it references them directly in `series[i].encode`, which is standard ECharts and far more expressive:

```json
"series": [
  { "type": "bar", "name": "Flood",     "encode": { "x": "month", "y": "flood_count" } },
  { "type": "bar", "name": "Landslide", "encode": { "x": "month", "y": "landslide_count" } }
]
```

The tool constructs `dataset.source` as an **array-of-arrays** (ECharts' most efficient format): one header row of column names, followed by data rows. ECharts joins `encode` column names to the header automatically.

Making this a tool (rather than an inline JSON field in the response) still gives three benefits: JSON validation before it reaches the frontend, an unambiguous `on_tool_end` event the streamer can route as a `ui_action`, and a stored `ToolMessage` audit trail.

```python
from langgraph.prebuilt import InjectedState
from typing import Annotated

@tool
def publish_chart(
    echart_options_json: str,
    description: str,
    state: Annotated[AgentState, InjectedState],   # invisible to LLM
) -> dict:
    """
    Publish a chart by combining your ECharts config with the query data.

    YOU provide:
      echart_options_json: A complete ECharts option object as a JSON string.
                           Define mappings using series[i].encode — reference
                           column names exactly as they appear in your SQL query.
                           Do NOT include a "dataset" key — it is built automatically.
                           Do NOT include series[i].data arrays.

      description: Short human-readable label for the chart.

    ENCODE PATTERNS:
      Cartesian (bar, line, scatter):
        "encode": { "x": "<column>", "y": "<column>" }

      Pie / donut:
        "encode": { "itemName": "<label_column>", "value": "<value_column>" }

      Multi-axis or stacked: each series references the same x column,
        different y columns.

    The dataset is built programmatically from the last execute_sql result.
    The config and dataset are delivered to the frontend as separate objects
    so the frontend can update data independently of chart structure.
    """
    import json
    import pandas as pd

    # 1. Parse and validate the config skeleton
    try:
        config = json.loads(echart_options_json)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid ECharts JSON: {e}"}

    # Defensive: strip any dataset the LLM may have accidentally included
    config.pop("dataset", None)

    # 2. Pull rows from state — guaranteed to exist if workflow is followed
    query_result = state.get("query_results")
    if not query_result or not query_result.get("rows"):
        return {"error": "No query results in state. Call execute_sql first."}

    df = pd.DataFrame(query_result["rows"])

    # 3. Build dataset.source as array-of-arrays:
    #    [ [col1, col2, ...], [val1, val2, ...], ... ]
    #    This is ECharts' most efficient format and maps directly to encode.
    header = df.columns.tolist()
    rows = df.values.tolist()
    dataset = {"source": [header] + rows}

    return {
        "action": "render_chart",
        "config": config,
        "dataset": dataset,
        "description": description,
    }
```

### 5.4 `control_map`

Resolves a list of place names to their unioned geometry, centroid, and bounding box via the `get_places` RPC, and returns all three for the frontend to use. The LLM only needs to supply the place names it already knows from the query context — no coordinates, no SQL, no geometry reasoning. Returns `action: "map_update"` so `process_results` and the streamer can route it without inspecting the payload structure. Call in parallel with `execute_sql` when a location is involved.

```python
@tool
def control_map(place_names: list[str]) -> dict:
    """
    Control the Mapbox camera and highlight a geometry.

    place_names: List of place names to focus on and highlight.
                 The RPC resolves names to geometries, unions them, and
                 returns a single combined polygon, centroid, and bbox.

    Returns:
        action:          "map_update" — routing signal for the frontend
        unioned_polygon: GeoJSON geometry — for highlighting on the map
        centroid:        GeoJSON geometry — to move the camera
        bbox:            GeoJSON geometry — to set zoom level via fitBounds

    Call in PARALLEL with execute_sql to save latency — emit both in one tool_calls array.
    """
    try:
        client = get_supabase()
        result = client.rpc("get_places", {"place_names": place_names}).execute()
        row = result.data[0]
        return {
            "action": "map_update",
            "unioned_polygon": row["unioned_polygon"],
            "centroid": row["centroid"],
            "bbox": row["bbox"],
        }
    except Exception as e:
        return {"error": str(e)}
```

---

### 5.5 `set_conversation_title`

Called by the LLM **in parallel with its first `execute_sql` call**, so the conversation gets a meaningful title the moment the agent understands the user's intent — without adding any latency. Conversations are created with `title = NULL` by `ensure_conversation`; this tool performs the only title write. It is idempotent: if the title is already set (resumed conversation), the `WHERE title IS NULL` guard makes it a no-op.

The tool reads `conversation_id` from state via `InjectedState`, so the LLM only supplies the title string.

```python
@tool
def set_conversation_title(
    title: str,
    state: Annotated[AgentState, InjectedState],   # invisible to LLM
) -> dict:
    """
    Set a descriptive title for the current conversation.

    Call this ONCE on your first response turn, in PARALLEL with execute_sql.
    Keep the title short (under 60 characters) and specific to the user's query.
    Examples: "Flood alerts in Sindh — 2025", "KPK extreme weather frequency"

    Do NOT call this on subsequent turns — it is a no-op if a title already exists.
    """
    conversation_id = state.get("conversation_id")
    if not conversation_id:
        return {"error": "No conversation_id in state."}

    try:
        client = get_supabase()
        client.table("conversations") \
            .update({"title": title[:60]}) \
            .eq("id", conversation_id) \
            .is_("title", "null") \
            .execute()
        return {"ok": True, "title": title[:60]}
    except Exception as e:
        return {"error": str(e)}
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
   Use the returned summary and sample rows to:
     - Design the best chart type and axis structure
     - Write a markdown table in your textual response to present the data

4. DESIGN — Call publish_chart with an ECharts config JSON and a description.
   Use ECharts' dataset + encode pattern:
     - Do NOT include a "dataset" key — it is built automatically from query results.
     - Do NOT include series[i].data arrays.
     - Define all data mappings using series[i].encode, referencing column names
       exactly as they appear in your SQL SELECT clause.
   Encode patterns:
     - Cartesian (bar, line, scatter): "encode": { "x": "<col>", "y": "<col>" }
     - Pie / donut: "encode": { "itemName": "<label_col>", "value": "<value_col>" }
     - Stacked multi-series: each series has the same "x" column, different "y" columns.

5. MAP — If a location is mentioned, call control_map IN PARALLEL with execute_sql.
   Provide the place names exactly as you know them (province, district, or region names).

6. RESPOND — Write a concise textual answer. Include a markdown table of the key
   figures from the summarize_data sample. Reference the chart. Highlight key insights.

## DATA INJECTION RULE

NEVER include a "dataset" key in your echart_options_json.
NEVER include series[i].data arrays.
Instead, define encode mappings in each series using the exact column names from your SQL.
The dataset is built programmatically from query results and delivered to the frontend
as a separate object — this allows the frontend to update data without re-rendering
the full chart config. You only design structure, style, axes, and encode mappings.

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

  Severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'
  Urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'
  Category values: 'Geo','Met','Safety','Security','Rescue','Fire',
                   'Health','Env','Transport','Infra','CBRNE','Other'

## ECHARTS DESIGN RULES

- Always use dataset + encode. Never use series[i].data or xAxis.data directly.
- Use dark-mode optimized colors. Set backgroundColor: "#0d1117" on every chart.
- All text (titles, axis labels, legends): "#e0e0e0" or "#ccc".
- Grid lines and axis lines: "#333" or "#444".
- Severity color palette: ["#52c41a","#faad14","#ff7a45","#f5222d"]
  maps to: Minor → Moderate → Severe → Extreme
- General series palette: ["#5470c6","#91cc75","#fac858","#ee6666","#73c0de","#3ba272"]
- Always set tooltip.trigger: "axis" for cartesian, "item" for pie/scatter
- For stacked charts: set stack: "total" on each series
- For responsive layout: include grid: { containLabel: true }
- For >12 x-axis points: add dataZoom: [{ type: "inside" }, { type: "slider" }]
- For many categories: xAxis.axisLabel.rotate: 45
- Date format: "MMM YYYY" or "YYYY-MM" on axes
- For radar charts: use encode: { itemName: "<label_col>", value: ["<col1>", ...] }
- For scatter3D: use encode: { x: "<col>", y: "<col>", z: "<col>" } and visualMap

## CONSTRAINTS

- NEVER fabricate data. Every number must come from execute_sql results.
- NEVER call publish_chart without first calling summarize_data.
- ALWAYS call control_map IN PARALLEL with execute_sql when a location is involved.
- On your FIRST response turn, call set_conversation_title IN PARALLEL with execute_sql.
  It is idempotent — safe to include even if called on a resumed conversation.
- If a query returns 0 rows, tell the user — do not generate an empty chart.
- Keep prose concise. Let the chart do the heavy lifting.
"""
```

### 7.2 Few-Shot Examples

Two complete worked examples cover the core patterns: parallel `set_conversation_title` + `execute_sql` on the first turn, parallel `control_map` + `execute_sql` on a location query, and advanced ECharts chart types. Additional examples for other chart types can be appended as needed.

```python
FEW_SHOT_EXAMPLES: list = [

    # ════════════════════════════════════════════════════════════════════════
    # EXAMPLE 1 — Scatter3D
    # Shows: set_conversation_title in parallel on first turn, no location query
    # Query: 3D breakdown of alert counts by province, event type, and severity
    # ════════════════════════════════════════════════════════════════════════

    HumanMessage(content="Give me a 3D breakdown of alert counts by province and event type this year."),

    # ── Turn 1: query DB + set title in parallel ──────────────────────────
    AIMessage(
        content="I'll query the alert data and build a 3D visualization — let me also title this conversation.",
        tool_calls=[
            {
                "id": "call_sql_1", "name": "execute_sql",
                "args": {
                    "query": (
                        "SELECT province, category, severity, COUNT(*) AS count "
                        "FROM alert_search_index "
                        "WHERE effective_from >= date_trunc('year', CURRENT_DATE) "
                        "GROUP BY province, category, severity "
                        "ORDER BY count DESC "
                        "LIMIT 200"
                    )
                }
            },
            {
                "id": "call_title_1", "name": "set_conversation_title",
                "args": {"title": "3D alert breakdown — province & event type"}
            }
        ]
    ),
    ToolMessage(
        content=json.dumps({
            "columns": ["province", "category", "severity", "count"],
            "rows": [
                {"province": "Punjab",      "category": "Met",   "severity": "Moderate", "count": 42},
                {"province": "Sindh",       "category": "Met",   "severity": "Severe",   "count": 35},
                {"province": "Balochistan", "category": "Geo",   "severity": "Severe",   "count": 22},
                {"province": "Sindh",       "category": "Met",   "severity": "Extreme",  "count": 18},
                {"province": "KPK",         "category": "Geo",   "severity": "Severe",   "count": 14},
                {"province": "KPK",         "category": "Met",   "severity": "Extreme",  "count": 12},
                {"province": "Punjab",      "category": "Infra", "severity": "Moderate", "count": 11},
                {"province": "Balochistan", "category": "Met",   "severity": "Minor",    "count": 9},
            ],
            "row_count": 8
        }),
        tool_call_id="call_sql_1"
    ),
    ToolMessage(
        content=json.dumps({"ok": True, "title": "3D alert breakdown — province & event type"}),
        tool_call_id="call_title_1"
    ),

    # ── Turn 2: summarize ─────────────────────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_sum_1", "name": "summarize_data",
            "args": {
                "columns": ["province", "category", "severity", "count"],
                "rows": [
                    {"province": "Punjab",      "category": "Met",   "severity": "Moderate", "count": 42},
                    {"province": "Sindh",       "category": "Met",   "severity": "Severe",   "count": 35},
                    {"province": "Balochistan", "category": "Geo",   "severity": "Severe",   "count": 22},
                    {"province": "Sindh",       "category": "Met",   "severity": "Extreme",  "count": 18},
                    {"province": "KPK",         "category": "Geo",   "severity": "Severe",   "count": 14},
                    {"province": "KPK",         "category": "Met",   "severity": "Extreme",  "count": 12},
                    {"province": "Punjab",      "category": "Infra", "severity": "Moderate", "count": 11},
                    {"province": "Balochistan", "category": "Met",   "severity": "Minor",    "count": 9},
                ]
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "shape": {"rows": 8, "columns": 4},
            "dtypes": {"province": "object", "category": "object", "severity": "object", "count": "int64"},
            "describe": {
                "province": {"unique": "4", "top": "Sindh"},
                "category": {"unique": "3", "top": "Met"},
                "severity": {"unique": "4", "top": "Moderate"},
                "count": {"min": "9", "max": "42", "mean": "20.4"}
            },
            "sample": [
                {"province": "Punjab", "category": "Met", "severity": "Moderate", "count": 42},
                {"province": "Sindh",  "category": "Met", "severity": "Severe",   "count": 35}
            ]
        }),
        tool_call_id="call_sum_1"
    ),

    # ── Turn 3: publish Scatter3D chart ───────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1", "name": "publish_chart",
            "args": {
                "description": "3D scatter of alert counts by province, event type, and severity (current year)",
                "echart_options_json": json.dumps({
                    "backgroundColor": "#0d1117",
                    "title": {
                        "text": "Alert Distribution — Province × Event Type",
                        "left": "center",
                        "textStyle": {"color": "#e0e0e0", "fontSize": 14}
                    },
                    "tooltip": {"trigger": "item"},
                    "visualMap": {
                        "show": True,
                        "dimension": "count",
                        "min": 9,
                        "max": 42,
                        "inRange": {
                            "symbolSize": [5, 40],
                            "color": ["#313695","#4575b4","#74add1","#fee090","#f46d43","#a50026"],
                            "colorAlpha": [0.6, 1]
                        },
                        "textStyle": {"color": "#ccc"},
                        "orient": "vertical",
                        "right": 10
                    },
                    "xAxis3D": {
                        "type": "category", "name": "Province",
                        "nameTextStyle": {"color": "#aaa"}, "axisLabel": {"color": "#ccc"}
                    },
                    "yAxis3D": {
                        "type": "category", "name": "Event Type",
                        "nameTextStyle": {"color": "#aaa"}, "axisLabel": {"color": "#ccc"}
                    },
                    "zAxis3D": {
                        "type": "value", "name": "Alert Count",
                        "nameTextStyle": {"color": "#aaa"}, "axisLabel": {"color": "#ccc"}
                    },
                    "grid3D": {
                        "axisLine": {"lineStyle": {"color": "#444"}},
                        "axisPointer": {"lineStyle": {"color": "#666"}},
                        "viewControl": {"autoRotate": False, "distance": 250, "alpha": 20, "beta": 40}
                    },
                    "series": [{
                        "type": "scatter3D",
                        "symbolSize": 8,
                        "encode": {"x": "province", "y": "category", "z": "count"}
                    }]
                })
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "action": "render_chart",
            "config": {"backgroundColor": "#0d1117", "series": [{"type": "scatter3D", "encode": {"x": "province", "y": "category", "z": "count"}}]},
            "dataset": {"source": [["province","category","severity","count"],["Punjab","Met","Moderate",42]]},
            "description": "3D scatter of alert counts by province, event type, and severity (current year)"
        }),
        tool_call_id="call_chart_1"
    ),

    # ── Turn 4: final response ────────────────────────────────────────────
    AIMessage(content=(
        "Here's the 3D breakdown of alerts issued this year across provinces and event types.\n\n"
        "| Province | Category | Severity | Count |\n"
        "|---|---|---|---|\n"
        "| Punjab | Met | Moderate | 42 |\n"
        "| Sindh | Met | Severe | 35 |\n"
        "| Balochistan | Geo | Severe | 22 |\n"
        "| Sindh | Met | Extreme | 18 |\n"
        "| KPK | Geo | Severe | 14 |\n\n"
        "**Meteorological events dominate** across all provinces, with Punjab recording the "
        "highest single combination (42 moderate-severity weather alerts). "
        "Balochistan stands out for geological activity (22 severe events), "
        "reflecting its seismically active terrain. Bubble size and color both encode alert count — "
        "rotate the 3D view to explore clusters by axis."
    )),


    # ════════════════════════════════════════════════════════════════════════
    # EXAMPLE 2 — Radar
    # Shows: control_map in parallel with execute_sql for a multi-province query
    # Query: disaster category profile comparison across Pakistan's provinces
    # ════════════════════════════════════════════════════════════════════════

    HumanMessage(content="Compare the disaster alert profiles across Pakistan's main provinces."),

    # ── Turn 1: query DB + move map in parallel ───────────────────────────
    AIMessage(
        content="I'll query the per-province category breakdown and highlight all four provinces on the map.",
        tool_calls=[
            {
                "id": "call_sql_1", "name": "execute_sql",
                "args": {
                    "query": (
                        "SELECT province, "
                        "  SUM(CASE WHEN category = 'Met'    THEN 1 ELSE 0 END) AS met_alerts, "
                        "  SUM(CASE WHEN category = 'Geo'    THEN 1 ELSE 0 END) AS geo_alerts, "
                        "  SUM(CASE WHEN category = 'Health' THEN 1 ELSE 0 END) AS health_alerts, "
                        "  SUM(CASE WHEN category = 'Infra'  THEN 1 ELSE 0 END) AS infra_alerts, "
                        "  SUM(CASE WHEN category = 'Rescue' THEN 1 ELSE 0 END) AS rescue_alerts "
                        "FROM alert_search_index "
                        "WHERE province IN ('KPK','Sindh','Punjab','Balochistan') "
                        "  AND effective_from >= NOW() - INTERVAL '1 year' "
                        "GROUP BY province ORDER BY province"
                    )
                }
            },
            {
                "id": "call_map_1", "name": "control_map",
                "args": {"place_names": ["KPK", "Sindh", "Punjab", "Balochistan"]}
            }
        ]
    ),
    ToolMessage(
        content=json.dumps({
            "columns": ["province","met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"],
            "rows": [
                {"province": "Balochistan", "met_alerts": 22, "geo_alerts": 28, "health_alerts": 2,  "infra_alerts": 6,  "rescue_alerts": 15},
                {"province": "KPK",         "met_alerts": 48, "geo_alerts": 15, "health_alerts": 5,  "infra_alerts": 8,  "rescue_alerts": 12},
                {"province": "Punjab",      "met_alerts": 38, "geo_alerts": 2,  "health_alerts": 8,  "infra_alerts": 24, "rescue_alerts": 4},
                {"province": "Sindh",       "met_alerts": 62, "geo_alerts": 3,  "health_alerts": 12, "infra_alerts": 18, "rescue_alerts": 6},
            ],
            "row_count": 4
        }),
        tool_call_id="call_sql_1"
    ),
    ToolMessage(
        content=json.dumps({
            "action": "map_update",
            "unioned_polygon": {"type": "MultiPolygon", "coordinates": []},
            "centroid": {"type": "Point", "coordinates": [69.0, 30.0]},
            "bbox": {"type": "Polygon", "coordinates": [[[60.0,23.0],[60.0,37.0],[77.0,37.0],[77.0,23.0],[60.0,23.0]]]}
        }),
        tool_call_id="call_map_1"
    ),

    # ── Turn 2: summarize ─────────────────────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_sum_1", "name": "summarize_data",
            "args": {
                "columns": ["province","met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"],
                "rows": [
                    {"province": "Balochistan", "met_alerts": 22, "geo_alerts": 28, "health_alerts": 2,  "infra_alerts": 6,  "rescue_alerts": 15},
                    {"province": "KPK",         "met_alerts": 48, "geo_alerts": 15, "health_alerts": 5,  "infra_alerts": 8,  "rescue_alerts": 12},
                    {"province": "Punjab",      "met_alerts": 38, "geo_alerts": 2,  "health_alerts": 8,  "infra_alerts": 24, "rescue_alerts": 4},
                    {"province": "Sindh",       "met_alerts": 62, "geo_alerts": 3,  "health_alerts": 12, "infra_alerts": 18, "rescue_alerts": 6},
                ]
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "shape": {"rows": 4, "columns": 6},
            "dtypes": {"province": "object", "met_alerts": "int64", "geo_alerts": "int64", "health_alerts": "int64", "infra_alerts": "int64", "rescue_alerts": "int64"},
            "describe": {
                "met_alerts":    {"min": "22", "max": "62", "mean": "42.5"},
                "geo_alerts":    {"min": "2",  "max": "28", "mean": "12.0"},
                "infra_alerts":  {"min": "6",  "max": "24", "mean": "14.0"},
                "rescue_alerts": {"min": "4",  "max": "15", "mean": "9.25"}
            },
            "sample": [
                {"province": "Balochistan", "met_alerts": 22, "geo_alerts": 28},
                {"province": "Sindh",       "met_alerts": 62, "geo_alerts": 3}
            ]
        }),
        tool_call_id="call_sum_1"
    ),

    # ── Turn 3: publish Radar chart ───────────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1", "name": "publish_chart",
            "args": {
                "description": "Disaster alert profile comparison across Pakistan's four main provinces",
                "echart_options_json": json.dumps({
                    "backgroundColor": "#0d1117",
                    "title": {
                        "text": "Provincial Disaster Alert Profiles",
                        "left": "center",
                        "textStyle": {"color": "#e0e0e0", "fontSize": 14}
                    },
                    "legend": {
                        "bottom": 5,
                        "textStyle": {"color": "#ccc", "fontSize": 12},
                        "selectedMode": "single"
                    },
                    "tooltip": {"trigger": "item"},
                    "radar": {
                        "indicator": [
                            {"name": "Meteorological", "max": 70},
                            {"name": "Geological",     "max": 35},
                            {"name": "Health",         "max": 15},
                            {"name": "Infrastructure", "max": 30},
                            {"name": "Rescue",         "max": 20}
                        ],
                        "shape": "circle",
                        "splitNumber": 5,
                        "axisName": {"color": "#91cc75"},
                        "splitLine": {
                            "lineStyle": {
                                "color": [
                                    "rgba(145,204,117,0.1)", "rgba(145,204,117,0.2)",
                                    "rgba(145,204,117,0.4)", "rgba(145,204,117,0.6)",
                                    "rgba(145,204,117,0.8)", "rgba(145,204,117,1.0)"
                                ]
                            }
                        },
                        "splitArea": {"show": False},
                        "axisLine": {"lineStyle": {"color": "rgba(145,204,117,0.3)"}}
                    },
                    "color": ["#5470c6", "#91cc75", "#fac858", "#ee6666"],
                    "series": [{
                        "type": "radar",
                        "encode": {
                            "itemName": "province",
                            "value": ["met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"]
                        },
                        "symbol": "none",
                        "lineStyle": {"width": 1.5, "opacity": 0.8},
                        "areaStyle": {"opacity": 0.1}
                    }]
                })
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "action": "render_chart",
            "config": {"backgroundColor": "#0d1117", "series": [{"type": "radar", "encode": {"itemName": "province", "value": ["met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"]}}]},
            "dataset": {"source": [["province","met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"],["Balochistan",22,28,2,6,15],["KPK",48,15,5,8,12],["Punjab",38,2,8,24,4],["Sindh",62,3,12,18,6]]},
            "description": "Disaster alert profile comparison across Pakistan's four main provinces"
        }),
        tool_call_id="call_chart_1"
    ),

    # ── Turn 4: final response ────────────────────────────────────────────
    AIMessage(content=(
        "Each axis of the radar represents a disaster category — each polygon one province.\n\n"
        "| Province | Met | Geo | Health | Infra | Rescue |\n"
        "|---|---|---|---|---|---|\n"
        "| Sindh | 62 | 3 | 12 | 18 | 6 |\n"
        "| KPK | 48 | 15 | 5 | 8 | 12 |\n"
        "| Punjab | 38 | 2 | 8 | 24 | 4 |\n"
        "| Balochistan | 22 | 28 | 2 | 6 | 15 |\n\n"
        "**Sindh** leads on meteorological alerts, driven by monsoon flooding. "
        "**Balochistan** has the highest geological risk — nearly 10× its meteorological count — "
        "reflecting seismic and landslide activity. **Punjab** stands out for infrastructure alerts, "
        "consistent with its dense urban and road network. "
        "Use the legend to isolate individual provinces for a clearer comparison."
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
from .tools import execute_sql, summarize_data, publish_chart, control_map, set_conversation_title
from .prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from .llm_factory import get_model
from .config import settings
import json

ALL_TOOLS = [execute_sql, summarize_data, publish_chart, control_map, set_conversation_title]


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
        Inspect the latest ToolMessages and:
          1. Promote structured UI payloads (render_chart, fly_to, highlight)
             into ui_actions so the streamer can route them cleanly.
          2. Capture the latest execute_sql result into state["query_results"]
             so publish_chart can read it via InjectedState without the LLM
             ever reproducing the rows.
        """
        ui_actions = []
        query_results = None

        for msg in reversed(state["messages"]):
            if not isinstance(msg, ToolMessage):
                break  # Stop at the most recent tool call batch
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(content, dict):
                continue

            # Capture the latest SQL result for programmatic data injection
            if "row_count" in content and query_results is None:
                query_results = content

            action = content.get("action")
            if action == "render_chart":
                ui_actions.append({
                    "action": "render_chart",
                    "config": content.get("config", {}),
                    "dataset": content.get("dataset", {}),
                    "description": content.get("description", "")
                })
            elif action == "map_update":
                ui_actions.append({"action": "map_update", "payload": content})

        return {"ui_actions": ui_actions, "query_results": query_results}

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
) -> str:
    """
    Create a new conversation (with no title) if needed. Returns the conversation_id.
    The title is set later by the LLM via the set_conversation_title tool.
    """
    client = get_supabase()
    if conversation_id:
        return conversation_id

    result = (
        client.table("conversations")
        .insert({"user_id": user_id})
        .execute()
    )
    return result.data[0]["id"]


def list_conversations(user_id: str) -> list[dict]:
    """
    Return all conversations for a user, ordered by most recently updated.
    Used to populate the sidebar conversation list — no message content included.
    """
    client = get_supabase()
    rows = (
        client.table("conversations")
        .select("id, title, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
        .data
    )
    return rows or []


def load_messages_for_display(conversation_id: str) -> list[dict]:
    """
    Return all messages in a conversation for frontend rendering.
    Returns raw dicts (not LangChain objects) — the frontend decides what to show.

    Role rendering guide:
      user      → user chat bubble
      assistant, no tool_calls, has content → AI response bubble
      assistant, has tool_calls → collapsed "thinking" step (optional)
      tool, content parses to action=render_chart → ECharts component
                                                     using ui_state config+dataset
      tool, other → hidden or collapsed
    """
    client = get_supabase()
    rows = (
        client.table("messages")
        .select("id, role, content, tool_calls, tool_call_id, ui_state, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    return rows or []
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
{ "event": "chunk",       "data": { "content": "I found 22 severe alerts…" } }
{ "event": "status",      "data": { "tool": "execute_sql", "content": "Querying database…" } }
{ "event": "data_preview","data": { "row_count": 79, "columns": ["severity","count"] } }
{ "event": "ui_action",   "data": {
    "action": "render_chart",
    "config":  { "title": {…}, "series": [{ "encode": {…} }], … },
    "dataset": { "source": [["severity","count"],["Extreme",8],…] },
    "description": "Alert severity in Sindh"
  }
}
{ "event": "ui_action",   "data": {
    "action": "map_update",
    "payload": {
      "unioned_polygon": { "type": "MultiPolygon", "coordinates": […] },
      "centroid":        { "type": "Point", "coordinates": [68.5, 26.0] },
      "bbox":            { "type": "Polygon", "coordinates": […] }
    }
  }
}
{ "event": "error",       "data": { "content": "Database error: …" } }
```

**`config` and `dataset` are delivered as separate keys in the same event payload.** The frontend merges them for the initial render and can apply a dataset-only update later without reinitialising the chart instance:

```javascript
// Initial render
echartsInstance.setOption({ ...config, dataset })

// Data-only update (e.g. user changes filter, same chart structure)
echartsInstance.setOption({ dataset }, false)  // notMerge: false → merges into existing config
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
from .persistence import load_history, save_messages, ensure_conversation, list_conversations, load_messages_for_display
from .state import AgentState
import json
from typing import Optional

app = FastAPI(title="REACH Analytics Agent", version="1.0.0")

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
| `ui_action { action: "render_chart" }` | Initial render: `setOption({ ...config, dataset })`. Data-only update: `setOption({ dataset }, false)` |
| `ui_action { action: "map_update" }` | `map.flyTo(centroid.coordinates)` + `map.fitBounds(bbox)` + add `unioned_polygon` as a GeoJSON highlight layer |
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
    │    ├─ execute_sql ──► Supabase RPC (read-only role) → rows
    │    ├─ summarize_data ──► pandas describe/info → shape + sample
    │    ├─ publish_chart ──► reads state["query_results"] via InjectedState
    │    │                    builds dataset.source as array-of-arrays with pandas
    │    │                    validates ECharts config (encode mappings only, no data)
    │    │                    returns config + dataset as separate keys
    │    ├─ control_map ──► get_places RPC → { action:"map_update", unioned_polygon, centroid, bbox }
    │    └─ set_conversation_title ──► UPDATE conversations SET title WHERE title IS NULL (first turn, idempotent)
    │        │
    │        ▼
    │   process_results
    │    ├─ promotes ui_actions (render_chart {config,dataset}, map_update)
    │    └─ writes execute_sql rows → state["query_results"]
    │        │
    │        └──────────────► back to reasoner
    │
    └─► final AIMessage (no tool_calls) → stream ends
         LLM response includes markdown table from summarize_data sample
    │
SSE stream → React client
    ├─ chunk events → chat bubble text (including markdown table)
    ├─ status events → "Querying database…" badge
    ├─ ui_action render_chart → setOption({ ...config, dataset })
    │                           data-only refresh → setOption({ dataset }, false)
    └─ ui_action map_update → flyTo(centroid) + fitBounds(bbox) + highlight layer
    │
FastAPI (after stream)
    └─ save_messages → Supabase messages table
```

Every component has a single responsibility. The LLM designs charts; pandas moves the data. The graph is stateless and independently testable. Adding a new tool requires only editing `tools.py` and the `ALL_TOOLS` list in `graph.py`. Swapping the LLM is a two-line change to `.env`.

### API surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Start or continue a conversation. Returns SSE stream. |
| `GET` | `/api/conversations?user_id=` | List all conversations for a user (sidebar). |
| `GET` | `/api/conversations/{id}/messages` | Load full message history for a conversation. |
| `GET` | `/health` | Health check. |