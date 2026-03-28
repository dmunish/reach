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

    The following chart types are available:
        bar
        * What it is: A chart that presents categorical data with rectangular bars with heights or lengths proportional to the values they represent.
        * What it’s good for: Comparing discrete quantities across different categories, tracking changes over time (when few time points), or visualizing ranking.

        bar3D
        * What it is: A three-dimensional variation of the standard bar chart, usually plotted on a 3D Cartesian or geographic coordinate system.
        * What it’s good for: Visualizing data density or distribution across a grid (like a map or a matrix) where height represents magnitude. It is visually striking but can introduce occlusion (hiding) issues.

        boxplot
        * What it is: A standardized way of displaying the distribution of data based on a five-number summary: minimum, first quartile (Q1), median, third quartile (Q3), and maximum.
        * What it’s good for: Statistical analysis; comparing distributions between several groups, identifying outliers, and understanding data skewness and variance.

        candlestick
        * What it is: A financial chart type that displays the high, low, open, and closing prices of a security for a specific timeframe.
        * What it’s good for: Financial technical analysis to interpret price movements, market sentiment, and volatility patterns over time.

        chord
        * What it is: A diagram that visualizes relationships and flows between entities. Nodes are arranged radially, and arcs (ribbons) connect related nodes.
        * What it’s good for: showing complex inter-relationships, migration flows, or trade volumes between a set of entities.

        flowGL
        * What it is: A WebGL-based chart designed to visualize large-scale flow fields (vector fields) using particles or arrows.
        * What it’s good for: Visualizing meteorological data (wind, ocean currents) or massive vector datasets where performance and directional movement are critical.

        graph
        * What it is: A network diagram consisting of nodes (entities) and links (connections) that can be arranged via force-directed layouts or circular layouts.
        * What it’s good for: Visualizing social networks, topology structures, knowledge graphs, or any system defined by relationships rather than hierarchy.

        graphGL
        * What it is: A WebGL-accelerated version of the Graph chart, specifically optimized for performance.
        * What it’s good for: Rendering and interacting with massive relational datasets (tens of thousands to millions of nodes) that would crash a standard Canvas renderer.

        heatmap
        * What it is: A graphical representation of data where values within a matrix are represented as colors.
        * What it’s good for: Visualizing data density, intensity, or patterns across two dimensions (e.g., hourly traffic per day, correlation matrices).

        line
        * What it is: A chart that displays information as a series of data points connected by straight line segments.
        * What it’s good for: Visualizing trends, progress, or changes over continuous time intervals or ordered categories.

        line3D
        * What it is: A line chart plotted in a 3D space, allowing lines to travel along X, Y, and Z axes.
        * What it’s good for: Visualizing trajectories or paths in a 3D environment, such as electromagnetic field lines or flight paths.

        map
        * What it is: A geographic visualization tool that renders areas (polygons) or points on a map background.
        * What it’s good for: Visualizing location-based data, such as population by country, store locations, or election results.

        matrix
        * What it is: (Note: ECharts does not have a standalone `type: 'matrix'` series). This typically refers to a Scatter Plot Matrix (SPLOM) or a correlation matrix visualization created using multiple coordinate systems.
        * What it’s good for: Exploratory data analysis to compare multiple variables against each other simultaneously to spot correlations.

        pie
        * What it is: A circular statistical graphic divided into slices to illustrate numerical proportion.
        * What it’s good for: Showing part-to-whole relationships and composition percentages for a small number of categories.

        radar
        * What it is: A chart displaying multivariate data in the form of a two-dimensional chart of three or more quantitative variables represented on axes starting from the same point.
        * What it’s good for: Comparing multiple performance metrics (like skills, KPIs, or sports stats) for one or several entities.

        scatter
        * What it is: A chart that uses dots to represent values obtained for two different variables, plotted along the x- and y-axes.
        * What it’s good for: Observing relationships, correlations, or clusters between two variables, as well as identifying outliers.

        scatter3D
        * What it is: A three-dimensional scatter plot where data points are placed in an X, Y, Z coordinate system.
        * What it’s good for: Visualizing the distribution of data points across three variables to identify clusters in 3D space.

        sunburst
        * What it is: A hierarchical pie chart where levels of the hierarchy are represented by rings; the innermost circle is the top level.
        * What it’s good for: Visualizing multi-level hierarchical data while maintaining the ability to see the proportion of each segment relative to the whole.

        tree
        * What it is: A diagram that displays hierarchical data in a tree structure (node-link diagram), either top-down, left-right, or radial.
        * What it’s good for: Visualizing directory structures, organizational charts, or decision trees where the lineage or hierarchy is the focus.

        treemap
        * What it is: A visualization that displays hierarchical data as a set of nested rectangles. The size and color of each rectangle typically represent two distinct values.
        * What it’s good for: displaying hierarchical data efficiently, showing the weight of each node via area, and comparing proportions within complex hierarchies.
    """
    try:
        client = await get_supabase(config)
        result = await client.table("echarts").select("type, title, data, option").ilike("type", f"%{type}%").execute()

        all_examples = []
        for example in result.data: # result.data is typically a list of dicts
            all_examples.append(
                f"## Title: {example.get('title')}\n" +
                f"## Data: \nData in the chart was filled/mocked with the following:\n```javascript\n{example.get('data')}```\n" +
                f"## Option: \n```javascript\n{example.get('option')}```\n"
                )
        all_examples_str = ("\n\n").join(all_examples)
        return {"data": f"# Official examples for {result.get('type').title()} chart:\n\n" + all_examples_str}
    except Exception as e:
        return {"error": str(e)}