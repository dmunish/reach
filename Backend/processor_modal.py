import asyncio
import modal
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os

#################################################
# AUTH & MODELS
#################################################

auth_scheme = HTTPBearer()

class ProcessRequest(BaseModel):
    limit: int = 3
    worker_count: int = 1

class ProcessResponse(BaseModel):
    status: str
    message: str
    worker_count: int

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
        "python-dotenv",
        "beautifulsoup4",
        "pandas",
        "openai",
        "PyMuPDF",
        "pillow"
    )
    .add_local_dir("processing_engine", remote_path="/root/processing_engine")
    .add_local_file("utils.py", remote_path="/root/utils.py")
    .add_local_file("processor.py", remote_path="/root/processor.py")
)

app = modal.App(name="reach-processor", image=image)

#################################################
# BACKGROUND WORKER FUNCTION
#################################################

@app.function(
    secrets=[modal.Secret.from_name("reach-secrets")],
    timeout=86400 # 24 hours
)
async def process_jobs(limit: int = 3):
    """
    Process jobs from the queue.
    """
    from processor import process
    return await process(limit=limit)

#################################################
# WEB ENDPOINT (Authentication & Job Spawning)
#################################################

@app.function(secrets=[modal.Secret.from_name("reach-secrets")])
@modal.fastapi_endpoint(method="POST")
async def trigger_processing(
    token: HTTPAuthorizationCredentials = Depends(auth_scheme),
    request: ProcessRequest = ProcessRequest()
) -> ProcessResponse:
    """
    FastAPI endpoint that authenticates requests and spawns background jobs.
    Returns immediately without waiting for job completion.
    """
    # Validate authentication
    if token.credentials != os.environ.get("SECRET_KEY"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Spawn background workers (non-blocking)
    worker_ids = []
    for _ in range(request.worker_count):
        call = await process_jobs.spawn.aio(limit=request.limit)
        worker_ids.append(call.object_id)
    
    return ProcessResponse(
        status="accepted",
        message=f"Spawned {request.worker_count} workers with IDs: {', '.join(worker_ids)}",
        worker_count=request.worker_count
    )

#################################################
# OPTIONAL: Status Check Endpoint
#################################################

@app.function()
@modal.fastapi_endpoint(method="GET")
async def health() -> dict:
    """Health check endpoint"""
    return {"status": "healthy", "service": "reach-processor"}

# @app.local_entrypoint()
# def main():
#     call = process_jobs.spawn(limit=2)
#     print(f"Spawned job with ID: {call.object_id}")