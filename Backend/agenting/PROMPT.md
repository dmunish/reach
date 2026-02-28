# High-level

``` question
I am planning to integrate a conversational data analytics agent to my REACH project. It's abilities should include:
- General QA
- Fetching appropriately formatted data from the backend (either by using a special function or RAW SQL for maximum control - there will be appropriate measures to prevent execution other than select)
- Using the returned data to answer questions and presenting it to the user
- Continuous streaming of the agent's thinking, tool choices and responses
- Moving the map to specific locations and coordinates by using centroids and bboxes
- Highlighting specific areas on the map by fetching geometries from the database
- Using Apache Echart's declarative nature to construct an options object, appending data to it and sending it to frontend for rendering

Now, you have to explain how to architect it, using high-level descriptions and code snippets:
- What framework to choose: LangChain, LangGraph, something else?
- What tools and nodes to define
- How data will flow
- What the agent's data schema should look like
- How to store user's interactions in Supabase and allow for branching, continuation of previous chats, etc.
- How to deploy: a Supabase edge function, a serverless container on Modal, Cloudflare Workers, etc.

Explain everything in detail. The architecture should be clean, modular. That said, it should also maintain a level of simplicity and be straightforward. Use modern software design patterns and principles. Format your answer to maintain a logical flow and make it easy for me to understand and follow.

This is a sophisticated addition to REACH that moves it from a visualization dashboard to an interactive decision-support system. Given your requirements for streaming, map control, and data visualization, a standard "chatbot" architecture won't suffice. You need a stateful, cyclic agentic workflow.
```


Here is a detailed architectural blueprint for the **REACH Analytics Agent**.

---

### 1. Framework Choice: **LangGraph**

While LangChain is excellent for linear chains, your requirements (branching, loops for tool correction, and continuous streaming) scream **LangGraph**.

* **Why?** LangGraph treats the agent as a graph of nodes (functions) and edges (conditions). It allows the agent to "think," try a SQL query, fail (perhaps due to syntax), fix it, and try again before responding.
* **State Management:** It maintains a global `State` object that passes through every node, making it easy to track conversation history, current tool outputs, and UI triggers (like map moves).

---

### 2. High-Level Architecture & Data Flow

The agent operates as a loop that only exits when it generates a final response for the user.

**The Graph Flow:**

1. **Input:** User sends a message (e.g., "Show me flood alerts in Sindh from last week").
2. **Reasoner Node (LLM):** The model analyzes the state and decides:
* Do I need data? $\rightarrow$ Call `SQL Tool`.
* Do I need to move the map? $\rightarrow$ Call `Map Control Tool`.
* Do I need a chart? $\rightarrow$ Call `ECharts Tool`.
* Do I have enough info? $\rightarrow$ Go to `Response Node`.


3. **Tool Node:** Executes the chosen tool (e.g., runs the SQL on Supabase).
4. **Feedback:** The tool output is added to the state.
5. **Loop:** Control goes back to the **Reasoner Node** to decide the next step.
6. **Streaming:** Throughout this process, "thoughts" and "tool calls" are streamed to the frontend via Server-Sent Events (SSE) or WebSockets.

---

### 3. Agent State Schema

In LangGraph, the State is the single source of truth.

```python
from typing import TypedDict, Annotated, List, Union
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    # Append-only list of messages (User, AI, Tool)
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Context for the UI (e.g., Map coordinates to fly to)
    ui_actions: List[dict] 
    
    # Extracted user intent (optional, good for debugging)
    current_intent: str

```

---

### 4. Tool Definitions

These are the "arms and legs" of your agent.

#### A. `read_only_sql`

Executes raw SQL against your Supabase instance.

* **Safety:** Create a specific Postgres Role (`read_only_agent`) in Supabase that *only* has `SELECT` permissions on specific tables (`alerts`, `geometries`). This is safer than any prompt injection guardrail.

```python
from langchain.tools import tool

@tool
def read_only_sql(query: str):
    """
    Executes a read-only SQL query against the REACH database.
    Schema: alerts(id, severity, description, created_at, location_name, geom_id), 
            geometries(id, polygon, centroid)
    """
    # 1. basic string check for strict safety (redundant if DB role is set correctly)
    if "drop" in query.lower() or "delete" in query.lower() or "update" in query.lower():
        return "Error: Read-only access allowed."
    
    # 2. Execute via Supabase Python Client
    try:
        response = supabase.rpc("execute_sql", {"query_text": query}).execute()
        return response.data
    except Exception as e:
        return f"Database Error: {e}"

```

#### B. `control_map`

Does not fetch data, but returns a structured command that the frontend interprets to move the Mapbox camera.

```python
@tool
def control_map(location_name: str = None, lat: float = None, lon: float = None, zoom: float = 10):
    """
    Moves the map to a specific location. Use either location_name (to lookup centroid) 
    or specific lat/lon coordinates.
    """
    return {
        "action": "fly_to",
        "params": {
            "center": [lon, lat],
            "zoom": zoom
        }
    }

```

#### C. `generate_echart`

Constructs the JSON config for Apache ECharts. The agent retrieves data first (via SQL), then passes that data into this tool to format it.

```python
@tool
def generate_echart(chart_type: str, x_axis_data: list, series_data: list, title: str):
    """
    Generates an ECharts configuration object.
    chart_type: 'bar', 'line', or 'pie'.
    """
    options = {
        "title": {"text": title},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": x_axis_data},
        "yAxis": {"type": "value"},
        "series": [{"data": series_data, "type": chart_type}]
    }
    return {"action": "render_chart", "payload": options}

```

---

### 5. Backend Logic (The Node Code)

You'll need a "Router" to decide what to do next.

```python
from langgraph.graph import StateGraph, END

# Define the graph
workflow = StateGraph(AgentState)

# 1. Define Nodes
def reasoner(state):
    # Calls the LLM (e.g., Gemini 3 Pro) with access to tools
    response = model.invoke(state['messages'])
    return {"messages": [response]}

def tool_executor(state):
    # Executes the tool call requested by the last message
    last_message = state['messages'][-1]
    # ... logic to run tool and return ToolMessage ...
    return {"messages": [tool_message], "ui_actions": [ui_payload]}

# 2. Define Edges
def should_continue(state):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "continue"
    return "end"

# 3. Build Graph
workflow.add_node("agent", reasoner)
workflow.add_node("action", tool_executor)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "end": END
    }
)
workflow.add_edge("action", "agent")

app = workflow.compile()

```

---

### 6. Chat Persistence Schema (Supabase)

To support branching and history, do not store "chat logs" as a simple JSON blob. Use a relational structure.

**Table: `conversations**`

* `id` (UUID, PK)
* `user_id` (UUID, FK to auth.users)
* `title` (Text)
* `created_at`

**Table: `messages**`

* `id` (UUID, PK)
* `conversation_id` (FK)
* `role` (Enum: 'user', 'assistant', 'tool')
* `content` (Text)
* `tool_calls` (JSONB) - stores the tool name and args if applicable
* `parent_id` (UUID, Self-FK) - **Crucial for Branching/Edit**
* `ui_state` (JSONB) - Stores the map position or chart displayed at this turn

*Why `parent_id`?* If a user edits a previous message, you fork the tree from that parent ID, creating a new "branch" of the conversation without losing the old one.

---

### 7. Deployment Strategy: **Modal (Serverless Containers)**

Do not use Supabase Edge Functions for the agent itself.

* **Reason:** Edge functions have timeout limits (usually 60s max on Pro) and restricted Python environments (no C-extensions like Pandas or heavy ML libraries).
* **Solution:** Use **Modal** (or Fly.io/Render). It spins up a container in seconds, runs the heavy LangGraph logic, and shuts down.

**The Setup:**

1. **Frontend (React):** Sends user message + conversation history ID to Modal endpoint.
2. **Modal Container:**
* Initializes LangGraph.
* Connects to Supabase (via connection string).
* Runs the graph loop.
* **Streams** chunks back to the frontend.


3. **Frontend:**
* Listens to the stream.
* If a chunk contains textual tokens $\rightarrow$ Append to chat bubble.
* If a chunk contains `ui_actions` (e.g., `fly_to`) $\rightarrow$ Trigger Mapbox `map.flyTo()`.
* If a chunk contains chart config $\rightarrow$ Update React ECharts state.



### 8. Example "Thinking" Stream Format

When streaming from the backend, use a structured event format so the frontend knows what to render.

```json
// Event: "thought"
{ "type": "thought", "content": "I need to query the database for alerts in Punjab..." }

// Event: "tool_start"
{ "type": "tool_start", "tool": "read_only_sql", "input": "SELECT * FROM..." }

// Event: "tool_result"
{ "type": "tool_result", "output": "25 rows returned..." }

// Event: "ui_command"
{ "type": "map_move", "lat": 30.37, "lon": 69.34 }

// Event: "response_chunk"
{ "type": "text", "content": "I found 25 severe alerts..." }

```

### Summary of Next Steps

1. **Database:** Create the `read_only_agent` role and `conversations/messages` tables in Supabase.
2. **Backend:** Initialize a Python project with `langgraph`, `langchain-google-genai` (since you use Gemini), and `supabase`.
3. **Frontend:** Build a persistent chat sidebar in your React app that handles the streaming protocol defined above.


# Few-shot
``` question
Where do I prompt the LLM? Such as giving it examples of Echarts options object for better generation.
```

To ensure your AI agent consistently outputs valid SQL, precise map coordinates, and correctly structured ECharts objects, you need to implement a **System Prompt** and **Few-Shot Examples**.

In the LangGraph architecture we discussed, this happens at the **Reasoner Node**. You don't just send the user's message; you wrap it in a comprehensive set of instructions and "golden" examples.

---

## 1. The System Prompt Structure

The System Prompt is the "personality and rulebook" of your agent. You should define it as a static string or a managed template.

### What to include:

* **Role Definition:** "You are the REACH Analytics Specialist. You help users visualize disaster data in Pakistan."
* **Database Schema:** Explicitly list your table names and columns so the LLM doesn't hallucinate field names.
* **Output Constraints:** "Always return ECharts options as a JSON object within the `generate_echart` tool call."
* **Spatial Logic:** "When a user mentions a province, use the `control_map` tool to center on that province's centroid."

---

## 2. Implementing Few-Shot Examples

This is where you provide the "examples of ECharts options" you mentioned. By showing the model 2–3 successful "User Query $\rightarrow$ Tool Call" pairs, you dramatically improve its accuracy.

### Example Python Implementation (LangChain/LangGraph):

```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Define your few-shot examples
FEW_SHOT_EXAMPLES = [
    HumanMessage(content="Show me a bar chart of alerts by severity in Sindh."),
    AIMessage(
        content="",
        tool_calls=[{
            "name": "read_only_sql",
            "args": {"query": "SELECT severity, COUNT(*) FROM alerts WHERE location_name ILIKE '%Sindh%' GROUP BY severity"}
        }]
    ),
    # Pre-calculated mock response from the tool to show the model how to use that data for ECharts
    HumanMessage(content="The database returned: [{'severity': 'High', 'count': 12}, {'severity': 'Medium', 'count': 8}]"),
    AIMessage(
        content="I've gathered the data. Here is the breakdown for Sindh.",
        tool_calls=[{
            "name": "generate_echart",
            "args": {
                "chart_type": "bar",
                "title": "Alert Severity in Sindh",
                "x_axis_data": ["High", "Medium"],
                "series_data": [12, 8]
            }
        }]
    )
]

def reasoner(state):
    # Combine System Message + Few-Shot Examples + Current Conversation History
    system_message = SystemMessage(content="You are a data expert for REACH... [Full System Prompt Here]")
    
    # The 'messages' in state contains the current user session
    full_prompt = [system_message] + FEW_SHOT_EXAMPLES + state['messages']
    
    response = model.bind_tools(tools).invoke(full_prompt)
    return {"messages": [response]}

```

---

## 3. Where to store these prompts?

Since your project uses **Supabase**, you have two clean options for managing these prompts without hardcoding them:

| Method | Description | Pros |
| --- | --- | --- |
| **Supabase Config Table** | Store the system prompt string and few-shot JSON in a `system_settings` table. | You can update the AI's "brain" via the Supabase dashboard without redeploying code. |
| **LangSmith (Recommended)** | If you use LangChain/LangGraph, use LangSmith's "Prompt Hub." | Provides version control and a playground to test how different prompts affect ECharts generation. |

---

## 4. Pro-Tip: The "Negative Constraint"

To prevent the LLM from making "ugly" charts, add specific style requirements to the ECharts example in your prompt:

* *"Always use the color palette: ['#ff4d4f', '#ffa940', '#ffec3d'] for High, Medium, and Low severity."*
* *"Ensure `responsive: true` is set in the options object."*

**Would you like me to draft a full, production-ready System Prompt specifically tailored to your REACH database schema?**


# Provider agnostic
``` question
How to make the agent "LLM agnostic" and easily plug in different LLMs and providers (like Novita AI, my own deployment on Modal, etc.)? I already have a setup where I have defined the options for different LLM in a json to be used with the OpenAI API, and then I can change the LLM my changing a single variable. We could use that or something even more clearer.
```

To make your agent truly **LLM-agnostic**, you should decouple the model initialization from your graph logic. Since most providers (Novita, DeepSeek, or your own vLLM deployment on Modal) now support the **OpenAI API specification**, you can use a "Factory Pattern" combined with LangChain’s standardized interface.

Here is the most professional and scalable way to architect this.

---

### 1. The LLM Factory Pattern

Instead of hardcoding a model, create a `get_model` utility. This function takes a "Provider ID" and returns a LangChain-compatible object.

Even if you use different providers, LangChain’s `ChatOpenAI` class can be "tricked" into talking to them by simply changing the `base_url`.

```python
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import os

def get_model(provider: str, model_name: str, temperature: float = 0):
    """
    Factory to return a unified LLM interface.
    """
    # 1. Custom Modal / Self-Hosted / Novita (OpenAI Compatible)
    if provider in ["modal", "novita", "together", "deepseek"]:
        return ChatOpenAI(
            model=model_name,
            openai_api_key=os.getenv(f"{provider.upper()}_API_KEY"),
            openai_api_base=os.getenv(f"{provider.upper()}_BASE_URL"), # e.g., https://api.novita.ai/v3
            temperature=temperature,
            streaming=True
        )
    
    # 2. Native Google Gemini
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=temperature
        )
    
    # 3. Standard OpenAI
    elif provider == "openai":
        return ChatOpenAI(model=model_name, temperature=temperature)

    raise ValueError(f"Provider {provider} not supported.")

```

---

### 2. Standardizing Tool Calling

The biggest challenge with being "agnostic" isn't the text generation—it's **Tool Calling**. Gemini, OpenAI, and Llama (via vLLM) all handle tool schemas slightly differently.

To solve this, use LangChain's `.bind_tools()` method. It automatically converts your Python functions into the specific JSON schema the selected provider expects.

```python
# In your node definition:
def reasoner(state):
    # This comes from your config/variable
    llm = get_model(current_provider, current_model) 
    
    # Standardizes the tools for whatever model is currently active
    llm_with_tools = llm.bind_tools([read_only_sql, control_map, generate_echart])
    
    response = llm_with_tools.invoke(state['messages'])
    return {"messages": [response]}

```

---

### 3. The "Power User" Choice: LiteLLM

If you want to move beyond simple JSON configs and handle dozens of providers with a single API key and format, use **LiteLLM**. It acts as a universal bridge.

LangChain has a direct integration for it:

```python
from langchain_community.chat_models import ChatLiteLLM

# This single class can talk to 100+ providers
llm = ChatLiteLLM(
    model="together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1", # Provider/Model prefix
    api_key=os.getenv("TOGETHER_AI_API_KEY")
)

```

---

### 4. Architectural Data Flow

By using this factory, your architecture remains clean. Your LangGraph logic doesn't care if it's talking to a $405$B Llama model on Modal or a Flash model on Google; it just receives a `BaseMessage` and moves to the next node.

### 5. Deployment on Modal

Since you mentioned your own deployment on Modal, you can host an **Inference Engine** (like vLLM or TGI) on one Modal function and your **LangGraph Agent** on another.

* **Modal Inference:** Hosts the weights, provides an `/v1/chat/completions` endpoint.
* **Modal Agent:** Calls the inference endpoint using the `base_url` logic shown in Step 1.

---

### Summary of Benefits

* **Zero Logic Changes:** You can swap models mid-conversation if a specific query requires more "reasoning power."
* **Cost Control:** Use a cheap model (Gemini Flash) for simple QA and a heavy model (GPT-4o or Llama 3 70B) for complex SQL generation.
* **Future Proof:** If a new "SOTA" (State of the Art) model is released tomorrow, you just add one line to your JSON config.

**Would you like me to show you how to structure the JSON configuration file so it includes the `base_url` and `provider` mappings for this factory?**

# Streaming format
``` question
How to define the structured format for streaming
```

To provide a truly interactive experience where the user sees the agent "thinking" and the map moving in real-time, you should use **Server-Sent Events (SSE)**. Unlike standard WebSockets, SSE is easier to implement over HTTP, handles reconnections automatically, and is perfect for unidirectional data streaming from an AI.

Here is the structured architecture for your streaming protocol.

---

### 1. The Unified Stream Schema

Every chunk sent from your backend (Modal/Python) to your frontend (React) should follow a consistent JSON structure. This allows the frontend to distinguish between a "thought," a "tool result," and a "final answer."

```json
{
  "event": "status | chunk | tool_call | tool_output | ui_action | error",
  "data": {
    "content": "string (for text chunks)",
    "tool": "string (name of the tool)",
    "args": {},
    "result": {}, 
    "timestamp": "ISO-8601"
  }
}

```

---

### 2. Implementation: LangGraph `astream_events`

LangGraph's `astream_events` API is the gold standard for this. It emits events at every stage of the graph (when a node starts, when a tool is called, and when tokens are generated).

#### Backend (Python/Modal)

```python
from fastapi.responses import StreamingResponse

async def stream_agent_updates(user_input, conversation_id):
    # 'astream_events' version 2 provides granular control
    async for event in agent_app.astream_events(
        {"messages": [HumanMessage(content=user_input)]},
        version="v2"
    ):
        kind = event["event"]

        # 1. Capture LLM Reasoning/Text
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield f"data: {json.dumps({'event': 'chunk', 'data': {'content': content}})}\n\n"

        # 2. Capture Tool Calls (Start)
        elif kind == "on_tool_start":
            yield f"data: {json.dumps({'event': 'status', 'data': {'content': f'Executing {event['name']}...'}})}\n\n"

        # 3. Capture Tool Results (The Data)
        elif kind == "on_tool_end":
            tool_output = event["data"]["output"]
            # If the tool returned a map move or a chart, we flag it as a UI action
            event_type = "ui_action" if "action" in str(tool_output) else "tool_output"
            
            yield f"data: {json.dumps({'event': event_type, 'data': {'tool': event['name'], 'result': tool_output}})}\n\n"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(stream_agent_updates(request.message, request.id), media_type="text/event-stream")

```

---

### 3. Frontend: Handling the Stream in React

On the frontend, you need a way to "reduce" these incoming events into your UI state.

| Event Type | UI Response |
| --- | --- |
| **`status`** | Update a small "Agent Status" badge (e.g., "Querying Supabase..."). |
| **`chunk`** | Append text to the current AI message bubble. |
| **`tool_output`** | If it's SQL data, show a "Data retrieved" preview. |
| **`ui_action`** | Directly trigger `map.flyTo()` or update the ECharts component state. |

---

### 4. Special Case: ECharts & Mapbox

Because ECharts and Mapbox are heavy, you don't want to re-render them on every text token. Only trigger them when the `ui_action` event arrives.

* **For the Map:** Use a `useEffect` that listens to the latest `ui_action` in your chat state. If it contains `center` and `zoom`, call the Mapbox instance.
* **For Charts:** Your message component should check if a message has a `chart_options` property. If so, render the `<ReactECharts option={options} />` component inside the chat bubble.

---

### 5. Why this is modular

* **Separation of Concerns:** The LLM doesn't need to know *how* to move a map; it just needs to call a tool that returns a specific JSON structure.
* **Agnostic:** Whether you use Gemini or Llama 3 on Modal, as long as they call the tool, the streaming format remains identical.
* **UX:** The user sees immediate feedback (the "status" events) even if the SQL query takes 2 seconds to run.

Would you like me to provide the React hook implementation to parse and manage this stream state on the frontend?

# Freedom for charts
```question
Instead of having the model use a function to generate a chart, I want the agent (LLM) to write the entire JSON itself to be able to leverage the sheer power and customizability of Apache Echarts. The agent should:
- Reason whether the user could benefit from the chart (even if they haven't explicitly asked for one
- Plan how the chart should be constructed
- Write the SQL query to fetch properly formatted data (can even use different queries for itself and user-facing data)
- Retrieve a summary of the structure of the returned data (column, min/mx, etc.)
- Write the Apache Echarts JSON to construct the best chart (anything from a bar chart to a 3D scatter graph)
- Append the large data to it (usually in the data property under the series property)

For example, if the user asks "How has the frequency of extreme weather been in KPK last year?", the agent should answer like this:
"Sure! I can help with that! I'll check the database to uncover the trend of extreme weather event in Khyber Pakhtunkhwa in 2025."
(querying database)
(reading data)
(writing chart object)
(hydrating with data)
(moving map to KPK and highlighting)
"The frequency of extreme weather events in KPK in 2025 has been greater than the previous 5 years. Compared to 2024, the monsoon season.... Here is a stacked bar chart comparing the frequency of extreme weather events each month in KPK from 2025 and back:"

I want all this to be executed in an extremely clean manner following modern practices and LangGraph standards. I also want it to be extremely performant, with any form of parallelization if available.
```

This is a significant upgrade — you're giving the LLM full creative control over visualization, which is the right call for ECharts' depth. Here's the complete architecture.

---

## 1. Revised Agent State

The state needs to carry richer intermediate artifacts — data summaries, chart configs, and parallel UI actions.

````python
from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
import operator


class ChartArtifact(TypedDict):
    """A fully constructed ECharts option object with data hydrated."""
    chart_id: str
    options: dict  # The complete ECharts JSON
    summary: str   # Human-readable description of what the chart shows


class UIAction(TypedDict):
    """A command for the frontend to execute."""
    action: str    # "fly_to" | "highlight_geometry" | "render_chart"
    payload: dict


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    ui_actions: Annotated[List[UIAction], operator.add]
    
    # Intermediate data artifacts (set by tools, read by LLM)
    query_results: Optional[List[dict]]
    data_summary: Optional[dict]
    chart_artifact: Optional[ChartArtifact]
````

---

## 2. Revised Tool Definitions

Remove the `generate_echart` tool entirely. The LLM writes charts directly. But you still need tools for data retrieval, data inspection, and map control — plus a new tool to "publish" the final chart.

````python
from langchain_core.tools import tool
from typing import Optional
import json


@tool
def execute_sql(query: str) -> dict:
    """
    Execute a read-only SQL query against the REACH PostgreSQL database.
    Returns: { "columns": [...], "rows": [...], "row_count": int }
    
    Available tables:
      - alerts(id, severity, event_type, description, created_at, location_name, province, district, geom_id)
      - geometries(id, name, level, polygon, centroid, bbox)
      - weather_events(id, event_type, intensity, date, province, district, casualties, affected_pop)
      - admin_boundaries(id, name, level, province, geom)
    """
    from supabase_client import supabase
    
    forbidden = ["drop", "delete", "update", "insert", "alter", "truncate", "grant"]
    if any(kw in query.lower() for kw in forbidden):
        return {"error": "Write operations are not permitted."}
    
    try:
        result = supabase.rpc("execute_readonly_sql", {"query_text": query}).execute()
        rows = result.data or []
        columns = list(rows[0].keys()) if rows else []
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e)}


@tool
def summarize_data(columns: list[str], rows: list[dict]) -> dict:
    """
    Compute a statistical summary of query results so you can design the best chart.
    Returns min, max, unique counts, and sample values per column.
    Call this AFTER execute_sql to understand the shape of your data before writing ECharts JSON.
    """
    import statistics
    
    summary = {}
    for col in columns:
        values = [r.get(col) for r in rows if r.get(col) is not None]
        col_info = {"count": len(values), "nulls": len(rows) - len(values)}
        
        if values and isinstance(values[0], (int, float)):
            col_info["min"] = min(values)
            col_info["max"] = max(values)
            col_info["mean"] = round(statistics.mean(values), 2)
            col_info["sample"] = values[:3]
        else:
            unique = list(set(values))
            col_info["unique_count"] = len(unique)
            col_info["unique_values"] = unique[:15]  # Cap to avoid token bloat
            col_info["sample"] = values[:3]
        
        summary[col] = col_info
    
    return summary


@tool
def publish_chart(echart_options_json: str, description: str) -> dict:
    """
    Publish a fully constructed Apache ECharts options JSON object to the frontend.
    
    'echart_options_json': A COMPLETE, valid ECharts option object as a JSON string.
    This must include all data already embedded in the series[].data arrays.
    Do NOT use placeholder data — embed the real query results.
    
    'description': A short human-readable label for the chart.
    """
    try:
        options = json.loads(echart_options_json)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    
    return {
        "action": "render_chart",
        "payload": options,
        "description": description
    }


@tool
def control_map(
    action: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    zoom: Optional[float] = None,
    bbox: Optional[list[float]] = None,
    geometry_sql: Optional[str] = None
) -> dict:
    """
    Control the map view. Supports two modes:
    
    1. fly_to: Move camera. Provide lat, lon, zoom.
    2. highlight: Fetch and highlight a geometry. Provide geometry_sql 
       (a SELECT returning GeoJSON) and optionally bbox to fit bounds.
    
    Can combine both: fly + highlight in one call.
    """
    result = {"action": action}
    
    if lat is not None and lon is not None:
        result["center"] = [lon, lat]
        result["zoom"] = zoom or 8
    
    if bbox:
        result["bbox"] = bbox  # [west, south, east, north]
    
    if geometry_sql:
        from supabase_client import supabase
        try:
            geom = supabase.rpc("execute_readonly_sql", {"query_text": geometry_sql}).execute()
            result["geometry"] = geom.data
        except Exception as e:
            result["geometry_error"] = str(e)
    
    return result
````

---

## 3. The Graph: Nodes, Edges & Parallelism

This is the core. The key insight: **after the LLM decides it needs data + a map move, those can execute in parallel.** LangGraph supports this natively via `Send()`.

````python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from state import AgentState
from tools import execute_sql, summarize_data, publish_chart, control_map
from prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from llm_factory import get_model
import json

# All tools the agent can call
ALL_TOOLS = [execute_sql, summarize_data, publish_chart, control_map]


def build_agent(provider: str = "google", model_name: str = "gemini-2.5-pro"):
    
    llm = get_model(provider, model_name).bind_tools(ALL_TOOLS)
    
    # ── Node 1: Reasoner ───────────────────────────────────────────────
    def reasoner(state: AgentState) -> dict:
        """The LLM decides what to do next: call tools or respond."""
        prompt = [SystemMessage(content=SYSTEM_PROMPT)] + FEW_SHOT_EXAMPLES + state["messages"]
        response = llm.invoke(prompt)
        return {"messages": [response]}

    # ── Node 2: Tool Executor (parallel-safe) ──────────────────────────
    # LangGraph's built-in ToolNode automatically parallelizes 
    # multiple tool_calls in a single AIMessage.
    tool_node = ToolNode(ALL_TOOLS)

    # ── Node 3: Post-Tool Processing ──────────────────────────────────
    def process_tool_results(state: AgentState) -> dict:
        """
        After tools execute, inspect results and promote UI actions.
        This keeps the graph clean: tools return data, this node routes it.
        """
        ui_actions = []
        
        for msg in state["messages"]:
            if not isinstance(msg, ToolMessage):
                continue
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                continue
            
            # Promote chart publications to ui_actions
            if isinstance(content, dict) and content.get("action") == "render_chart":
                ui_actions.append({
                    "action": "render_chart",
                    "payload": content["payload"]
                })
            
            # Promote map commands to ui_actions
            if isinstance(content, dict) and content.get("action") in ("fly_to", "highlight"):
                ui_actions.append({
                    "action": content["action"],
                    "payload": content
                })
        
        return {"ui_actions": ui_actions}

    # ── Routing Logic ──────────────────────────────────────────────────
    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "end"

    # ── Build the Graph ────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    graph.add_node("reasoner", reasoner)
    graph.add_node("tools", tool_node)
    graph.add_node("process", process_tool_results)

    graph.set_entry_point("reasoner")

    graph.add_conditional_edges(
        "reasoner",
        should_continue,
        {"tools": "tools", "end": END}
    )
    
    # After tools execute → process results → back to reasoner
    graph.add_edge("tools", "process")
    graph.add_edge("process", "reasoner")

    return graph.compile()
````

### Graph Visualization

```
         ┌──────────┐
         │ reasoner │◄──────────────────┐
         └────┬─────┘                   │
              │                         │
        has tool_calls?                 │
        ┌─────┴─────┐                  │
       yes          no                  │
        │            │                  │
        ▼            ▼                  │
   ┌─────────┐    [END]                │
   │  tools   │  (parallel exec)       │
   └────┬─────┘                        │
        │                              │
        ▼                              │
   ┌──────────┐                        │
   │ process  │────────────────────────┘
   │ results  │  (extract UI actions)
   └──────────┘
```

**Parallelism happens automatically:** When the LLM returns a single `AIMessage` with multiple `tool_calls` (e.g., `execute_sql` + `control_map`), `ToolNode` executes them concurrently using `asyncio.gather`.

---

## 4. The System Prompt (ECharts-Native)

This is the most critical piece. The prompt must teach the LLM to be a **visualization designer**, not just a SQL runner.

````python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json

SYSTEM_PROMPT = """You are the REACH Analytics Agent — an expert data analyst and visualization designer for Pakistan's disaster management platform. You help users explore weather events, alerts, and geographic patterns through data, maps, and charts.

## YOUR WORKFLOW

When a user asks a question, follow this process:

### Step 1: Plan
Reason about what the user needs. Consider:
- Do they need raw data, a visual summary, or both?
- Would a chart help them even if they didn't ask for one? (Proactively suggest.)
- What chart type best represents this data? (time series → line, comparison → bar, distribution → scatter, composition → pie/stacked bar, geospatial → map highlight)

### Step 2: Query
Write SQL to fetch the data you need. You may issue MULTIPLE queries:
- One optimized for chart consumption (aggregated, sorted, formatted)
- One for the textual summary you'll give the user

### Step 3: Inspect
ALWAYS call `summarize_data` after `execute_sql`. You must understand the shape, range, and distribution of data before designing a chart. Never skip this step.

### Step 4: Design & Publish the Chart
Using `publish_chart`, write a COMPLETE Apache ECharts options JSON object. You have the full power of ECharts — use it:
- Bar, line, scatter, pie, radar, heatmap, boxplot, treemap, stacked bar, multi-axis, 3D scatter — whatever fits best.
- Embed the REAL data directly into `series[].data`.
- Always include: title, tooltip, legend (if multi-series), axis labels, and a color palette.
- For time series: use `xAxis.type: "time"`.
- For large datasets (>100 rows): consider using `dataZoom` for interactivity.

### Step 5: Map Control
If the question involves a specific location, province, or district:
- Call `control_map` to fly the camera there.
- If you want to highlight a boundary, provide a `geometry_sql` that returns GeoJSON.
- You can call `control_map` IN PARALLEL with `execute_sql` to save time.

### Step 6: Respond
Write a clear, concise textual answer. Reference the chart. Explain key insights.

## DATABASE SCHEMA

```sql
-- Weather events recorded across Pakistan
weather_events(
    id SERIAL PRIMARY KEY,
    event_type TEXT,        -- 'flood', 'heatwave', 'earthquake', 'cyclone', 'drought', 'landslide'
    intensity TEXT,         -- 'low', 'moderate', 'severe', 'extreme'  
    date DATE,
    province TEXT,          -- 'KPK', 'Sindh', 'Punjab', 'Balochistan', 'GB', 'AJK', 'ICT'
    district TEXT,
    casualties INT,
    affected_pop INT
)

-- Active alerts
alerts(
    id SERIAL PRIMARY KEY,
    severity TEXT,          -- 'low', 'medium', 'high', 'critical'
    event_type TEXT,
    description TEXT,
    created_at TIMESTAMPTZ,
    location_name TEXT,
    province TEXT,
    district TEXT,
    geom_id UUID
)

-- Administrative geometries
geometries(
    id UUID PRIMARY KEY,
    name TEXT,
    level TEXT,             -- 'province', 'district', 'tehsil'
    polygon GEOMETRY,       -- PostGIS
    centroid GEOMETRY,
    bbox FLOAT[]            -- [west, south, east, north]
)

-- Use ST_AsGeoJSON(polygon) to retrieve GeoJSON for map highlighting.
-- Use ST_X(centroid), ST_Y(centroid) for lat/lon coordinates.
```

## ECHARTS DESIGN RULES

1. Color palette for severity: ["#52c41a", "#faad14", "#ff7a45", "#f5222d"] (low → critical)
2. Color palette for general series: ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de", "#3ba272"]
3. Always set `tooltip.trigger` appropriately ("axis" for cartesian, "item" for pie/scatter).
4. For stacked charts, set `stack: "total"` on each series.
5. For responsive design, include `grid: { containLabel: true }`.
6. Always format dates as "MMM YYYY" or "YYYY-MM" for readability.
7. For charts with many categories, use `xAxis.axisLabel.rotate: 45`.
8. Include `dataZoom: [{ type: "inside" }, { type: "slider" }]` for datasets with >12 x-axis points.

## IMPORTANT CONSTRAINTS

- NEVER fabricate data. Every number in a chart must come from a query result.
- NEVER call `publish_chart` without first calling `execute_sql` and `summarize_data`.
- You may call `execute_sql` and `control_map` in the SAME tool_calls array (they run in parallel).
- Keep textual responses concise. Let the chart do the heavy lifting.
- If a query returns 0 rows, tell the user clearly — do not generate an empty chart.
"""


# ── Few-Shot Examples ──────────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    # ── Turn 1: User asks about weather frequency ──
    HumanMessage(content="How has the frequency of extreme weather been in KPK last year?"),
    
    AIMessage(
        content="I'll analyze the trend of extreme weather events in Khyber Pakhtunkhwa throughout 2025. Let me query the data and prepare a visualization.",
        tool_calls=[
            {
                "id": "call_sql_1",
                "name": "execute_sql",
                "args": {
                    "query": """
                        SELECT 
                            TO_CHAR(date, 'YYYY-MM') AS month,
                            event_type,
                            COUNT(*) AS event_count
                        FROM weather_events
                        WHERE province = 'KPK'
                          AND date >= '2025-01-01' AND date < '2026-01-01'
                          AND intensity IN ('severe', 'extreme')
                        GROUP BY month, event_type
                        ORDER BY month, event_type
                    """
                }
            },
            {
                "id": "call_map_1",
                "name": "control_map",
                "args": {
                    "action": "highlight",
                    "lat": 34.5,
                    "lon": 71.5,
                    "zoom": 7,
                    "bbox": [69.0, 31.0, 74.0, 37.0],
                    "geometry_sql": "SELECT ST_AsGeoJSON(polygon) as geojson FROM geometries WHERE name = 'Khyber Pakhtunkhwa' AND level = 'province'"
                }
            }
        ]
    ),
    
    ToolMessage(content=json.dumps({
        "columns": ["month", "event_type", "event_count"],
        "rows": [
            {"month": "2025-01", "event_type": "flood", "event_count": 2},
            {"month": "2025-01", "event_type": "landslide", "event_count": 1},
            {"month": "2025-03", "event_type": "earthquake", "event_count": 1},
            {"month": "2025-06", "event_type": "heatwave", "event_count": 3},
            {"month": "2025-07", "event_type": "flood", "event_count": 8},
            {"month": "2025-07", "event_type": "landslide", "event_count": 4},
            {"month": "2025-08", "event_type": "flood", "event_count": 12},
            {"month": "2025-08", "event_type": "landslide", "event_count": 6},
            {"month": "2025-09", "event_type": "flood", "event_count": 5},
            {"month": "2025-10", "event_type": "drought", "event_count": 2},
        ],
        "row_count": 10
    }), tool_call_id="call_sql_1"),
    
    ToolMessage(content=json.dumps({
        "action": "highlight",
        "center": [71.5, 34.5],
        "zoom": 7,
        "bbox": [69.0, 31.0, 74.0, 37.0],
        "geometry": [{"geojson": "{...}"}]
    }), tool_call_id="call_map_1"),
    
    # ── Turn 2: Agent inspects the data ──
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_summary_1",
            "name": "summarize_data",
            "args": {
                "columns": ["month", "event_type", "event_count"],
                "rows": [
                    {"month": "2025-01", "event_type": "flood", "event_count": 2},
                    {"month": "2025-01", "event_type": "landslide", "event_count": 1},
                    {"month": "2025-03", "event_type": "earthquake", "event_count": 1},
                    {"month": "2025-06", "event_type": "heatwave", "event_count": 3},
                    {"month": "2025-07", "event_type": "flood", "event_count": 8},
                    {"month": "2025-07", "event_type": "landslide", "event_count": 4},
                    {"month": "2025-08", "event_type": "flood", "event_count": 12},
                    {"month": "2025-08", "event_type": "landslide", "event_count": 6},
                    {"month": "2025-09", "event_type": "flood", "event_count": 5},
                    {"month": "2025-10", "event_type": "drought", "event_count": 2}
                ]
            }
        }]
    ),
    
    ToolMessage(content=json.dumps({
        "month": {"count": 10, "unique_count": 7, "unique_values": ["2025-01","2025-03","2025-06","2025-07","2025-08","2025-09","2025-10"]},
        "event_type": {"count": 10, "unique_count": 5, "unique_values": ["flood","landslide","earthquake","heatwave","drought"]},
        "event_count": {"count": 10, "min": 1, "max": 12, "mean": 4.2}
    }), tool_call_id="call_summary_1"),
    
    # ── Turn 3: Agent writes and publishes the chart ──
    AIMessage(
        content="",
        tool_calls=[{
            "id": "call_chart_1",
            "name": "publish_chart",
            "args": {
                "description": "Stacked bar chart of severe/extreme weather events in KPK by month (2025)",
                "echart_options_json": json.dumps({
                    "title": {"text": "Extreme Weather Events in KPK (2025)", "subtext": "Severe & Extreme intensity", "left": "center"},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "legend": {"bottom": 0},
                    "grid": {"containLabel": True, "bottom": 60},
                    "xAxis": {"type": "category", "data": ["Jan", "Mar", "Jun", "Jul", "Aug", "Sep", "Oct"], "axisLabel": {"rotate": 0}},
                    "yAxis": {"type": "value", "name": "Event Count"},
                    "color": ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de"],
                    "dataZoom": [{"type": "inside"}, {"type": "slider"}],
                    "series": [
                        {"name": "Flood", "type": "bar", "stack": "total", "data": [2, 0, 0, 8, 12, 5, 0]},
                        {"name": "Landslide", "type": "bar", "stack": "total", "data": [1, 0, 0, 4, 6, 0, 0]},
                        {"name": "Earthquake", "type": "bar", "stack": "total", "data": [0, 1, 0, 0, 0, 0, 0]},
                        {"name": "Heatwave", "type": "bar", "stack": "total", "data": [0, 0, 3, 0, 0, 0, 0]},
                        {"name": "Drought", "type": "bar", "stack": "total", "data": [0, 0, 0, 0, 0, 0, 2]}
                    ]
                })
            }
        }]
    ),
    
    ToolMessage(content=json.dumps({
        "action": "render_chart",
        "payload": {"title": {"text": "..."}},
        "description": "Stacked bar chart of severe/extreme weather events in KPK by month (2025)"
    }), tool_call_id="call_chart_1"),
    
    # ── Turn 4: Final response ──
    AIMessage(content="""The frequency of extreme weather events in KPK during 2025 shows a dramatic spike during the monsoon season (July–August), with **floods** being the dominant event type at 25 total occurrences.

**Key findings:**
- **August 2025** was the most severe month with 18 events (12 floods + 6 landslides)
- Floods and landslides account for **86%** of all severe/extreme events
- The monsoon corridor (Jul–Sep) concentrated **78%** of the year's extreme events

I've highlighted KPK on the map and attached a stacked bar chart showing the monthly breakdown by event type."""),
]
````

---

## 5. Streaming Endpoint

````python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from graph import build_agent
from langchain_core.messages import HumanMessage
import json

app = FastAPI()
agent = build_agent(provider="google", model_name="gemini-2.5-pro")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


async def stream_events(user_message: str):
    input_state = {
        "messages": [HumanMessage(content=user_message)],
        "ui_actions": [],
        "query_results": None,
        "data_summary": None,
        "chart_artifact": None,
    }
    
    async for event in agent.astream_events(input_state, version="v2"):
        kind = event["event"]
        
        # ── LLM text tokens ──
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield f"data: {json.dumps({'event': 'chunk', 'data': {'content': chunk.content}})}\n\n"
        
        # ── Tool execution starts ──
        elif kind == "on_tool_start":
            tool_name = event["name"]
            # Don't leak raw SQL/JSON to user — provide a friendly status
            status_map = {
                "execute_sql": "Querying database...",
                "summarize_data": "Analyzing data structure...",
                "publish_chart": "Rendering visualization...",
                "control_map": "Updating map view...",
            }
            yield f"data: {json.dumps({'event': 'status', 'data': {'tool': tool_name, 'content': status_map.get(tool_name, 'Processing...')}})}\n\n"
        
        # ── Tool execution ends ──
        elif kind == "on_tool_end":
            tool_name = event["name"]
            output = event["data"]["output"]
            
            try:
                parsed = json.loads(output) if isinstance(output, str) else output
            except (json.JSONDecodeError, TypeError):
                parsed = output
            
            # Route chart and map actions to the frontend as UI commands
            if isinstance(parsed, dict):
                action = parsed.get("action")
                
                if action == "render_chart":
                    yield f"data: {json.dumps({'event': 'ui_action', 'data': {'action': 'render_chart', 'payload': parsed['payload'], 'description': parsed.get('description', '')}})}\n\n"
                
                elif action in ("fly_to", "highlight"):
                    yield f"data: {json.dumps({'event': 'ui_action', 'data': parsed})}\n\n"
                
                else:
                    # Data tool results — send a compact summary, not raw rows
                    row_count = parsed.get("row_count")
                    if row_count is not None:
                        yield f"data: {json.dumps({'event': 'data_preview', 'data': {'row_count': row_count, 'columns': parsed.get('columns', [])}})}\n\n"
    
    yield "data: [DONE]\n\n"


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        stream_events(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Prevents nginx from buffering SSE
        }
    )
````

---

## 6. Key Design Decisions Explained

### Why `summarize_data` exists as a separate tool

Without it, the LLM must ingest potentially hundreds of raw rows to understand the data shape before writing the chart JSON. The `summarize_data` tool gives it a compressed statistical view (column types, min/max, unique values) so it can **design the chart intelligently** without consuming its entire context window on raw data.

The flow is always: `execute_sql` → `summarize_data` → `publish_chart`.

### Why `publish_chart` and not a direct JSON response

By making it a tool call, you get:
1. **Validation** — The tool parses the JSON and catches malformed ECharts before it reaches the frontend.
2. **Clean streaming** — The `on_tool_end` event for `publish_chart` is unambiguously a chart, making frontend routing trivial.
3. **Audit trail** — Every chart ever generated is stored as a `ToolMessage` in the conversation history.

### Parallelism

When the agent decides it needs both data and a map move, it returns **one** `AIMessage` with two `tool_calls`:

```json
{
  "tool_calls": [
    { "name": "execute_sql", "args": { "query": "SELECT ..." } },
    { "name": "control_map", "args": { "action": "fly_to", "lat": 34.5, "lon": 71.5 } }
  ]
}
```

`ToolNode` runs both concurrently. The user sees the map fly to KPK **while** the database query is executing. This is native LangGraph behavior — no extra code needed.

### Data hydration strategy

The LLM receives the full `rows` array in the `ToolMessage` from `execute_sql`. When it writes the `publish_chart` JSON, it must **embed the real numbers** into `series[].data`. The system prompt explicitly forbids placeholders. This keeps the chart a single, self-contained artifact that the frontend can render without any additional data-fetching.

For large datasets (>500 rows), you could add pagination to `execute_sql` or have the LLM write a more aggregated query. The `summarize_data` step helps it decide whether aggregation is needed.
