import json
import os
from typing import Any, Optional, Dict, List

from supabase import create_async_client
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from utils import load_env
from agents.transforms import transform_to_graph, transform_to_matrix, transform_to_tree

load_env()

async def get_supabase(config: RunnableConfig):
    jwt = config["configurable"]["jwt"]
    client = await create_async_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    await client.auth.set_session(access_token=jwt, refresh_token="")
    return client

@tool(response_format="content_and_artifact")
async def query(query: str, read: bool = False, config: RunnableConfig = None):
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns the raw data from the Supabase client.
    The schema of REACH is based on the Common Alerting Protocol standard, with some modifications.

    Args:
        query: The SQL string to execute against the database.
        read: Boolean for if you want to see the database results. Set to false so large amounts of data is only available to the chart tool for visualization. Prefer to set to false if you suspect amount of data will be large.

    # Instructions:
    - Only write SELECT statements.
    - Provide a single continuous string, no need for newlines.
    - Structure data in a way that makes it easy to visualize and digest. E.g using aggregation, counts, and others a lot.
    - If doing a trend analysis, always sort data chronologically.
    - Use TO_CHAR() to present dates in a more human-readable format when constructing charts. For example: `TO_CHAR(effective_from, 'FMMonth, YYYY')`. Use `FMMonth` instead of `Month` to prevent space around months with shorter names.
    - Prefer the denormalized alert_search_index table for fast queries as it is a dnormalized view.
    - Unless date ranges are specified, assume user's are asking about 'active' alerts and use `WHERE NOW() >= effective_from AND NOW() < effective_until`.
    - You have the following schema available, only use the following columns:
    | Table                | Column                     | Description                                    |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | documents            | id                         | UUID primary key                               |
    |                      | source                     | Name of the originating data source            |
    |                      | posted_date                | Date the document was published                |
    |                      | title                      | Document title                                 |
    |                      | url                        | URL of the source document                     |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | alerts               | id                         | UUID primary key                               |
    |                      | document_id                | FK → documents.id                              |
    |                      | category                   | CAP-based category (Geo, Met, Safety, etc.)    |
    |                      | event                      | Short event label, e.g. Flash Flood            |
    |                      | urgency                    | Immediate / Expected / Future / Past / Unknown |
    |                      | severity                   | Extreme / Severe / Moderate / Minor / Unknown  |
    |                      | description                | Full narrative description of the alert        |
    |                      | instruction                | Recommended action for affected people         |
    |                      | effective_from             | Start of the alert validity window             |
    |                      | effective_until            | End of the alert validity window               |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | alert_areas          | id                         | UUID primary key                               |
    |                      | alert_id                   | FK → alerts.id                                 |
    |                      | place_id                   | FK → places.id                                 |
    |                      | specific_effective_from    | Area-level override for effective start        |
    |                      | specific_effective_until   | Area-level override for effective end          |
    |                      | specific_urgency           | Area-level urgency override                    |
    |                      | specific_severity          | Area-level severity override                   |
    |                      | specific_instruction       | Area-level protective instruction override     |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | places               | id                         | UUID primary key                               |
    |                      | name                       | Place name                                     |
    |                      | parent_id                  | Self-referencing FK to parent place            |
    |                      | parent_name                | Denormalised parent place name                 |
    |                      | hierarchy_level            | Depth in the geographic hierarchy              |
    |                      |                            | (0: country, 3: tehsil)                        |
    |                      | polygon                    | PostGIS geometry of the place boundary         |
    | -------------------- | -------------------------- | ---------------------------------------------- |
    | alert_search_index   | alert_id                   | UUID primary key, FK → alerts.id               |
    |                      | centroid                   | Geometry, center point of all affected areas   |
    |                      | bbox                       | Geometry, bounding box of all affected areas   |
    |                      | unioned_polygon            | Geometry,combined polygon of all affected areas|
    |                      | search_text                | Text for full-text search (event + desc + etc.)|
    |                      | category                   | CAP-based category (Geo, Met, Safety, etc.)    |
    |                      | severity                   | Extreme / Severe / Moderate / Minor / Unknown  |
    |                      | urgency                    | Immediate / Expected / Future / Past / Unknown |
    |                      | event                      | Short event label, e.g. Flash Flood            |
    |                      | description                | Full narrative description of the alert        |
    |                      | instruction                | Recommended action for affected people         |
    |                      | source                     | Name of the originating data source            |
    |                      | url                        | URL of the source document                     |
    |                      | posted_date                | Date the document was published                |
    |                      | effective_from             | Start of the alert validity window             |
    |                      | effective_until            | End of the alert validity window               |
    |                      | affected_places            | Array of all affected place names              |
    |                      | place_ids                  | Array of all affected place UUIDs              |
    |                      | last_updated_at            | Time the index was last updated                |

    - Severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'.
    - Urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'.
    - Category values: 'Geo','Met','Safety','Security','Rescue','Fire', 'Health','Env','Transport','Infra','CBRNE','Other'.
    """
    try:
        client = await get_supabase(config)
        result = await client.rpc("execute_readonly_sql", {"query_text": query}).execute()

        # Store raw data in artifact because its invisible to LLM and doesn't flood context
        artifact = result.data or []

        # Get a summary for the LLM
        num_rows = len(artifact)
        column_names = list(artifact[0].keys())
        content = f"""
                ## Query Execution Summary
                * **Total Rows:** {num_rows}
                * **Columns:** {', '.join(f'`{col}`' for col in column_names)}

                ### Data Preview (First 2 rows):
                {artifact[:2]}
                """
        if read:
            content = artifact
        
        return content, artifact
    
    except Exception as e:
        return f"Error: {str(e)}", None

@tool(response_format="content_and_artifact")
def chart(option: str, data_transform: Optional[Dict] = None, config: RunnableConfig = None) -> Any:
    """
    Publish a chart by providing a JavaScript ECharts option object. 
    Never hardcode data, let it be injected through the `datasource` variable as described below.
    Always include a toolbox in the option object. saveAsImage is compulsary. dataView, dataZoom, restore, magicType, and brush if appropriate/requested. Change the order of the tools as you please.

    CRITICAL DO-NOT-VIOLATE STYLING RULES:
    1. BACKGROUND: ALWAYS explicitly set `backgroundColor: 'transparent'`. DO NOT use solid colors (no '#000', no hex codes) regardless of what examples show.
    2. OVERLAPPING & ROTATION: You MUST prevent tilted text. Inside `xAxis.axisLabel` (and any other timeline or axis), ALWAYS set: `{ interval: 'auto', hideOverlap: true, rotate: 0 }`.
    3. THEME/COLORS: The UI is already dark mode. Do not make the chart background dark. Use bright/white, highly legible colors for title, legend, and all other text text. Use a meaningful and modern/minimalist color palette all around.
    4. PADDING/POSITIONING: ALWAYS include padding around elements like title, legend, dataZoom, toolbox, and others so they don't overlap with each other and the chart. Position them appropriately to prevent overlapping.
    5. RESPONSIVENESS: Achieve polished interactions with animationDuration and animationEasing.
    6. TYPOGRAPHY: Use custom, carefully picked fonts for modern feel.
    
    Args:
        option: A string containing a valid JavaScript object literal.
                Use the variable `datasource` directly to assign dataset.source or series.data.
                
        data_transform: Optional. A dictionary to restructure tabular SQL data for complex charts.
                        - For 'tree', 'treemap', 'sunburst': 
                          {"type": "hierarchy", "id_key": "id_col", "parent_key": "parent_col", "name_key": "name_col"}
                        - For 'graph', 'sankey':
                          {"type": "graph", "source_key": "from_col", "target_key": "to_col"}
                        - For 'heatmap':
                          {"type": "matrix", "x_key": "col_x", "y_key": "col_y", "v_key": "col_val"}
    
    Example:
    {
      "option": "{ series: [{ type: 'graph', data: datasource.nodes, links: datasource.links }] }",
      "data_transform": {
          "type": "graph",
          "source_key": "sender",
          "target_key": "receiver"
      }
    }
    """
    try:
        # Retrieve Data
        data = config.get("configurable", {}).get("dataset")
        if not data:
            return "Error: No data artifact found. Please run `query` first.", None

        # Apply Transformation Logic
        if data_transform:
            transform_type = data_transform.get("type")
            if transform_type == "hierarchy":
                data = transform_to_tree(data, data_transform)
            elif transform_type == "graph":
                data = transform_to_graph(data, data_transform)
            elif transform_type == "matrix":
                data = transform_to_matrix(data, data_transform)
        
        # Inject Data
        data_json = json.dumps(data, default=str)
        clean_config = option[option.find("{") : option.rfind("}") + 1].strip()

        # Return Result
        content = "Chart generated with injected data."
        artifact =  {
            "action": "render_chart",
            "data": {
                "config": clean_config,
                "datasource": data_json
            }
        }

        return content, artifact

    except Exception as e:
        import traceback
        return f"Chart generation failed: {str(e)}\n{traceback.format_exc()}", None

    
@tool(response_format="content_and_artifact")
async def map(places: List[str], config: RunnableConfig) -> dict:
    """
    Control the Mapbox camera and highlight a geometry.
    
    Args:
    place_names: List of string containing names of places to focus on and highlight.

    Call in PARALLEL with 'query' tool to save latency — emit both in one tool_calls array.
    """    
    try:
        client = await get_supabase(config)        
        result = await client.rpc("get_places", {"place_names": places}).execute()
        
        if not result.data:
            return "Error: No data found.", None
        
        row = result.data[0]
        content = f"Found data for {', '.join(places)}."
        artifact = {
            "action": "map_update",
            "data":{
                "polygon": row["unioned_polygon"],
                "centroid": row["centroid"],
                "bbox": row["bbox"]
            }
        }
        return content, artifact
        
    except Exception as e:
        return f"Error: {str(e)}", None

@tool
async def examples(type: str, config: RunnableConfig) -> dict:
    """
    Get official ECharts examples for a specific chart type to understand how to format the 'option' object.

    Args: 
        type: The chart type to pull examples of. Must be one of the official types from below.
    
    Returns: 
        A set of official examples, each with:
        - A dataset/data generation function(s) to show you how the data was structured.
        - The option object settings all the styles and mapping the data.

    The following chart types are available, along with a description/sugestion for each:
        - bar: Categorical bars for comparison. Use for alert counts by category, severity, or province.
        - bar3D: 3D bars on a grid. Use for severity density across geographic areas.
        - boxplot: Statistical distribution summary. Use for analyzing spread of alert durations.
        - candlestick: High/low/open/close values. Use for visualizing daily alert activity windows.
        - chord: Relationship flows between entities. Use for correlations between events and places.
        - flowGL: WebGL flow fields. Use for meteorological wind or current visualizations.
        - graph: Network of nodes and links. Use for place hierarchies or disaster clusters.
        - graphGL: High-performance network graph. Use for massive alert relationship datasets.
        - heatmap: Color-coded matrix values. Use for temporal alert patterns or disaster hotspots.
        - line: Trend lines over time. Use for time-series analysis of alert frequency.
        - line3D: Lines in 3D space. Use for tracking disaster trajectories like cyclone paths.
        - map: Geographic visualization. Use for rendering alert polygons and affected areas.
        - matrix: Multi-variable comparison grid. Use for correlating categories across provinces.
        - pie: Circular proportional slices. Use for percentage breakdown of alert categories.
        - radar: Multi-variable web chart. Use for comparing regional disaster risk profiles.
        - scatter: Dots for two variables. Use for plotting geographic spread of alert centroids.
        - scatter3D: Dots in 3D space. Use for plotting location against severity or urgency.
        - sunburst: Hierarchical rings. Use for drilling down alert counts from Country to District.
        - tree: Hierarchical node structure. Use for visualizing place parent-child relationships.
        - treemap: Nested proportional rectangles. Use for alert volume by region hierarchy.
    """
    try:
        client = await get_supabase(config)
        result = await client.table("echarts").select("type, title, data, option").ilike("type", f"%{type}%").execute()

        all_examples = []
        for example in result.data: # result.data is typically a list of dicts
            all_examples.append(
                f"## Title: {example.get('title')}\n" +
                f"### Data: \n```javascript\n{example.get('data')}```\n" +
                f"### Option: \n```javascript\n{example.get('option')}```\n"
                )
        all_examples_str = ("\n\n").join(all_examples)
        content = f"# Official examples for {result.data[0].get('type').title()} chart:\n\n" + all_examples_str  
        + """\n\n # REMINDER:\n ALWAYS FOLLOW THE STYLING GUIDELINES IN THE `chart` TOOL DESCRIPTION REGARDLESS OF WHAT THE EXAMPLES USE. 
        USE BRIGHT COLORS FOR ALL TEXT, AND KEEP BACKGROUND TRANSPARENT."""
        return content
    except Exception as e:
        return f"Error: {str(e)}"