from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
import json
import pandas as pd
from .config import get_supabase
from .state import AgentState
from typing import Annotated, List



FORBIDDEN_KEYWORDS = frozenset({
    "drop", "delete", "update", "insert",
    "alter", "truncate", "grant", "revoke", "create"
})


@tool
def execute_sql(query: str) -> dict:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns: { "columns": [...], "rows": [...], "row_count": int}

    The schema of REACH is based on the Common Alerting Protocol standard, with some modifications.
    It consists of the following tables:
    ...
    """
    import logging
    normalized = query.lower()
    if any(kw in normalized for kw in FORBIDDEN_KEYWORDS):
        return {"error": "Write operations are not permitted."}

    try:
        client = get_supabase()
        print(f"[DEBUG SQL] 🛠️ Executing query: {query}...")
        result = client.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        columns = list(rows[0].keys()) if rows else []
        print(f"[DEBUG SQL] ✅ Success: Returned {len(rows)} rows.")
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        print(f"[DEBUG SQL] ❌ ERROR: {e}")
        return {"error": str(e)}

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

@tool
def publish_chart(echart_options_json: str,description: str,state: Annotated[AgentState, InjectedState]) -> dict:
    """
    Publish a chart by combining your ECharts config with the query data.

    YOU provide:
      echart_options_json: A complete ECharts option object as a JSON string.
                           Define mappings using series[i].encode, reference
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
    header = df.columns.tolist()
    rows = df.values.tolist()
    dataset = {"source": [header] + rows}

    return {
        "action": "render_chart",
        "config": config,
        "dataset": dataset,
        "description": description,
    }

@tool
def control_map(place_names: List[str]) -> dict:
    """
    Control the Mapbox camera and highlight a geometry.
    
    YOU provide:
    place_names: List of places to focus on and highlight.

    Returns a dict with keys:
        - unioned_polygon: dict  (GeoJSON geometry, for highlighting)
        - centroid: dict         (GeoJSON geometry, to move camera)
        - bbox: dict             (GeoJSON geometry, to set zoom)

    Call in PARALLEL with execute_sql to save latency — emit both in one tool_calls array.
    """
    try:
        client = get_supabase()
        print(f"[DEBUG MAP] 🗺️ Fetching geometry for: {place_names}")
        result = client.rpc("get_places", {"place_names": place_names}).execute()
        if not result.data:
            print(f"[DEBUG MAP] ⚠️ No places found")
            return {"error": "No geometry found for the given places."}
            
        row = result.data[0]
        print(f"[DEBUG MAP] ✅ Success: Found geometry")
        
        return {
        "action": "map_update",
        "unioned_polygon": row["unioned_polygon"],
        "centroid": row["centroid"],
        "bbox": row["bbox"]
        }
    except Exception as e:
        print(f"[DEBUG MAP] ❌ ERROR: {e}")
        return {"error": str(e)}

@tool
def set_conversation_title(title: str, state: Annotated[AgentState, InjectedState]) -> dict:
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
