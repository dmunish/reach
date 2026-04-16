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

@tool
async def title(title: str, config: RunnableConfig):
    """Set a title for the chat session according to the user's prompt"""
    return "Title set."

@tool(response_format="content_and_artifact")
async def query(query: str, read: bool = False, config: RunnableConfig = None):
    """
Fetch data by executing a SQL query against the PostgreSQL database.
Returns the raw data from the Supabase client.

## Args:
- query: The SQL string to execute against the database.
- read: Boolean for if you want to see the database results. Set to false if you don't need to see the results OR you suspect the amount of data returned is large

## Instructions:
- Only write SELECT statements
- Structure data in a way that makes it easy to visualize and digest. E.g using aggregation, counts, etc. extensively
- Prefer alert_search_index table for fast queries as it is a denormalized view

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
|                    | category                 | CAP-based type(Geo, Met, Safety, etc.)                                                                               |
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
|                    | affected_places          | Array of all affected place names                                                                                    |
|                    | place_ids                | Array of all affected place UUIDs                                                                                    |
|                    | last_updated_at          | Time the index was last updated                                                                                      |

## Must-use SQL patterns
```sql
-- For "active/current alerts", use NOW() in both conditions
WHERE NOW() >= effective_from AND NOW() < effective_until

-- For historical analysis of a specific year (e.g., 2024):
WHERE EXTRACT(YEAR FROM effective_from) = 2024

-- ALWAYS use TO_CHAR() with FMMonth (no spaces) for clean labels from the timestamptz columns:
TO_CHAR(effective_from, 'FMMonth, YYYY') as period

-- For chronological sorting in trends:
ORDER BY effective_from ASC

-- ALWAYS use the recursive CTE pattern
-- This captures alerts for both parent regions and their child areas
WITH RECURSIVE place_tree AS (
    SELECT id FROM places WHERE name ILIKE '%Region Name%'
    UNION ALL
    SELECT p.id FROM places p JOIN place_tree pt ON p.parent_id = pt.id
)
SELECT * FROM alert_search_index 
WHERE place_ids && (SELECT array_agg(id) FROM place_tree);
```
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

## Args:
1.  option: A string containing a valid JavaScript object literal
2. data_transform: Optional. A dictionary to restructure tabular SQL data for complex charts.
	- For 'tree', 'treemap', 'sunburst': 
		{"type": "hierarchy", "id_key": "id_col", "parent_key": "parent_col", "name_key": "name_col"}
	-  For 'graph', 'sankey':
		{"type": "graph", "source_key": "from_col", "target_key": "to_col"}
	- For 'heatmap':
		{"type": "matrix", "x_key": "col_x", "y_key": "col_y", "v_key": "col_val"}

## Tool Requirements - CRITICAL:
1. You must not call this tool unless you have already called the `examples` tool in a previous step to learn the correct structure for your chosen chart type
2. ALways reference the `datasource` variable in your option object at the appropriate location like dataset.source or series.data (or others) to inject data
3. Always map data to the specific keys the chart type expects for chart types like Pie, Graph (and others) using `data: datasource.map(item => ({name:, value:}))` or `encode: { itemName:, value:}`
4. Always include a toolbox in the option object. saveAsImage is compulsary. dataView (read-only), dataZoom, restore, magicType, and brush if appropriate/requested. Change the order of the tools as you please. NO other tools in toolbox besides the ones mentioned

### Chart error prevention checklist:
- [ ] Data structure matches what the `examples` showed
- [ ] All required keys exist in your data (e.g., if example uses `name` and `value`, your data must have those)
- [ ] Data array is not empty
- [ ] Data field names are correctly mapped to variable names expected by chart

## Styling Rules:
The `examples` tool returns official ECharts examples, but they often use a boring blue/green color theme. You MUST use better colors.
1. Background: Always explicitly set `backgroundColor: 'transparent'`. Do not use solid colors (no '#000', no hex codes) regardless of what examples show. Unless the user asks for a specific color, you MUST use transparent
2. Overlapping/Rotation: You must prevent tilted text. Inside `xAxis.axisLabel` (and any other timeline or axis), ALWAYS set: `{ interval: 'auto', hideOverlap: true, rotate: 0 }`
3. Theme/Colors: The UI is already dark mode. Do not make the chart background dark. Don't set text color, as dark mode handles that. ALWAYS use a meaningful and modern/minimalist/harmonic color palette instead of the default blue coloring for charts For example, for alert severities, use yellow (minor), orange (moderate), red (severe), purple (extreme) to show the severity level through visual design
4. PADDING/POSITIONING: ALWAYS include padding around elements like title, legend, dataZoom, toolbox, and others so they don't overlap with each other and the chart. Position them appropriately to prevent overlapping (for example, positioning legend on the bottom)
5. RESPONSIVENESS: Achieve polished interactions with animationDuration and animationEasing

## Visual Design Rules:
- Use gradients where appropriate
- Add shadows for depth: `shadowColor: 'rgba(0,0,0,0.3)'`,  `shadowBlur: 10`
- Ensure text is readable: Minimum 12px font size, high contrast with background
- Make interactive: Enable tooltip with meaningful formatting, enable legend when showing multiple series
- Custom font: ALWAYS use the modern Josefin Sans font by setting `textStyle: {fontFamily: '"Josefin Sans", sans-serif'}` in the global scope (and any other place like legend, tooltip, etc.), unless the user asks for a different font
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
    - graphGL: High-performance network graph. Use instead of `graph` when you expect data volume (like number of nodes or edges) to be large.
    - heatmap: Matrix density visualization. Highly effective for temporal heatmaps (e.g., Day vs. Month) showing when disasters are most frequent.
    - line: Continuous time-series trends. The go-to for showing the historical trend of alert frequencies over days, months, or years.
    - line3D: 3D trajectories. Can be used for plotting paths over time, such as tracking a cyclone's coordinate bounds dynamically.
    - map: Choropleth/Geographical map. Essential for visualizing the geographic spread of alerts and highlighting specific affected regions.
    - matrix: Gridded comparison. Similar to heatmap; useful for multi-dimensional correlation (e.g., comparing alert severity versus urgency).
    - pie: Proportional composition. Best for showing the percentage breakdown of active alerts by category (e.g., 60% Met, 30% Geo).
    - radar: Multi-axis profiles. Useful for visualizing the "disaster risk profile" of a specific region based on historical frequencies.
    - scatter: 2D dot plots. Great for correlating two variables, like plotting alert duration against severity, or mapping geographic centroids.
    - scatter3D: 3D bubble plots. Useful for plotting three variables simultaneously, like longitude, latitude, and duration or severity.
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