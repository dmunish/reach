from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
import json
import pandas as pd
from .config import get_supabase
from .state import AgentState
from .logging_config import get_logger, LogContext
from typing import Annotated, List

logger = get_logger(__name__)

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
    log = LogContext(logger)
    
    log.info("🔧 TOOL: execute_sql called")
    log.debug(f"   Query (first 200 chars): {query[:200]}...")
    
    normalized = query.lower()
    if any(kw in normalized for kw in FORBIDDEN_KEYWORDS):
        log.warning(f"⚠️  BLOCKED: Query contains forbidden keyword")
        return {"error": "Write operations are not permitted."}

    try:
        client = get_supabase()
        log.info(f"   Executing SQL query...")
        
        result = client.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        columns = list(rows[0].keys()) if rows else []
        
        log.info(f"✅ SQL Success: {len(rows)} rows, {len(columns)} columns")
        log.debug(f"   Columns: {columns}")
        if rows:
            log.debug(f"   First row sample: {rows[0]}")
        
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    
    except Exception as e:
        log.error(f"❌ SQL Execution Failed: {str(e)}", exc_info=True)
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
    log = LogContext(logger)
    
    log.info("🔧 TOOL: summarize_data called")
    log.debug(f"   Input: {len(columns)} columns, {len(rows)} rows")

    if not rows:
        log.warning(f"⚠️  No data to summarize")
        return {"error": "No data to summarize."}

    try:
        df = pd.DataFrame(rows, columns=columns)
        
        summary = {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "dtypes": df.dtypes.astype(str).to_dict(),
            "describe": df.describe(include="all").fillna("").astype(str).to_dict(),
            "sample": df.head(5).to_dict(orient="records"),
        }
        
        log.info(f"✅ Data Summary: shape={summary['shape']}")
        log.debug(f"   Dtypes: {summary['dtypes']}")
        
        return summary
    
    except Exception as e:
        log.error(f"❌ Summarize Failed: {str(e)}", exc_info=True)
        return {"error": str(e)}

@tool
def publish_chart(echart_options_json: str, description: str, state: Annotated[AgentState, InjectedState]) -> dict:
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
    log = LogContext(logger)
    
    log.info("🔧 TOOL: publish_chart called")
    log.debug(f"   Description: {description}")
    log.debug(f"   ECharts config (first 200 chars): {echart_options_json[:200]}...")
    
    # 1. Parse and validate the config skeleton
    try:
        config = json.loads(echart_options_json)
        log.info(f"✅ ECharts JSON parsed successfully")
    except json.JSONDecodeError as e:
        log.error(f"❌ Invalid ECharts JSON: {str(e)}")
        return {"error": f"Invalid ECharts JSON: {e}"}

    # Defensive: strip any dataset the LLM may have accidentally included
    if "dataset" in config:
        log.warning(f"⚠️  ECharts config included dataset key (should not). Stripping it.")
        config.pop("dataset")

    # 2. Pull rows from state — guaranteed to exist if workflow is followed
    query_result = state.get("query_results")
    if not query_result or not query_result.get("rows"):
        log.error(f"❌ No query results in state. Call execute_sql first.")
        return {"error": "No query results in state. Call execute_sql first."}
    
    log.debug(f"   Query results available: {query_result.get('row_count')} rows")

    try:
        df = pd.DataFrame(query_result["rows"])

        # 3. Build dataset.source as array-of-arrays:
        header = df.columns.tolist()
        rows = df.values.tolist()
        dataset = {"source": [header] + rows}

        log.info(f"✅ Chart data prepared: {len(rows)} rows × {len(header)} columns")
        log.debug(f"   Columns: {header}")

        result = {
            "action": "render_chart",
            "config": config,
            "dataset": dataset,
            "description": description,
        }
        
        log.info(f"✅ Chart published successfully")
        return result
    
    except Exception as e:
        log.error(f"❌ Chart Publishing Failed: {str(e)}", exc_info=True)
        return {"error": str(e)}

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
    log = LogContext(logger)
    
    log.info("🔧 TOOL: control_map called")
    log.debug(f"   Place names: {place_names}")
    
    try:
        client = get_supabase()
        log.info(f"   Fetching geometries for {len(place_names)} place(s)...")
        
        result = client.rpc("get_places", {"place_names": place_names}).execute()
        
        if not result.data:
            log.warning(f"⚠️  No places found for: {place_names}")
            return {"error": "No geometry found for the given places."}
        
        row = result.data[0]
        log.info(f"✅ Geometry retrieved successfully")
        log.debug(f"   Has unioned_polygon, centroid, and bbox")
        
        return {
            "action": "map_update",
            "unioned_polygon": row["unioned_polygon"],
            "centroid": row["centroid"],
            "bbox": row["bbox"]
        }
    except Exception as e:
        log.error(f"❌ Map Control Failed: {str(e)}", exc_info=True)
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
    log = LogContext(logger).set(
        conversation_id=state.get("conversation_id", "unknown")
    )
    
    log.info("🔧 TOOL: set_conversation_title called")
    log.debug(f"   Title: {title[:60]}")
    
    conversation_id = state.get("conversation_id")
    if not conversation_id:
        log.error(f"❌ No conversation_id in state")
        return {"error": "No conversation_id in state."}

    try:
        client = get_supabase()
        log.info(f"   Updating conversation title in database...")
        
        client.table("conversations") \
            .update({"title": title[:60]}) \
            .eq("id", conversation_id) \
            .is_("title", "null") \
            .execute()
        
        log.info(f"✅ Conversation title set: {title[:60]}")
        return {"ok": True, "title": title[:60]}
    except Exception as e:
        log.error(f"❌ Title Update Failed: {str(e)}", exc_info=True)
        return {"error": str(e)}
