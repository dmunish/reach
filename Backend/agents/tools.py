from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.runnables import RunnableConfig
from supabase import create_client
from typing import Annotated, List
import json
import os
from agents.state import State


def get_supabase(config: RunnableConfig):
    jwt = config["configurable"]["jwt"]
    return create_client(os.environ.get("SUPABASE_URL"), jwt)

@tool
def query(query: str) -> List[dict]:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns the raw data from the Supabase client.

    The schema of REACH is based on the Common Alerting Protocol standard, with some modifications.
    """
    try:
        client = get_supabase()
        result = client.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        return {"data": rows}
    
    except Exception as e:
        return {"error": str(e)}

@tool
def chart(echarts_options: str, state: Annotated[State, InjectedState]) -> dict:
    """
    Publish a chart by combining your ECharts config with the query data.
    You need to provide a complete ECharts option object as a JSON string.
    You will utlize the dataset property for clean seperation between data and presentation.
    Define mappings using series[i].encode, reference column names exactly as they appear in your SQL query.
    Do NOT include a 'dataset' key — it is built automatically.
    Do NOT include series[i].data arrays - data is injected automatically.
    """    
    try:
        config = json.loads(echarts_options)
    except json.JSONDecodeError as e:
        return {"error": str(e)}

    data = state.get("db_results")
    if not data:
        return {"error": "No query results available. Call 'query' first."}

    # Inject data into config as a list of dicts
    config["dataset"] = {"source": data}

    result = {
        "action": "render_chart",
        "data": {
            "config": config,
        }
    }
    
    return result
    
@tool
def map(places: List[str]) -> dict:
    """
    Control the Mapbox camera and highlight a geometry.
    
    YOU provide:
    place_names: List of places to focus on and highlight.

    Returns a dict with keys:
        - unioned_polygon: dict  (GeoJSON geometry, for highlighting)
        - centroid: dict         (GeoJSON geometry, to move camera)
        - bbox: dict             (GeoJSON geometry, to set zoom)

    Call in PARALLEL with 'query' to save latency — emit both in one tool_calls array.
    """    
    try:
        client = get_supabase()        
        result = client.rpc("get_places", {"place_names": places}).execute()
        
        if not result.data:
            return {"error": "No data found."}
        
        row = result.data[0]
        return {
            "action": "map_update",
            "data":{
                "polygon": row["unioned_polygon"],
                "centroid": row["centroid"],
                "bbox": row["bbox"]
            }
        }
    except Exception as e:
        return {"error": str(e)}