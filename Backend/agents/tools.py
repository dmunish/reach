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
Fetch data by executing a SQL query against the PostgreSQL database.
Returns the raw data from the Supabase client.

## Args:
- query: The SQL string to execute against the database.
- read: Boolean for if you want to see the database results. Default is False, set to True if you want to see results of the query

## Instructions:
- Provide it all in a single line, no newlines
- Only write SELECT statements
- Structure data in a way that makes it easy to visualize and digest. E.g using aggregation, counts, etc. extensively
- ALWAYS prefer to use alert_search_index table as it is a denormalized view and is very fast

## Schema
You have the following schema available, only use the following columns:

| Table              | Column                   | Description                                                                                                          |
| ------------------ | ------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| documents          | id                       | UUID primary key                                                                                                     |
|                    | source                   | Name of the originating data source                                                                                  |
|                    | posted_date              | Date the document was published                                                                                      |
|                    | title                    | Document title                                                                                                       |
|                    | url                      | URL of the source document                                                                                           |
| alerts             | id                       | UUID primary key                                                                                                     |
|                    | document_id              | FK → documents.id                                                                                                    |
|                    | category                 | CAP-based type ('Geo','Met','Safety','Security','Rescue','Fire', 'Health','Env','Transport','Infra','CBRNE','Other') |
|                    | event                    | Short title for the alert                                                                                            |
|                    | urgency                  | Immediate / Expected / Future / Past / Unknown                                                                       |
|                    | severity                 | Extreme / Severe / Moderate / Minor / Unknown                                                                        |
|                    | description              | Full narrative description of the alert                                                                              |
|                    | instruction              | Recommended action for affected people                                                                               |
|                    | effective_from           | Start of the alert validity window (timestamptz)                                                                     |
|                    | effective_until          | End of the alert validity window (timestamptz)                                                                       |
| alert_areas        | id                       | UUID primary key                                                                                                     |
|                    | alert_id                 | FK → alerts.id                                                                                                       |
|                    | place_id                 | FK → places.id                                                                                                       |
|                    | specific_effective_from  | Area-level override for effective start (timestamptz)                                                                |
|                    | specific_effective_until | Area-level override for effective end (timestamptz)                                                                  |
|                    | specific_urgency         | Area-level urgency override                                                                                          |
|                    | specific_severity        | Area-level severity override                                                                                         |
|                    | specific_instruction     | Area-level protective instruction override                                                                           |
| places             | id                       | UUID primary key                                                                                                     |
|                    | name                     | Place name                                                                                                           |
|                    | parent_id                | Self-referencing FK to parent place                                                                                  |
|                    | parent_name              | Denormalised parent place name                                                                                       |
|                    | hierarchy_level          | Level in the geographic hierarchy (0: country, 1: province, 2: district, 3: tehsil)                                  |
|                    | polygon                  | PostGIS geometry of the place boundary                                                                               |
| alert_search_index | alert_id                 | UUID primary key, FK → alerts.id                                                                                     |
|                    | centroid                 | Geometry, center point of all affected areas                                                                         |
|                    | bbox                     | Geometry, bounding box of all affected areas                                                                         |
|                    | unioned_polygon          | Geometry, combined polygon of all affected areas                                                                     |
|                    | search_text              | Text for full-text search (event + desc + etc.)                                                                      |
|                    | category                 | CAP-based type (Geo, Met, Safety, etc.)                                                                               |
|                    | severity                 | Extreme / Severe / Moderate / Minor / Unknown                                                                        |
|                    | urgency                  | Immediate / Expected / Future / Past / Unknown                                                                       |
|                    | event                    | Short alert title, e.g. Flash Flood                                                                                  |
|                    | description              | Full narrative description of the alert                                                                              |
|                    | instruction              | Recommended action for affected people                                                                               |
|                    | source                   | Name of the originating data source                                                                                  |
|                    | url                      | URL of the source document                                                                                           |
|                    | posted_date              | Date the document was published                                                                                      |
|                    | effective_from           | Start of the alert validity window (timestamptz)                                                                     |
|                    | effective_until          | End of the alert validity window (timestamptz)                                                                       |
|                    | last_updated_at          | Time the index was last updated                                                                                      |
    """
    try:
        client = await get_supabase(config)
        result = await client.rpc("execute_readonly_sql", {"query_text": query}).execute()

        # Convert raw data to list-of-lists from list-of-dicts
        data = result.data or []
        if data:
            columns = list(data[0].keys())
            artifact = [columns] + [list(row.values() for row in data)]
        else:
            artifact = []

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
def chart(option: str, new_data: bool, data_transform: Optional[Dict] = None, config: RunnableConfig = None) -> Any:
    """
Publish a chart by providing a JavaScript ECharts option object.

## Args:
1. option: A string containing a valid JavaScript object literal
2. new_data: Boolean for whether you want to attach data from the last query - set to false if only restyling chart and reusing older data
3. data_transform: Optional. A dictionary to restructure tabular SQL data for complex charts
	- For 'tree', 'treemap', 'sunburst': 
		{"type": "hierarchy", "id_key": "id_col", "parent_key": "parent_col", "name_key": "name_col"}
	-  For 'graph', 'sankey':
		{"type": "graph", "source_key": "from_col", "target_key": "to_col"}
	- For 'heatmap':
		{"type": "matrix", "x_key": "col_x", "y_key": "col_y", "v_key": "col_val"}

## Tool Requirements:
1. You must not call this tool unless you have already called the `examples` tool in a previous step to learn the correct structure for your chosen chart type
2. ALways reference the `datasource` variable in your option object at the appropriate location like dataset.source or series.data (or others) to inject data. Do not hard code data values
3. Always map data to the specific keys the chart type expects for chart types like Pie, Graph (and others) using `data: datasource.map(item => ({name:, value:}))` or `encode: { itemName:, value:}`
4. Always include a toolbox in the option object. saveAsImage is compulsary. dataView (read-only), dataZoom, restore, magicType if appropriate/requested. Change the order of the tools as you please. NO other tools in toolbox besides the ones mentioned

## Visual Design Rules:
- Use a modern/dark-theme optimized visual style
- Use pleasing, neon-style gradients where appropriate
- Add shadows for depth
- Ensure text is readable
- Always set background color as `'transparent'`
- Use the custom font 'Josefin Sans' anywhere there is text
- Prevent rotation of text on axes with `rotate: 0`
- Keep colors and styling fresh - use new colors with new charts
- Use padding to ensure there isn't too little space between chart elements or too much space with the chart border
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
                "datasource": data_json if new_data else None
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
- place_names: List of string containing names of places to focus on and highlight.

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
Get official ECharts examples for a specific chart type to understand how to structure the 'option' object.
Mandatory prerequisite tool for charting. You MUST call this before calling the `chart` tool.

Args: 
- type: The chart type to pull examples of. Must be one of the official types from below.

The following chart types are available, along with a description/sugestion for each:
    - bar: Categorical bars. Best for comparing alert volume across different categories (Geo, Met), severity levels, or provinces.
    - bar3D: 3D bar visualization. Great for spatio-temporal density, like showing alert counts by province (X) over different months (Y).
    - boxplot: Statistical distribution. Excellent for visualizing the spread, median, and outliers of alert turnaround times or durations.
    - candlestick: Temporal ranges. Useful for visualizing the start, peak, and end dates of prolonged disaster events over a timeline.
    - chord: Relationship flows. Perfect for showing complex correlations, like which disaster categories frequently coincide in specific regions.
    - flowGL: WebGL vector fields. Typically used for meteorological wind patterns or ocean currents if raw spatial vector data is available.
    - graph: Network node-link structures. Ideal for visualizing chains of cascading disaster events, or relationships between affected regions.
    - heatmap: Matrix density visualization. Highly effective for temporal heatmaps (e.g., Day vs. Month) showing when disasters are most frequent.
    - line: Continuous time-series trends. The go-to for showing the historical trend of alert frequencies over days, months, or years.
    - line3D: 3D trajectories. Can be used for plotting paths over time, such as tracking a cyclone's coordinate bounds dynamically.
    - map: Choropleth/Geographical map. Essential for visualizing the geographic spread of alerts and highlighting specific affected regions.
    - matrix: Gridded comparison. Similar to heatmap; useful for multi-dimensional correlation (e.g., comparing alert severity versus urgency).
    - pie: Proportional composition. Best for showing the percentage breakdown of active alerts by category (e.g., 60% Met, 30% Geo).
    - radar: Multi-axis profiles. Useful for visualizing the "disaster risk profile" of a specific region based on historical frequencies.
    - scatter: Dot plots. Great for correlating two variables, like plotting alert duration against severity, or mapping geographic centroids.
    - sunburst: Radial hierarchical data. Excellent for drilling down into nested data: e.g., Total Alerts -> Category -> Severity -> Region.
    - tree: Branching hierarchy. Ideal for clearly displaying the geographic administrative parent-child hierarchy (Country -> Province -> District).
    - treemap: Nested rectangles. Highly effective for showing the total volume of alerts distributed across geographic regions or category hierarchies.
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
        content = f"# Official examples for {result.data[0].get('type').title()} chart:\n\n" + all_examples_str + "\n\n # REMINDER:\n ALWAYS FOLLOW THE STYLING GUIDELINES IN THE `chart` TOOL DESCRIPTION REGARDLESS OF WHAT THE EXAMPLES USE."
        return content
    except Exception as e:
        return f"Error: {str(e)}"