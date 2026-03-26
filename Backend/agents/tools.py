from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.runnables import RunnableConfig
from supabase import create_client
from typing import Annotated, List
import json
import os
from agents.state import State
from utils import load_env

load_env()

def get_supabase(config: RunnableConfig):
    jwt = config["configurable"]["jwt"]
    client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    client.auth.set_session(access_token=jwt, refresh_token="")
    return client

@tool
def query(query: str, config: RunnableConfig) -> List[dict]:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns the raw data from the Supabase client.

    The schema of REACH is based on the Common Alerting Protocol standard, with some modifications.
    """
    try:
        client = get_supabase(config)
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

    # Strip markdown
    echarts_options = echarts_options[echarts_options.find("{") : echarts_options.rfind("}") + 1]

    try:
        config = json.loads(echarts_options)

        data = state.get("db_results")
        if not data:
            return {"error": "No query results available. Call 'query' first."}
        
        if "dataset" in config:
            del config["dataset"]
        for series in config.get("series", []):
            if "data" in series:
                del series["data"]

        # Inject data into config as a list of dicts
        echarts_options["dataset"] = {"source": data}

        result = {
            "action": "render_chart",
            "data": {
                "config": echarts_options,
            }
        }
        return result
    
    except json.JSONDecodeError as e:
        return {"error": f"JSON Decode error: {str(e)}"}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": str(e)}
    
@tool
def map(places: List[str], config: RunnableConfig) -> dict:
    """
    Control the Mapbox camera and highlight a geometry.
    
    YOU provide:
    place_names: List of string containing names of places to focus on and highlight.

    Returns a dict with keys:
        - unioned_polygon: dict  (GeoJSON geometry, for highlighting)
        - centroid: dict         (GeoJSON geometry, to move camera)
        - bbox: dict             (GeoJSON geometry, to set zoom)

    Call in PARALLEL with 'query' tool to save latency — emit both in one tool_calls array.
    """    
    try:
        client = get_supabase(config)        
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