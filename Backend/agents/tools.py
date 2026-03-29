from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from supabase import create_async_client
from typing import List, Any
import json
import os
from utils import load_env

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
    """
    try:
        client = await get_supabase(config)
        result = await client.rpc("execute_readonly_sql", {"query_text": query}).execute()
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
async def map(places: List[str], config: RunnableConfig) -> dict:
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
    Each example contains:
    - A dataset/data generation function(s) to show you how the data was structured.
    - The option object settings all the styles and mapping the data.

    The following chart types are available:
    Here are the reworded descriptions tailored for the REACH agent, focusing on disaster data analysis and visualization design for the provided schema.

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
                f"# Title: {example.get('title')}\n" +
                f"## Data: \n```javascript\n{example.get('data')}```\n" +
                f"## Option: \n```javascript\n{example.get('option')}```\n"
                )
        all_examples_str = ("\n\n").join(all_examples)
        return {"data": f"# Official examples for {result.get('type').title()} chart:\n\n" + all_examples_str}
    except Exception as e:
        return {"error": str(e)}