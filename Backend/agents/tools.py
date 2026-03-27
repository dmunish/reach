from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from supabase import create_client
from typing import List, Any
import json
import os
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
def chart(echart_options: str, config: RunnableConfig) -> Any:
    """
    Publish a chart by providing a JavaScript ECharts option object.
    This method allows for advanced features like JS functions (formatters, etc.).

    Args:
        echart_options: A string containing a valid JavaScript object literal (NOT just JSON).
                 - Use the placeholder 'DATA_SOURCE' for the dataset.source value.
                 - Use series[i].encode to map SQL column names to axes.
                 - You can include 'formatter' functions for tooltips or labels.

    Example:
        echart_options = {
            title: { text: 'Alerts per Region' },
            tooltip: { trigger: 'axis' },
            dataset: { source: DATA_SOURCE },
            xAxis: { type: 'category' },
            yAxis: { type: 'value' },
            series: [{ 
                type: 'bar', 
                encode: { x: 'region', y: 'count' },
                label: { show: true, formatter: (params) => params.value.count + ' alerts' }
            }]
        }
    """ 
    try:
        data = config.get("configurable", {}).get("db_results")
        if not data:
            return {"error": "No query results available. Call 'query' tool first to fetch data."}
        
        clean_config = echart_options[echart_options.find("{") : echart_options.rfind("}") + 1].strip()
        clean_config = clean_config.replace("DATA_SOURCE", json.dumps(data, default = str))
  
        result = {
            "action": "render_chart",
            "data": {
                "config": clean_config,
            }
        }
        return result
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Chart tool error:\n{error_details}")
        return {"error": f"Chart generation failed: {str(e)}\n\nDetails:\n{error_details}"}

    
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