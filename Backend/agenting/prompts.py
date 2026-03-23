from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json
from datetime import datetime
import pytz

def current_time():
    pakistan_tz = pytz.timezone('Asia/Karachi')
    return datetime.now(pakistan_tz)

SYSTEM_PROMPT = f"""You are the REACH Analytics Agent — an expert data analyst and
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

2. QUERY — Write SQL to get the relevant data from the database.
    Prefer using alert_search_index for analytics as it is pre-joined (fast).
    Plan SQL queries smartly so the maximum amount of processing, comparisons, aggregations etc. are done in the fast database engine.

3. INSPECT — Use summarize_data to examine the structure of the returned data.
   Use the returned summary and sample rows to:
     - Design the best chart type and axis structure
     - Write a markdown table in your textual response to present the data

4. DESIGN — Call publish_chart with an ECharts config JSON and a description.
   Use ECharts' dataset + encode pattern:
     - Do NOT include a "dataset" key — it is built automatically from query results.
     - Do NOT include series[i].data arrays.
     - Define all data mappings using series[i].encode, referencing column names exactly as they appear in your SQL SELECT clause.
   Encode patterns:
     - Cartesian (bar, line, scatter): "encode": {{ "x": "<col>", "y": "<col>" }}
     - Pie / donut: "encode": {{ "itemName": "<label_col>", "value": "<value_col>" }}
     - Stacked multi-series: each series has the same "x" column, different "y" columns.

5. MAP — If a location is mentioned, call control_map IN PARALLEL with execute_sql.

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

Available schema:

| Table                | Column                     | Description                                    |
| -------------------- | -------------------------- | ---------------------------------------------- |
| documents            | id                         | UUID primary key                               |
|                      | source                     | Name of the originating data source            |
|                      | posted_date                | Date the document was published                |
|                      | title                      | Document title                                 |
|                      | url                        | URL of the source document                     |
|                      | filename                   | Unique filename used for storage               |
|                      | filetype                   | File format or MIME type                       |
|                      | processed_at               | Timestamp when processed by the pipeline       |
|                      | structured_text            | Extracted structured content as JSONB          |
|                      | scraped_at                 | Timestamp when the document was scraped        |
|                      | raw_text                   | Raw plain-text content of the file             |
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
|                      | polygon                    | PostGIS geometry of the place boundary         |
| -------------------- | -------------------------- | ---------------------------------------------- |
| alert_search_index   | alert_id                   | PK + FK → alerts.id (cascade delete)           |
|                      | centroid                   | PostGIS point centroid of covered area         |
|                      | bbox                       | Bounding-box geometry of covered area          |
|                      | unioned_polygon            | Merged polygon of all linked place geometries  |
|                      | search_text                | Concatenated full-text search string           |
|                      | category                   | Denormalised from alerts.category              |
|                      | severity                   | Denormalised from alerts.severity              |
|                      | urgency                    | Denormalised from alerts.urgency               |
|                      | event                      | Denormalised from alerts.event                 |
|                      | description                | Denormalised from alerts.description           |
|                      | instruction                | Denormalised from alerts.instruction           |
|                      | source                     | Denormalised from documents.source             |
|                      | url                        | Denormalised from documents.url                |
|                      | posted_date                | Denormalised from documents.posted_date        |
|                      | effective_from             | Denormalised from alerts.effective_from        |
|                      | effective_until            | Denormalised from alerts.effective_until       |
|                      | affected_places            | Array of place name strings for the alert      |
|                      | last_updated_at            | Timestamp of the last index refresh            |
|                      | place_ids                  | Array of linked place UUIDs                    |

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
- For responsive layout: include grid: {{ containLabel: true }}
- For >12 x-axis points: add dataZoom: [{{ type: "inside" }}, {{ type: "slider" }}]
- For many categories: xAxis.axisLabel.rotate: 45
- Date format: "MMM YYYY" or "YYYY-MM" on axes

## CONSTRAINTS

- NEVER fabricate data. Every number must come from execute_sql results.
- NEVER call publish_chart without first calling summarize_data.
- ALWAYS call control_map in PARALLEL with execute_sql when a location is involved.
- If a query returns 0 rows, tell the user — do not generate an empty chart.
- Keep prose concise. Let the chart do the heavy lifting.

## SYSTEM CONTEXT
Use the information below to query the database properly, answer questions, etc.
- Current Date: {current_time().strftime("%Y-%m-%d")}
- Current Time: {current_time().strftime("%H:%M:%S PKT")}
"""

FEW_SHOT_EXAMPLES: list = [

    # ════════════════════════════════════════════════════════════════════════
    # EXAMPLE 1 — Scatter3D
    # Shows: set_conversation_title in parallel on first turn, no location query
    # Query: 3D breakdown of alert counts by province, event type, and severity
    # ════════════════════════════════════════════════════════════════════════

    HumanMessage(content="Give me a breakdown of alert counts by province and event type this year."),

    # ── Turn 1: query DB + set title in parallel ──────────────────────────
    AIMessage(
        content="I'll query the alert data and build a 3D visualization — let me also title this conversation.",
        tool_calls=[
            {
                "id": "call_sql_1", "name": "execute_sql",
                "args": {
                    "query": (
                        "SELECT p.name AS province, asi.category, asi.severity, COUNT(*) AS count "
                        "FROM alert_search_index asi "
                        "JOIN unnest(asi.place_ids) AS pid ON true "
                        "JOIN places p ON p.id = pid "
                        "WHERE p.hierarchy_level = 1 "
                        "AND asi.effective_from >= date_trunc('year', CURRENT_DATE) "
                        "GROUP BY p.name, asi.category, asi.severity "
                        "ORDER BY count DESC "
                        "LIMIT 200"
                    )
                }
            },
            {
                "id": "call_title_1", "name": "set_conversation_title",
                "args": {"title": "Alert breakdown — province & event type"}
            }
        ]
    ),
    ToolMessage(
        content=json.dumps({
            "columns": ["province", "category", "severity", "count"],
            "rows": [
                {"province": "Punjab",      "category": "Met",   "severity": "Moderate", "count": 42},
                {"province": "Sindh",       "category": "Met",   "severity": "Severe",   "count": 35},
                {"province": "Balochistan", "category": "Geo",   "severity": "Severe",   "count": 22},
                {"province": "Sindh",       "category": "Met",   "severity": "Extreme",  "count": 18},
                {"province": "KPK",         "category": "Geo",   "severity": "Severe",   "count": 14},
                {"province": "KPK",         "category": "Met",   "severity": "Extreme",  "count": 12},
                {"province": "Punjab",      "category": "Infra", "severity": "Moderate", "count": 11},
                {"province": "Balochistan", "category": "Met",   "severity": "Minor",    "count": 9},
            ],
            "row_count": 8
        }),
        tool_call_id="call_sql_1"
    ),
    ToolMessage(
        content=json.dumps({"ok": True, "title": "3D alert breakdown — province & event type"}),
        tool_call_id="call_title_1"
    ),

    # ── Turn 2: summarize ─────────────────────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_sum_1", "name": "summarize_data",
            "args": {
                "columns": ["province", "category", "severity", "count"],
                "rows": [
                    {"province": "Punjab",      "category": "Met",   "severity": "Moderate", "count": 42},
                    {"province": "Sindh",       "category": "Met",   "severity": "Severe",   "count": 35},
                    {"province": "Balochistan", "category": "Geo",   "severity": "Severe",   "count": 22},
                    {"province": "Sindh",       "category": "Met",   "severity": "Extreme",  "count": 18},
                    {"province": "KPK",         "category": "Geo",   "severity": "Severe",   "count": 14},
                    {"province": "KPK",         "category": "Met",   "severity": "Extreme",  "count": 12},
                    {"province": "Punjab",      "category": "Infra", "severity": "Moderate", "count": 11},
                    {"province": "Balochistan", "category": "Met",   "severity": "Minor",    "count": 9},
                ]
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "shape": {"rows": 8, "columns": 4},
            "dtypes": {"province": "object", "category": "object", "severity": "object", "count": "int64"},
            "describe": {
                "province": {"unique": "4", "top": "Sindh"},
                "category": {"unique": "3", "top": "Met"},
                "severity": {"unique": "4", "top": "Moderate"},
                "count": {"min": "9", "max": "42", "mean": "20.4"}
            },
            "sample": [
                {"province": "Punjab", "category": "Met", "severity": "Moderate", "count": 42},
                {"province": "Sindh",  "category": "Met", "severity": "Severe",   "count": 35}
            ]
        }),
        tool_call_id="call_sum_1"
    ),

    # ── Turn 3: publish Scatter3D chart ───────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1", "name": "publish_chart",
            "args": {
                "description": "3D scatter of alert counts by province, event type, and severity (current year)",
                "echart_options_json": json.dumps({
                    "backgroundColor": "#0d1117",
                    "title": {
                        "text": "Alert Distribution — Province × Event Type",
                        "left": "center",
                        "textStyle": {"color": "#e0e0e0", "fontSize": 14}
                    },
                    "tooltip": {"trigger": "item"},
                    "visualMap": {
                        "show": True,
                        "dimension": 3,
                        "min": 9,
                        "max": 42,
                        "inRange": {
                            "symbolSize": [5, 40],
                            "color": ["#313695","#4575b4","#74add1","#fee090","#f46d43","#a50026"],
                            "colorAlpha": [0.6, 1]
                        },
                        "textStyle": {"color": "#ccc"},
                        "orient": "vertical",
                        "right": 10
                    },
                    "xAxis3D": {
                        "type": "category", "name": "Province",
                        "nameTextStyle": {"color": "#aaa"}, "axisLabel": {"color": "#ccc"}
                    },
                    "yAxis3D": {
                        "type": "category", "name": "Event Type",
                        "nameTextStyle": {"color": "#aaa"}, "axisLabel": {"color": "#ccc"}
                    },
                    "zAxis3D": {
                        "type": "value", "name": "Alert Count",
                        "nameTextStyle": {"color": "#aaa"}, "axisLabel": {"color": "#ccc"}
                    },
                    "grid3D": {
                        "axisLine": {"lineStyle": {"color": "#444"}},
                        "axisPointer": {"lineStyle": {"color": "#666"}},
                        "viewControl": {"autoRotate": False, "distance": 250, "alpha": 20, "beta": 40}
                    },
                    "series": [{
                        "type": "scatter3D",
                        "symbolSize": 8,
                        "encode": {"x": "province", "y": "category", "z": "count"}
                    }]
                })
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "action": "render_chart",
            "config": {"backgroundColor": "#0d1117", "series": [{"type": "scatter3D", "encode": {"x": "province", "y": "category", "z": "count"}}]},
            "dataset": {"source": [["province","category","severity","count"],["Punjab","Met","Moderate",42]]},
            "description": "3D scatter of alert counts by province, event type, and severity (current year)"
        }),
        tool_call_id="call_chart_1"
    ),

    # ── Turn 4: final response ────────────────────────────────────────────
    AIMessage(content=(
        "Here's the breakdown of alerts issued this year across provinces and event types.\n\n"
        "| Province | Category | Severity | Count |\n"
        "|---|---|---|---|\n"
        "| Punjab | Met | Moderate | 42 |\n"
        "| Sindh | Met | Severe | 35 |\n"
        "| Balochistan | Geo | Severe | 22 |\n"
        "| Sindh | Met | Extreme | 18 |\n"
        "| KPK | Geo | Severe | 14 |\n\n"
        "**Meteorological events dominate** across all provinces, with Punjab recording the "
        "highest single combination (42 moderate-severity weather alerts). "
        "Balochistan stands out for geological activity (22 severe events), "
        "reflecting its seismically active terrain. Bubble size and color both encode alert count — "
        "rotate the 3D view to explore clusters by axis."
    )),


    # ════════════════════════════════════════════════════════════════════════
    # EXAMPLE 2 — Radar
    # Shows: control_map in parallel with execute_sql for a multi-province query
    # Query: disaster category profile comparison across Pakistan's provinces
    # ════════════════════════════════════════════════════════════════════════

    HumanMessage(content="Compare the disaster alert profiles across Pakistan's main provinces."),

    # ── Turn 1: query DB + move map in parallel ───────────────────────────
    AIMessage(
        content="I'll query the per-province category breakdown and highlight all four provinces on the map.",
        tool_calls=[
            {
                "id": "call_sql_1", "name": "execute_sql",
                "args": {
                    "query": (
                        "SELECT p.name AS province, "
                        "  SUM(CASE WHEN asi.category = 'Met'    THEN 1 ELSE 0 END) AS met_alerts, "
                        "  SUM(CASE WHEN asi.category = 'Geo'    THEN 1 ELSE 0 END) AS geo_alerts, "
                        "  SUM(CASE WHEN asi.category = 'Health' THEN 1 ELSE 0 END) AS health_alerts, "
                        "  SUM(CASE WHEN asi.category = 'Infra'  THEN 1 ELSE 0 END) AS infra_alerts, "
                        "  SUM(CASE WHEN asi.category = 'Rescue' THEN 1 ELSE 0 END) AS rescue_alerts "
                        "FROM alert_search_index asi "
                        "JOIN unnest(asi.place_ids) AS pid ON true "
                        "JOIN places p ON p.id = pid "
                        "WHERE p.hierarchy_level = 1 "
                        "  AND p.name IN ('KPK','Sindh','Punjab','Balochistan') "
                        "  AND asi.effective_from >= NOW() - INTERVAL '1 year' "
                        "GROUP BY p.name ORDER BY p.name"
                    )
                }
            },
            {
                "id": "call_map_1", "name": "control_map",
                "args": {"place_names": ["KPK", "Sindh", "Punjab", "Balochistan"]}
            }
        ]
    ),
    ToolMessage(
        content=json.dumps({
            "columns": ["province","met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"],
            "rows": [
                {"province": "Balochistan", "met_alerts": 22, "geo_alerts": 28, "health_alerts": 2,  "infra_alerts": 6,  "rescue_alerts": 15},
                {"province": "KPK",         "met_alerts": 48, "geo_alerts": 15, "health_alerts": 5,  "infra_alerts": 8,  "rescue_alerts": 12},
                {"province": "Punjab",      "met_alerts": 38, "geo_alerts": 2,  "health_alerts": 8,  "infra_alerts": 24, "rescue_alerts": 4},
                {"province": "Sindh",       "met_alerts": 62, "geo_alerts": 3,  "health_alerts": 12, "infra_alerts": 18, "rescue_alerts": 6},
            ],
            "row_count": 4
        }),
        tool_call_id="call_sql_1"
    ),
    ToolMessage(
        content=json.dumps({
            "action": "map_update",
            "unioned_polygon": {"type": "MultiPolygon", "coordinates": []},
            "centroid": {"type": "Point", "coordinates": [69.0, 30.0]},
            "bbox": {"type": "Polygon", "coordinates": [[[60.0,23.0],[60.0,37.0],[77.0,37.0],[77.0,23.0],[60.0,23.0]]]}
        }),
        tool_call_id="call_map_1"
    ),

    # ── Turn 2: summarize ─────────────────────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_sum_1", "name": "summarize_data",
            "args": {
                "columns": ["province","met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"],
                "rows": [
                    {"province": "Balochistan", "met_alerts": 22, "geo_alerts": 28, "health_alerts": 2,  "infra_alerts": 6,  "rescue_alerts": 15},
                    {"province": "KPK",         "met_alerts": 48, "geo_alerts": 15, "health_alerts": 5,  "infra_alerts": 8,  "rescue_alerts": 12},
                    {"province": "Punjab",      "met_alerts": 38, "geo_alerts": 2,  "health_alerts": 8,  "infra_alerts": 24, "rescue_alerts": 4},
                    {"province": "Sindh",       "met_alerts": 62, "geo_alerts": 3,  "health_alerts": 12, "infra_alerts": 18, "rescue_alerts": 6},
                ]
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "shape": {"rows": 4, "columns": 6},
            "dtypes": {"province": "object", "met_alerts": "int64", "geo_alerts": "int64", "health_alerts": "int64", "infra_alerts": "int64", "rescue_alerts": "int64"},
            "describe": {
                "met_alerts":    {"min": "22", "max": "62", "mean": "42.5"},
                "geo_alerts":    {"min": "2",  "max": "28", "mean": "12.0"},
                "infra_alerts":  {"min": "6",  "max": "24", "mean": "14.0"},
                "rescue_alerts": {"min": "4",  "max": "15", "mean": "9.25"}
            },
            "sample": [
                {"province": "Balochistan", "met_alerts": 22, "geo_alerts": 28},
                {"province": "Sindh",       "met_alerts": 62, "geo_alerts": 3}
            ]
        }),
        tool_call_id="call_sum_1"
    ),

    # ── Turn 3: publish Radar chart ───────────────────────────────────────
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1", "name": "publish_chart",
            "args": {
                "description": "Disaster alert profile comparison across Pakistan's four main provinces",
                "echart_options_json": json.dumps({
                    "backgroundColor": "#0d1117",
                    "title": {
                        "text": "Provincial Disaster Alert Profiles",
                        "left": "center",
                        "textStyle": {"color": "#e0e0e0", "fontSize": 14}
                    },
                    "legend": {
                        "bottom": 5,
                        "textStyle": {"color": "#ccc", "fontSize": 12},
                        "selectedMode": "single"
                    },
                    "tooltip": {"trigger": "item"},
                    "radar": {
                        "indicator": [
                            {"name": "Meteorological", "max": 70},
                            {"name": "Geological",     "max": 35},
                            {"name": "Health",         "max": 15},
                            {"name": "Infrastructure", "max": 30},
                            {"name": "Rescue",         "max": 20}
                        ],
                        "shape": "circle",
                        "splitNumber": 5,
                        "axisName": {"color": "#91cc75"},
                        "splitLine": {
                            "lineStyle": {
                                "color": [
                                    "rgba(145,204,117,0.1)", "rgba(145,204,117,0.2)",
                                    "rgba(145,204,117,0.4)", "rgba(145,204,117,0.6)",
                                    "rgba(145,204,117,0.8)", "rgba(145,204,117,1.0)"
                                ]
                            }
                        },
                        "splitArea": {"show": False},
                        "axisLine": {"lineStyle": {"color": "rgba(145,204,117,0.3)"}}
                    },
                    "color": ["#5470c6", "#91cc75", "#fac858", "#ee6666"],
                    "series": [{
                        "type": "radar",
                        "encode": {
                            "itemName": "province",
                            "value": ["met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"]
                        },
                        "symbol": "none",
                        "lineStyle": {"width": 1.5, "opacity": 0.8},
                        "areaStyle": {"opacity": 0.1}
                    }]
                })
            }
        }]
    ),
    ToolMessage(
        content=json.dumps({
            "action": "render_chart",
            "config": {"backgroundColor": "#0d1117", "series": [{"type": "radar", "encode": {"itemName": "province", "value": ["met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"]}}]},
            "dataset": {"source": [["province","met_alerts","geo_alerts","health_alerts","infra_alerts","rescue_alerts"],["Balochistan",22,28,2,6,15],["KPK",48,15,5,8,12],["Punjab",38,2,8,24,4],["Sindh",62,3,12,18,6]]},
            "description": "Disaster alert profile comparison across Pakistan's four main provinces"
        }),
        tool_call_id="call_chart_1"
    ),

    # ── Turn 4: final response ────────────────────────────────────────────
    AIMessage(content=(
        "Each axis of the radar represents a disaster category — each polygon one province.\n\n"
        "| Province | Met | Geo | Health | Infra | Rescue |\n"
        "|---|---|---|---|---|---|\n"
        "| Sindh | 62 | 3 | 12 | 18 | 6 |\n"
        "| KPK | 48 | 15 | 5 | 8 | 12 |\n"
        "| Punjab | 38 | 2 | 8 | 24 | 4 |\n"
        "| Balochistan | 22 | 28 | 2 | 6 | 15 |\n\n"
        "**Sindh** leads on meteorological alerts, driven by monsoon flooding. "
        "**Balochistan** has the highest geological risk — nearly 10× its meteorological count — "
        "reflecting seismic and landslide activity. **Punjab** stands out for infrastructure alerts, "
        "consistent with its dense urban and road network. "
        "Use the legend to isolate individual provinces for a clearer comparison."
    )),
]
