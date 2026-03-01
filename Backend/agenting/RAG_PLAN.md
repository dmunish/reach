# REACH Agent — RAG System for Few-Shot Chart Guidance

> **Objective:** Design a retrieval-augmented generation system that dynamically injects relevant visualization examples into the agent's context, improving chart type selection, ECharts config quality, and encode mapping accuracy — without bloating the static system prompt.

---

## 1. Problem Statement

The agent's chart generation quality is bounded by what the LLM can infer from the static few-shot examples in `prompts.py`. Those examples are:

- **Fixed in number** — a handful of examples can't cover the breadth of ECharts' capabilities
- **Fixed in topic** — examples chosen at authoring time may be irrelevant to the user's actual query
- **Token-expensive** — adding more static examples always costs context, even when irrelevant

The specific failure modes that more examples would fix:

| Failure mode | Example |
|---|---|
| Wrong chart type chosen | Picking a bar chart for a time-series trend question |
| Weak visual design | Missing `dataZoom`, no `tooltip` formatter, wrong axis type |
| Bad encode mapping | Using `"x": "date"` when the column is named `"posted_date"` |
| Unknown ECharts features | Never using `visualMap`, `markLine`, `calendar` heatmap, scatter with bubble size |
| Poor stacking / multi-series setup | Forgetting `stack: "total"`, misaligned legend entries |

RAG solves this by retrieving 3–4 targeted examples that are **semantically relevant to the user's current question** and injecting them into the context for that turn only.

---

## 2. What to Store — Design Rationale

### The three candidates

**A. Pure ECharts config objects** — just the `option` JSON, showcasing styling and chart variety.

Good for demonstrating what's possible. But without a data context, the LLM can't see how `encode` connects to a real column structure. It also doesn't help with chart type *selection* — just chart type *execution*.

**B. Full Q→A flows** — user question → SQL → `summarize_data` call → `publish_chart` call → final answer.

Teaches the full reasoning chain. But most of the content (SQL, specific column names, prose response) is too specific to transfer to a different question. Each example is ~2,000 tokens, so you can only fit 1–2 per retrieval. And the SQL patterns are misleading: a retrieved example that queries `category = 'Flood'` teaches nothing useful if the user's question is about severity distribution.

**C. Visualization recipes** — intent description + representative data shape + ECharts config with encode.

This is the right unit. A recipe captures three things the LLM actually needs:
1. **When to use this pattern** (semantic anchor for retrieval and chart type selection)
2. **What data shape enables it** (a brief SQL pattern showing the required aggregation — not a full runnable query, just the structural shape)
3. **How to configure ECharts for it** (the complete options object with encode, styling, and design choices)

Each recipe is ~400–600 tokens. You can retrieve 3–4 per turn and stay well within budget. The SQL shape is general enough to transfer; the ECharts config is concrete enough to be immediately useful.

### The verdict

**Store visualization recipes.** Additionally, keep a static ECharts capabilities catalogue in the system prompt — a reference list of chart types and their key use cases. This ensures the LLM always knows *what exists*; RAG ensures it knows *how to build the relevant one well*.

---

## 3. The Recipe Schema

Each recipe is one row in a Supabase table. The embedding is computed over `intent_description` — the natural language anchor that retrieval queries against.

```sql
CREATE TABLE rag_chart_recipes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Retrieval anchor: describes the user question type this recipe serves.
    -- This field is embedded and used for semantic search.
    intent_description  TEXT NOT NULL,

    -- Taxonomy for filtering and analytics
    chart_type      TEXT NOT NULL,   -- 'bar', 'line', 'pie', 'scatter', 'heatmap',
                                     -- 'bar_stacked', 'line_multi', 'calendar', etc.
    domain_tags     TEXT[] NOT NULL, -- ['temporal','geographic','comparison',
                                     --  'distribution','composition','correlation']

    -- The SQL shape: shows what aggregation produces data suitable for this chart.
    -- Uses {{placeholders}} for variable parts. Not a runnable query — a structural guide.
    sql_shape       TEXT NOT NULL,

    -- The complete ECharts config skeleton with encode mappings.
    -- No dataset key, no series[i].data — those are injected programmatically.
    -- Column names in encode match the SELECT aliases in sql_shape.
    echart_config   JSONB NOT NULL,

    -- Brief prose explanation of key design decisions in this recipe.
    -- Injected as a comment alongside the config in the prompt.
    design_notes    TEXT,

    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    -- pgvector embedding of intent_description (text-embedding-004 = 768 dims)
    embedding       VECTOR(768)
);

-- Index for fast cosine similarity search
CREATE INDEX idx_rag_recipes_embedding
    ON rag_chart_recipes
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);   -- Small list count is fine for a corpus < 500 rows

-- Index for pre-filtering by chart type before similarity search
CREATE INDEX idx_rag_recipes_chart_type ON rag_chart_recipes(chart_type);
```

### A complete recipe example

```json
{
  "intent_description": "How has the frequency of a disaster type changed over time? Show monthly or yearly trend.",
  "chart_type": "line_multi",
  "domain_tags": ["temporal", "comparison"],
  "sql_shape": "SELECT TO_CHAR(posted_date, 'YYYY-MM') AS month, category, COUNT(*) AS alert_count FROM alert_search_index WHERE {{filters}} GROUP BY month, category ORDER BY month",
  "echart_config": {
    "title": { "text": "{{Title}}", "left": "center" },
    "tooltip": { "trigger": "axis" },
    "legend": { "bottom": 0 },
    "grid": { "containLabel": true },
    "xAxis": { "type": "category", "boundaryGap": false },
    "yAxis": { "type": "value", "name": "Alert Count" },
    "color": ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de"],
    "dataZoom": [{ "type": "inside" }, { "type": "slider" }],
    "series": [
      {
        "type": "line", "name": "{{series_name}}",
        "encode": { "x": "month", "y": "alert_count" },
        "smooth": true,
        "areaStyle": { "opacity": 0.15 }
      }
    ]
  },
  "design_notes": "Use smooth:true and a light areaStyle for temporal trend lines — it communicates continuity. boundaryGap:false anchors the line to the axis edges. Add one series per category by repeating the series object with a different encode.y or by using a pivot query that produces separate columns per category."
}
```

---

## 4. Vector Search Strategy

### Why vector-only (no hybrid)

The retrieval signal for this use case is **semantic intent**, not keyword overlap. The user asks "how bad were the monsoon floods this year?" — the relevant recipe has `intent_description: "How has the frequency of a disaster type changed over time?"`. There is no keyword overlap between the query and the recipe. Keyword (BM25) search would fail here. Vector search captures the semantic equivalence.

The corpus will be small (~80–150 recipes). At that scale, pgvector's exact search over the full table is fast enough — no need for approximate methods. The `ivfflat` index is included as a precaution for growth, but the `lists = 10` setting keeps it tuned for small corpora.

### Embedding model

Use **`text-embedding-004`** (Google, 768 dimensions) — it's in the same API family as Gemini and has no additional vendor dependency. The same model must be used at ingestion time and at retrieval time.

Embed only `intent_description`. The config and SQL shape are not embedded — they're payload, not retrieval signal.

### Retrieval function (Supabase RPC)

```sql
CREATE OR REPLACE FUNCTION search_chart_recipes(
    query_embedding VECTOR(768),
    match_count      INT DEFAULT 4,
    chart_type_filter TEXT DEFAULT NULL   -- optional pre-filter
)
RETURNS TABLE (
    id              UUID,
    intent_description TEXT,
    chart_type      TEXT,
    sql_shape       TEXT,
    echart_config   JSONB,
    design_notes    TEXT,
    similarity      FLOAT
)
LANGUAGE SQL STABLE
AS $$
    SELECT
        id,
        intent_description,
        chart_type,
        sql_shape,
        echart_config,
        design_notes,
        1 - (embedding <=> query_embedding) AS similarity
    FROM rag_chart_recipes
    WHERE
        chart_type_filter IS NULL
        OR chart_type = chart_type_filter
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
```

---

## 5. Integration into the Agent Graph

### Where retrieval happens

Retrieval runs **once per user message**, before the `reasoner` node processes it. It does not run inside the graph loop — it runs in the FastAPI layer, before building the initial `AgentState`. This keeps the graph stateless and retrieval logic out of the LLM reasoning cycle.

```
User message arrives at /api/chat
    │
    ▼
embed(user_message) → search_chart_recipes() → top-4 recipes
    │
    ▼
Build AgentState with retrieved recipes injected into initial messages
    │
    ▼
LangGraph graph runs normally
```

### How recipes are injected into context

Recipes are injected as a block between the system prompt and the static few-shot examples. This positioning is deliberate: the system prompt sets the rules; retrieved recipes demonstrate domain-specific application of those rules; static examples demonstrate the tool-call mechanics. Each layer serves a different purpose.

```python
# agenting/retrieval.py

from google.generativeai import embed_content
from .supabase_client import get_supabase


def retrieve_recipes(user_message: str, k: int = 4) -> str:
    """
    Embed the user message, retrieve top-k chart recipes,
    and format them as a prompt block for injection into context.
    """
    client = get_supabase()

    # Embed the user's message
    result = embed_content(
        model="models/text-embedding-004",
        content=user_message,
        task_type="RETRIEVAL_QUERY",
    )
    query_embedding = result["embedding"]

    # Retrieve from Supabase
    rows = client.rpc("search_chart_recipes", {
        "query_embedding": query_embedding,
        "match_count": k,
    }).execute().data

    if not rows:
        return ""

    # Format as a prompt block
    blocks = ["## RETRIEVED VISUALIZATION RECIPES\n"
              "The following examples are relevant to the user's question. "
              "Use them as style and encode references — adapt, don't copy.\n"]

    for i, row in enumerate(rows, 1):
        import json
        config_str = json.dumps(row["echart_config"], indent=2)
        blocks.append(
            f"### Recipe {i}: {row['intent_description']}\n"
            f"**Chart type:** {row['chart_type']}\n\n"
            f"**SQL shape:**\n```sql\n{row['sql_shape']}\n```\n\n"
            f"**ECharts config skeleton:**\n```json\n{config_str}\n```\n\n"
            f"**Design notes:** {row['design_notes']}\n"
        )

    return "\n".join(blocks)
```

### Injection in `agent.py`

```python
# agenting/agent.py — inside stream_agent()

from .retrieval import retrieve_recipes
from langchain_core.messages import SystemMessage

# ...existing code to load history and build initial state...

# Retrieve relevant recipes for this query
recipes_block = retrieve_recipes(request.message)

# Inject as a SystemMessage between the static system prompt and conversation history
# The graph's reasoner prepends SYSTEM_PROMPT + FEW_SHOT_EXAMPLES,
# so we inject here as an additional context message
rag_message = SystemMessage(content=recipes_block) if recipes_block else None

initial_state: AgentState = {
    "messages": (
        ([rag_message] if rag_message else [])
        + history
        + [user_message]
    ),
    "ui_actions": [],
    "query_results": None,
    "conversation_id": conversation_id,
    "user_id": request.user_id,
}
```

The `reasoner` node then builds its prompt as:

```
[SystemMessage: SYSTEM_PROMPT]
[FEW_SHOT_EXAMPLES]           ← static, always present, teaches tool-call mechanics
[SystemMessage: recipes_block] ← dynamic, teaches chart-specific styling for this query
[conversation history]
[user message]
```

---

## 6. Initial Corpus — Synthesis Plan

The starter set should cover the full range of chart types relevant to disaster analytics, with at least two recipes per chart type (different domain applications) and special recipes for ECharts features the LLM is unlikely to use unprompted.

### Target corpus: ~100 recipes

| Category | Count | Examples |
|---|---|---|
| Temporal trends | 12 | Monthly alert counts, severity over time, rolling averages, year-on-year comparison |
| Geographic comparison | 10 | Province vs province bar, choropleth proxy, ranked district bar |
| Severity / urgency distribution | 10 | Pie, donut, stacked bar, treemap |
| Category breakdown | 8 | Grouped bar by event type, radar chart of category spread |
| Correlation & bivariate | 8 | Scatter (two metrics), bubble (three metrics with `symbolSize`) |
| Multi-metric dashboards | 6 | Dual y-axis line+bar, multi-panel with `grid` array |
| Special ECharts features | 20 | Calendar heatmap, Sankey, `visualMap` on scatter, `markLine` for thresholds, `markArea` for seasons, data zoom with time axis, polar bar, boxplot |
| Sparse / no-data handling | 6 | Empty state config, partial data with `connect: false`, graceful axis scaling |
| Table-style charts | 6 | Horizontal bar (ranking), waterfall, diverging bar |
| Time-based animation | 4 | Bar race (sort by value), animated scatter |

### Synthesis script

Generate recipes with an LLM call, then validate each one manually before ingestion. Never ingest unvalidated recipes — a bad example is worse than no example.

```python
# scripts/synthesize_recipes.py

import json
import google.generativeai as genai
from agenting.supabase_client import get_supabase
from agenting.config import settings

SYNTHESIS_PROMPT = """
You are an expert in Apache ECharts and disaster data analytics.
Generate a visualization recipe for the REACH platform (Pakistan disaster alerts).

The recipe must follow this exact JSON schema:
{
  "intent_description": "Natural language description of the user question type this serves",
  "chart_type": "<one of: bar|line|pie|scatter|heatmap|bar_stacked|line_multi|calendar|treemap|radar|sankey|boxplot|waterfall|polar>",
  "domain_tags": ["<temporal|geographic|comparison|distribution|composition|correlation>"],
  "sql_shape": "SELECT ... FROM alert_search_index WHERE {{filters}} GROUP BY ... ORDER BY ...",
  "echart_config": { <complete ECharts option object with encode, NO dataset, NO series[i].data> },
  "design_notes": "Explanation of key design decisions, 2-4 sentences"
}

Available tables:
  alert_search_index: category, severity, urgency, event, source, posted_date,
                      effective_from, effective_until, affected_places, place_ids,
                      centroid (geometry), bbox (geometry)
  places: name, parent_name, hierarchy_level, polygon (geometry)

Encode column names in echart_config must match SQL SELECT aliases.
Use ECharts dataset+encode pattern. The dataset is injected programmatically —
the config skeleton must NOT include a dataset key.

Generate a recipe for: {topic}

Return only valid JSON. No markdown fences, no preamble.
"""

TOPICS = [
    "Monthly trend of flood alerts over a year, broken down by severity",
    "Comparison of alert counts across all provinces as a ranked horizontal bar",
    "Distribution of alert categories as a donut chart",
    "Year-on-year comparison of monsoon season alerts using dual time-series lines",
    "Calendar heatmap showing alert density by day of year",
    "Bubble scatter chart correlating alert count vs affected area size per district",
    "Stacked bar of alert urgency levels per month for a given province",
    "Treemap of alert categories sized by count, coloured by average severity",
    "Radar chart comparing disaster preparedness metrics across provinces",
    "Bar race showing top 10 most-alerted districts over time",
    "Boxplot of alert duration (effective_until - effective_from) by category",
    "Dual-axis chart: bar for alert count, line for severe/extreme ratio",
    "Waterfall chart showing month-over-month change in alert volume",
    "Sankey diagram of alert flow from source agency to category to province",
    "Diverging bar showing alerts above/below historical monthly average",
    # ... expand to cover all 100 target recipes
]


def synthesize_and_ingest(topic: str, dry_run: bool = True):
    model = genai.GenerativeModel("gemini-2.5-pro")
    response = model.generate_content(
        SYNTHESIS_PROMPT.format(topic=topic),
        generation_config={"temperature": 0.2}
    )

    try:
        recipe = json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"FAILED to parse recipe for '{topic}': {e}")
        return None

    # Basic validation
    required_keys = {"intent_description", "chart_type", "echart_config", "sql_shape"}
    if not required_keys.issubset(recipe.keys()):
        print(f"MISSING KEYS in recipe for '{topic}': {required_keys - recipe.keys()}")
        return None

    if "dataset" in recipe.get("echart_config", {}):
        print(f"WARNING: recipe for '{topic}' incorrectly includes a dataset key — stripping.")
        recipe["echart_config"].pop("dataset")

    print(json.dumps(recipe, indent=2))

    if dry_run:
        print("\n[DRY RUN] Recipe not ingested.")
        return recipe

    # Embed and ingest
    embedding_result = genai.embed_content(
        model="models/text-embedding-004",
        content=recipe["intent_description"],
        task_type="RETRIEVAL_DOCUMENT",
    )

    client = get_supabase()
    client.table("rag_chart_recipes").insert({
        **recipe,
        "embedding": embedding_result["embedding"],
    }).execute()
    print(f"Ingested recipe: {recipe['intent_description'][:60]}")
    return recipe


if __name__ == "__main__":
    for topic in TOPICS:
        synthesize_and_ingest(topic, dry_run=False)
```

### Validation checklist before ingestion

Run each synthesized recipe through this checklist manually (or automate as a second LLM pass):

- [ ] `echart_config` is valid JSON
- [ ] No `dataset` key present in `echart_config`
- [ ] No `series[i].data` arrays in `echart_config`
- [ ] All `encode` column names match SQL SELECT aliases in `sql_shape`
- [ ] `xAxis.type` matches data type (`"category"` for strings, `"time"` for timestamps)
- [ ] `tooltip.trigger` is `"axis"` for cartesian, `"item"` for pie/scatter
- [ ] Design notes explain at least one non-obvious decision
- [ ] `intent_description` is phrased as a user question, not a chart description

---

## 7. Production Flywheel — Growing the Corpus

The synthesized starter set has good breadth but synthetic origins. The best recipes come from real interactions. Build a lightweight feedback loop:

### Logging good examples

When a conversation ends with a successful chart (the user didn't follow up with "that's wrong" or ask for a correction), log it as a candidate recipe. The `messages` table already stores everything needed — a background job can extract `publish_chart` calls from successful conversations and queue them for review.

```python
# scripts/extract_production_recipes.py
# Run periodically (e.g. daily cron via Supabase pg_cron)

"""
SELECT
    m.content AS publish_chart_args,
    prev.content AS user_question
FROM messages m
JOIN messages prev ON prev.conversation_id = m.conversation_id
WHERE
    m.role = 'assistant'
    AND m.tool_calls @> '[{"name": "publish_chart"}]'
    -- Only from conversations with no correction follow-up
    AND NOT EXISTS (
        SELECT 1 FROM messages correction
        WHERE correction.conversation_id = m.conversation_id
          AND correction.created_at > m.created_at
          AND correction.role = 'user'
          AND correction.content ILIKE ANY(ARRAY[
              '%wrong%', '%incorrect%', '%not what%', '%fix%', '%change the chart%'
          ])
    )
LIMIT 50;
"""
```

A human reviewer picks the most interesting ones, distils them into recipe format (stripping the specific column values from the SQL, generalising the intent description), and ingests them via the synthesis script.

### Embedding refresh

If you switch embedding models (e.g. from `text-embedding-004` to a future model), re-embed all `intent_description` values and update the `embedding` column. Store the model name as a column (`embedding_model TEXT`) so you can track which rows need refreshing.

```sql
ALTER TABLE rag_chart_recipes ADD COLUMN embedding_model TEXT DEFAULT 'text-embedding-004';
```

---

## 8. Static ECharts Capabilities Reference (System Prompt Addition)

RAG retrieves *how to build* relevant chart types well. But the LLM also needs to know *what exists* — unconditionally, on every turn — so it can proactively suggest chart types the user didn't ask for but would benefit from.

Add this section to `SYSTEM_PROMPT` in `prompts.py`:

```
## ECHARTS CAPABILITIES REFERENCE

You have access to the full ECharts library. Beyond basic bar/line/pie, consider:

TEMPORAL
  - Line with areaStyle + smooth: true → trend with visual weight
  - Calendar heatmap (type:"heatmap", coordinateSystem:"calendar") → daily density
  - dataZoom with type:"slider" → interactive time window selection
  - markLine with type:"average" → reference lines on time series

COMPARISON
  - Horizontal bar (xAxis/yAxis swapped) → ranking, easier label reading
  - Grouped bar (no stack) vs stacked bar (stack:"total") → absolute vs proportional
  - Radar → multi-metric comparison across categories
  - Diverging bar (negative values) → above/below baseline

DISTRIBUTION
  - Boxplot → spread and outliers per category
  - Scatter with jitter → raw distribution over a category axis
  - Histogram (bar with uniform bins) → value frequency

COMPOSITION
  - Pie / donut (radius:["40%","70%"]) → part-of-whole, max 6 slices
  - Treemap → hierarchical composition, area encodes magnitude
  - Sunburst → two-level hierarchy

CORRELATION
  - Scatter → two continuous variables
  - Bubble (symbolSize from data column) → three variables simultaneously
  - Heatmap on cartesian grid → two categorical dimensions vs a value

SPECIAL
  - visualMap (type:"continuous") → colour-encode a third dimension on scatter
  - markArea → highlight a date range (e.g. monsoon season) on time series
  - Dual y-axis (yAxis array, series.yAxisIndex) → bar + line on same chart
  - Sankey → flow between categories
  - Multi-grid (grid array) → multiple linked charts in one option object
```

This reference costs ~300 tokens (always present) and means the LLM never fails to consider a chart type simply because it wasn't in the retrieved recipes.

---

## 9. Complete File Additions

```
agenting/
├── retrieval.py          # NEW: embed + search_chart_recipes + format_for_prompt
└── ...existing files

scripts/
├── synthesize_recipes.py # NEW: LLM-assisted recipe generation
└── extract_production_recipes.py  # NEW: mine successful production charts
```

No new dependencies beyond `google-generativeai` (already used for the LLM) and `supabase` (already present). The pgvector extension must be enabled in Supabase (it is enabled by default on all Supabase projects).

---

## 10. Summary

```
Offline (one-time + periodic)
    synthesize_recipes.py
        │  LLM generates recipes for each topic
        │  Human validates checklist
        │  embed(intent_description) → ingest to rag_chart_recipes
        │
    extract_production_recipes.py (periodic)
        │  Mine successful publish_chart calls from messages table
        │  Human distils → generalise → ingest

Runtime (every user turn)
    User message
        │
        ▼
    retrieval.py
        embed(user_message, task="RETRIEVAL_QUERY")
        → search_chart_recipes(embedding, k=4)
        → format recipes as SystemMessage block
        │
        ▼
    AgentState.messages =
        [SYSTEM_PROMPT]           ← rules + encode reference + ECharts capabilities
        [FEW_SHOT_EXAMPLES]       ← static: teaches tool-call mechanics
        [retrieved recipes block] ← dynamic: teaches chart-specific style for this query
        [conversation history]
        [user message]
        │
        ▼
    LangGraph graph runs normally
    LLM generates publish_chart call with encode patterns
    informed by both static examples and retrieved recipes
```

**What each layer contributes:**

| Layer | What the LLM learns |
|---|---|
| System prompt | Rules, schema, encode syntax, what chart types exist |
| Static few-shot | How to call tools in sequence (the mechanics) |
| Retrieved recipes | How to style and structure *this kind* of chart well |
| Production flywheel | Continuously improves retrieved recipes from real usage |