from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from supabase import create_async_client
from typing import Any, Optional, Dict, List
import json
import os
from utils import load_env
from transforms import transform_to_graph, transform_to_matrix, transform_to_tree

load_env()

async def get_supabase(config: RunnableConfig):
    jwt = config["configurable"]["jwt"]
    client = await create_async_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    await client.auth.set_session(access_token=jwt, refresh_token="")
    return client

@tool
async def query(query: str, config: RunnableConfig) -> List[dict]:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns the raw data from the Supabase client.
    The schema of REACH is based on the Common Alerting Protocol standard, with some modifications.

    Args:
        query: The SQL string to execute against the database

    # Instructions:
    - Only write SELECT statements.
    - Provide a single continuous string, no need for newlines.
    - Structure data in a way that makes it easy to visualize and digest. E.g using aggregation, counts, and others a lot.
    - Use TO_CHAR() to present dates in a more human-readable format when constructing charts. For example: TO_CHAR(effective_from, 'FMMonth, YYYY').
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

    - Severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'.
    - Urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'.
    - Category values: 'Geo','Met','Safety','Security','Rescue','Fire', 'Health','Env','Transport','Infra','CBRNE','Other'.
    - alert_search_index is a denormalized and performant view.
    """
    try:
        client = await get_supabase(config)
        result = await client.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        return {"data": rows}
    
    except Exception as e:
        return {"error": str(e)}

@tool
def chart(option: str, data_transform: Optional[Dict], config: RunnableConfig) -> Any:
    """
    Publish a chart by providing a JavaScript ECharts option object.
    
    Args:
        option: A string containing a valid JavaScript object literal.
                Use the placeholder 'DATA_SOURCE' for the dataset.source or series.data value.
                
        data_transform: Optional. A dictionary to restructure tabular SQL data for complex charts.
                        - For 'tree', 'treemap', 'sunburst': 
                          {"type": "hierarchy", "id_key": "id_col", "parent_key": "parent_col", "name_key": "name_col"}
                        - For 'graph', 'sankey':
                          {"type": "graph", "source_key": "from_col", "target_key": "to_col"}
                        - For 'heatmap':
                          {"type": "matrix", "x_key": "col_x", "y_key": "col_y", "v_key": "col_val"}
    
    Example:
        option={ series: [{ type: 'graph', data: DATA_SOURCE.nodes, links: DATA_SOURCE.links }] },
        data_transform={
            "type": "graph",
            "source_key": "sender",
            "target_key": "receiver"
        }
)
    """
    try:
        # Retrieve Data
        data = config.get("configurable", {}).get("db_results")
        if not data:
            return {"error": "No query results available. Call 'query' tool first."}

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
        clean_config = clean_config.replace("DATA_SOURCE", data_json)

        # Return Result
        return {
            "action": "render_chart",
            "data": {
                "config": clean_config,
            }
        }

    except Exception as e:
        import traceback
        return {"error": f"Chart generation failed: {str(e)}\n{traceback.format_exc()}"}

    
@tool
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

    The following chart types are available (each `usage` guide is merely a suggestion):
    - bar
        - Description: A chart that presents categorical data with rectangular bars where heights are proportional to the values they represent.
        - Usage: Ideal for comparing discrete counts or aggregates. Use this to visualize the number of alerts per category (Met, Geo, Safety), the count of alerts per severity level, or the volume of alerts issued per province.

    - bar3D
        - Description: A three-dimensional bar chart usually plotted on a grid or geographic coordinate system.
        - Usage: Useful for visualizing density or magnitude across two dimensions. Use this to show the distribution of alert severity (height) across a geographic grid (longitude/latitude) or a matrix of Category vs. Urgency.

    - boxplot
        - Description: A statistical chart displaying the distribution of data based on a five-number summary (minimum, Q1, median, Q3, maximum).
        - Usage: Useful for statistical analysis of alert durations. Use this to visualize the spread and skewness of alert validity periods (`effective_from` to `effective_until`) across different event types or regions.

    - candlestick
        - Description: A financial-style chart typically used to show high, low, open, and closing values.
        - Usage: While specialized for financial data, it can be adapted to visualize the lifecycle of alerts for a specific day: showing the first alert time (open), last alert time (close), and the peak activity window (high/low) for a disaster event.

    - chord
        - Description: A diagram visualizing relationships and flows between entities using arcs and ribbons.
        - Usage: Excellent for visualizing correlations or flows. Use this to show the relationship between `event` types and `places` (e.g., how floods in one province often correlate with alerts in neighboring provinces), or the flow of severity classifications between sources.

    - flowGL
        - Description: A WebGL-based visualization for large-scale flow fields using particles or arrows.
        - Usage: Highly effective for meteorological (`Met` category) data visualization. Use this to represent wind speed/direction or water current dynamics if you have access to vector field data related to cyclones or monsoons.

    - graph
        - Description: A network diagram displaying nodes (entities) and links (connections) to represent relationships.
        - Usage: Ideal for visualizing relational data. Use this to map the hierarchy of `places` (parent/child relationships) or to show connections between `events` and affected `places` to identify disaster clusters.

    - graphGL
        - Description: A WebGL-accelerated graph chart optimized for massive datasets.
        - Usage: Necessary when visualizing large-scale networks. Use this if the user queries a large subset of the `alert_search_index` to visualize thousands of connections between alerts and places without performance lag.

    - heatmap
        - Description: A graphical representation of data where values in a matrix are represented as colors.
        - Usage: Perfect for identifying temporal patterns or hotspots. Use this to visualize the frequency of alerts by day of the week vs. hour of the day, or a calendar heatmap of disaster intensity over the year.

    - line
        - Description: A chart that connects a series of data points with straight line segments to show trends over time.
        - Usage: The standard for time-series analysis. Use this to plot the trend of alert counts over days, weeks, or months, helping users identify if disaster frequency is increasing or decreasing.

    - line3D
        - Description: A line chart plotted in a 3D coordinate system.
        - Usage: Useful for visualizing trajectories in 3D space. Use this to track the path of a moving disaster event (like a cyclone track) where the Z-axis might represent intensity or time.

    - map
        - Description: A geographic visualization tool that renders areas or points on a map background using GeoJSON or coordinate systems.
        - Usage: Crucial for REACH. Use this to visualize `polygon` data from the `places` table or centroids from `alert_search_index`. It allows users to see exactly which districts or provinces are affected by specific alerts.

    - matrix
        - Description: (Note: Use `scatter` with multiple coordinate systems or `heatmap`). A format for comparing multiple variables against each other simultaneously.
        - Usage: Useful for multi-variate analysis. Use this to compare correlations between different disaster categories across multiple provinces simultaneously to identify which regions are prone to which types of disasters.

    - pie
        - Description: A circular chart divided into slices to illustrate numerical proportion.
        - Usage: Good for high-level summaries. Use this to show the percentage breakdown of alert categories (e.g., "70% Met, 20% Geo, 10% Safety") or the proportion of Urgency levels for a specific query.

    - radar
        - Description: A chart displaying multivariate data as a two-dimensional chart of three or more quantitative variables starting from the same point.
        - Usage: Useful for profiling. Use this to compare the "disaster profile" of different provinces—comparing their frequency of Floods, Earthquakes, and Heatwaves on a single axis to see which region is most diverse in terms of risk.

    - scatter
        - Description: A chart using dots to represent values for two different variables.
        - Usage: Useful for identifying correlations or distribution. Use this to plot `longitude` vs `latitude` of alert centroids to visualize the geographic spread of disaster points without full polygons.

    - scatter3D
        - Description: A three-dimensional scatter plot for visualizing data points in an X, Y, Z coordinate system.
        - Usage: Useful for adding a third dimension to geographic data. Use this to plot alert locations (Lat/Lon) where the Z-axis represents `severity` score or `urgency`, helping identify high-risk points in 3D space.

    - sunburst
        - Description: a hierarchical pie chart where levels of the hierarchy are represented by rings radiating outward.
        - Usage: Ideal for the `places` hierarchy. Use this to visualize alerts starting from the Country level, drilling down to Provinces, and then Districts/Tehsils, showing the count of alerts at each level of the geographic tree.

    - tree
        - Description: A diagram displaying hierarchical data in a tree structure (root to leaves).
        - Usage: Use this to explicitly visualize the parent-child relationships in the `places` table (e.g., Pakistan -> Punjab -> Lahore) or to show the categorization taxonomy of disaster events.

    - treemap
        - Description: A visualization displaying hierarchical data as a set of nested rectangles, where size and color represent values.
        - Usage: Highly effective for showing hierarchical proportions. Use this to display the alert volume by region, where the rectangle size represents the number of alerts, allowing users to quickly identify which administrative divisions have the largest disaster footprint.
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
        return {"data": f"# Official examples for {result.data[0].get('type').title()} chart:\n\n" + all_examples_str}
    except Exception as e:
        return {"error": str(e)}