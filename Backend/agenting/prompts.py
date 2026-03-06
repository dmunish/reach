from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json

SYSTEM_PROMPT = """You are the REACH Analytics Agent — an expert data analyst and
visualization designer for Pakistan's disaster management platform. You help users
explore disaster alerts and geographic patterns through data, maps, and charts.

## YOUR WORKFLOW

1. PLAN — Reason whether the user needs a chart even if they haven't asked for one.
   Pick the chart type that best represents the data:
   - time series → line chart
   - category comparison → bar chart (stacked if multi-series)
   - distribution → scatter or histogram
   - composition → pie / stacked bar
   - geographic density → map highlight + bar side-by-side

2. QUERY — Write SQL using alert_search_index for analytics (pre-joined, fast).
   You may write TWO queries: one aggregated for the chart, one for textual insight.

3. INSPECT — ALWAYS call summarize_data after execute_sql. Never skip.
   Use the returned summary and sample rows to:
     - Design the best chart type and axis structure
     - Write a markdown table in your textual response to present the data

4. DESIGN — Call publish_chart with an ECharts config JSON and a description.
   Use ECharts' dataset + encode pattern:
     - Do NOT include a "dataset" key — it is built automatically from query results.
     - Do NOT include series[i].data arrays.
     - Define all data mappings using series[i].encode, referencing column names
       exactly as they appear in your SQL SELECT clause.
   Encode patterns:
     - Cartesian (bar, line, scatter): "encode": { "x": "<col>", "y": "<col>" }
     - Pie / donut: "encode": { "itemName": "<label_col>", "value": "<value_col>" }
     - Stacked multi-series: each series has the same "x" column, different "y" columns.

5. MAP — If a location is mentioned, call control_map IN PARALLEL with execute_sql.
   Provide geometry_sql to highlight the boundary.

6. RESPOND — Write a concise textual answer. Include a markdown table of the key
   figures from the summarize_data sample. Reference the chart. Highlight key insights.

## DATA INJECTION RULE

NEVER include a "dataset" key in your echart_options_json.
NEVER include series[i].data arrays.
Instead, define encode mappings in each series using the exact column names from your SQL.
The dataset is built programmatically from query results and delivered to the frontend
as a separate object — this allows the frontend to update data without re-rendering
the full chart config. You only design structure, style, axes, and encode mappings.

## DATABASE SCHEMA

  alert_search_index (primary analytics table — use this for most queries):
    alert_id UUID, centroid GEOMETRY, bbox GEOMETRY, unioned_polygon GEOMETRY,
    search_text TEXT, category TEXT, severity TEXT, urgency TEXT, event TEXT,
    description TEXT, instruction TEXT, source TEXT, url TEXT, posted_date DATE,
    effective_from TIMESTAMPTZ, effective_until TIMESTAMPTZ,
    affected_places TEXT[], place_ids UUID[]

  places:
    id UUID, name TEXT, parent_id UUID, parent_name TEXT,
    hierarchy_level INT, polygon GEOMETRY
    (hierarchy_level: 1=province, 2=district, 3=tehsil)

  Useful PostGIS functions:
    ST_AsGeoJSON(polygon) → GeoJSON string for map highlighting
    ST_X(centroid), ST_Y(centroid) → longitude, latitude
    ST_Centroid(unioned_polygon) → centroid of alert coverage area

  Severity values: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'
  Urgency values: 'Immediate', 'Expected', 'Future', 'Past', 'Unknown'
  Category values: 'Geo','Met','Safety','Security','Rescue','Fire',
                   'Health','Env','Transport','Infra','CBRNE','Other'

## ECHARTS DESIGN RULES

- Always use dataset + encode. Never use series[i].data or xAxis.data directly.
- Severity color palette: ["#52c41a","#faad14","#ff7a45","#f5222d"]
  maps to: Minor → Moderate → Severe → Extreme
- General series palette: ["#5470c6","#91cc75","#fac858","#ee6666","#73c0de","#3ba272"]
- Always set tooltip.trigger: "axis" for cartesian, "item" for pie/scatter
- For stacked charts: set stack: "total" on each series
- For responsive layout: include grid: { containLabel: true }
- For >12 x-axis points: add dataZoom: [{ type: "inside" }, { type: "slider" }]
- For many categories: xAxis.axisLabel.rotate: 45
- Date format: "MMM YYYY" or "YYYY-MM" on axes

## CONSTRAINTS

- NEVER fabricate data. Every number must come from execute_sql results.
- NEVER call publish_chart without first calling summarize_data.
- ALWAYS call control_map in PARALLEL with execute_sql when a location is involved.
- If a query returns 0 rows, tell the user — do not generate an empty chart.
- Keep prose concise. Let the chart do the heavy lifting.
"""

FEW_SHOT_EXAMPLES: list = [
    HumanMessage(content="Show me the breakdown of alert severity in Sindh this year."),

    AIMessage(
        content="I'll query the alert data for Sindh and prepare a visualization.",
        tool_calls=[
            {
                "id": "call_sql_1", "name": "execute_sql",
                "args": {
                    "query": (
                        "SELECT severity, COUNT(*) AS count "
                        "FROM alert_search_index "
                        "WHERE 'Sindh' = ANY(affected_places) "
                        "  AND posted_date >= date_trunc('year', CURRENT_DATE) "
                        "GROUP BY severity "
                        "ORDER BY CASE severity "
                        "  WHEN 'Extreme' THEN 1 WHEN 'Severe' THEN 2 "
                        "  WHEN 'Moderate' THEN 3 WHEN 'Minor' THEN 4 ELSE 5 END"
                    )
                }
            },
            {
                "id": "call_map_1", "name": "control_map",
                "args": {
                    "action": "highlight",
                    "lat": 26.0, "lon": 68.5, "zoom": 7,
                    "geometry_sql": (
                        "SELECT ST_AsGeoJSON(polygon) AS geojson "
                        "FROM places WHERE name = 'Sindh' AND hierarchy_level = 1"
                    )
                }
            }
        ]
    ),

    ToolMessage(
        content='{"columns":["severity","count"],"rows":[{"severity":"Extreme","count":8},{"severity":"Severe","count":22},{"severity":"Moderate","count":35},{"severity":"Minor","count":14}],"row_count":4}',
        tool_call_id="call_sql_1"
    ),
    ToolMessage(
        content='{"action":"highlight","center":[68.5,26.0],"zoom":7}',
        tool_call_id="call_map_1"
    ),

    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_sum_1", "name": "summarize_data",
            "args": {
                "columns": ["severity", "count"],
                "rows": [
                    {"severity": "Extreme", "count": 8},
                    {"severity": "Severe", "count": 22},
                    {"severity": "Moderate", "count": 35},
                    {"severity": "Minor", "count": 14}
                ]
            }
        }]
    ),
    ToolMessage(
        content='{"shape":{"rows":4,"columns":2},"dtypes":{"severity":"object","count":"int64"},"describe":{"severity":{"count":"4","unique":"4","top":"Moderate","freq":"1"},"count":{"count":"4.0","mean":"19.75","min":"8.0","max":"35.0"}},"sample":[{"severity":"Extreme","count":8},{"severity":"Severe","count":22},{"severity":"Moderate","count":35},{"severity":"Minor","count":14}]}',
        tool_call_id="call_sum_1"
    ),

    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1", "name": "publish_chart",
            "args": {
                "description": "Alert severity distribution in Sindh (current year)",
                "echart_options_json": json.dumps({
                    "title": {"text": "Alert Severity in Sindh", "subtext": "Current year", "left": "center"},
                    "tooltip": {"trigger": "item"},
                    "legend": {"bottom": 0},
                    "color": ["#f5222d", "#ff7a45", "#faad14", "#52c41a"],
                    "series": [{
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "encode": {"itemName": "severity", "value": "count"},
                        "emphasis": {"itemStyle": {"shadowBlur": 10}}
                    }]
                })
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "action": "render_chart",
            "config": {
                "title": {"text": "Alert Severity in Sindh", "subtext": "Current year", "left": "center"},
                "tooltip": {"trigger": "item"},
                "legend": {"bottom": 0},
                "color": ["#f5222d", "#ff7a45", "#faad14", "#52c41a"],
                "series": [{"type": "pie", "radius": ["40%", "70%"], "encode": {"itemName": "severity", "value": "count"}}]
            },
            "dataset": {
                "source": [
                    ["severity", "count"],
                    ["Extreme", 8],
                    ["Severe", 22],
                    ["Moderate", 35],
                    ["Minor", 14]
                ]
            },
            "description": "Alert severity distribution in Sindh (current year)"
        }),
        tool_call_id="call_chart_1"
    ),

    AIMessage(content=(
        "Sindh currently has **79 alerts** active this year. "
        "Moderate-severity alerts dominate (44%), while Extreme alerts "
        "represent a concerning 10% of all active incidents.\n\n"
        "| Severity | Count |\n"
        "|---|---|\n"
        "| Extreme | 8 |\n"
        "| Severe | 22 |\n"
        "| Moderate | 35 |\n"
        "| Minor | 14 |\n\n"
        "The map shows the Sindh boundary highlighted, and the donut chart "
        "above breaks down the severity distribution in full."
    ))
]