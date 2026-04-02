import modal

#################################################
# IMAGE & APP SETUP
#################################################

image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi",
        "uvicorn",
        "httpx",
        "supabase",
        "PyJWT",
        "python-dotenv",
        "pydantic",
        "langchain",
        "langchain_core",
        "langchain_openai",
        "langgraph",
        "pytz"
    )
    .add_local_dir("agents", remote_path="/root/agents")
    .add_local_file("utils.py", remote_path="/root/utils.py")
    .add_local_file("agent.py", remote_path="/root/agent.py")
)

app = modal.App(name="reach-agent", image=image)

#################################################
# WEB ENDPOINT (FastAPI Integration)
#################################################

@app.function(
    secrets=[modal.Secret.from_name("reach-secrets")],
    keep_warm=1,  # Keep at least one instance warm for low latency
    timeout=600   # 10 minutes timeout for long LLM generation
)
@modal.asgi_app()
def fastapi_app():
    """
    Mount the entire FastAPI app from agent.py.
    This preserves the CORS middleware, streaming responses, and all routes.
    """
    from agent import app as reach_agent_app
    return reach_agent_app

