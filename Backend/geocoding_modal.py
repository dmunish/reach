"""
Geocoding Modal Endpoint

Modal.com deployment for the geocoding microservice.
Provides a web endpoint that accepts a list of place names and returns their IDs.

Features:
    - Parallel processing with Modal's container scaling
    - Async Supabase client for non-blocking I/O
    - Chunked batch processing for large requests
    - Concurrent request handling
    - Bearer token authentication

Usage:
    modal deploy geocoding_modal.py
    
    # Geocode locations (matches local API format)
    curl -X POST "https://[your-modal-url]/geocode" \
      --header "Authorization: Bearer YOUR_SECRET_KEY" \
      --header "Content-Type: application/json" \
      --data '{"locations": ["Islamabad", "Lahore", "Karachi"]}'
    
    # Response: {"place_ids": ["uuid-1", "uuid-2", "uuid-3"], "count": 3, "matched": 3}
"""

import modal
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import asyncio

#################################################
# CONFIGURATION
#################################################

# Batch processing configuration
CHUNK_SIZE = 50  # Number of places to process per container
MAX_CONCURRENT_CHUNKS = 20  # Maximum parallel containers (increased for better scaling)
CONTAINER_TIMEOUT = 300  # 5 minutes per container
MAX_CONCURRENT_REQUESTS = 200  # Maximum concurrent HTTP requests per container

#################################################
# AUTH & MODELS
#################################################

auth_scheme = HTTPBearer()


class GeocodeRequest(BaseModel):
    """Request model for geocoding endpoint - matches local API format"""
    locations: List[str] = Field(
        ..., 
        description="List of location strings to geocode",
        min_length=1,
        max_length=1000,
        examples=[["Islamabad", "Lahore", "Central Sindh"]]
    )


class GeocodeResponse(BaseModel):
    """Response model - flat list of place IDs"""
    place_ids: List[str] = Field(
        description="List of place IDs corresponding to input locations. Empty string if no match found.",
        examples=[["a48ab3ed-ed9d-404d-86df-753521a6aba9", "e6303363-edbb-4b31-8d7b-19c8bbae2e33"]]
    )
    count: int = Field(
        description="Total number of locations processed",
        examples=[3]
    )
    matched: int = Field(
        description="Number of locations successfully matched",
        examples=[3]
    )
    errors: Optional[List[str]] = Field(
        default=None,
        description="List of error messages if any locations failed"
    )


#################################################
# IMAGE & APP SETUP
#################################################

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.100.0",
        "uvicorn",
        "supabase>=2.0.0",
        "python-dotenv",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "httpx>=0.25.0",
        "rapidfuzz>=3.0.0",
        "geopy>=2.4.0",
    )
    .add_local_dir("geocoding", remote_path="/root/geocoding")
)

app = modal.App(name="reach-geocoder", image=image)


#################################################
# GEOCODING WORKER FUNCTION
#################################################

@app.function(
    secrets=[modal.Secret.from_name("reach-secrets")],
    timeout=CONTAINER_TIMEOUT,
    memory=512,  # MB - lightweight for I/O bound work
    cpu=0.5,  # Fractional CPU since mostly network I/O
    retries=2,  # Auto-retry on transient failures
    concurrency_limit=MAX_CONCURRENT_CHUNKS,  # Limit parallel containers
)
async def geocode_chunk(locations: List[str]) -> List[str]:
    """
    Worker function that geocodes a chunk of locations.
    
    Each invocation runs in its own Modal container, enabling
    parallel processing of large batches.
    
    Uses async Supabase client for non-blocking database I/O.
    
    Args:
        locations: List of location strings to geocode
        
    Returns:
        List of place ID strings (empty string if no match)
    """
    import sys
    sys.path.insert(0, "/root")
    
    import logging
    from geocoding import get_async_geocoding_service
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Processing chunk of {len(locations)} locations")
        
        # Use async service for non-blocking I/O
        service = await get_async_geocoding_service()
        place_ids = await service.geocode_batch_simple(locations)
        
        matched = len([id for id in place_ids if id])
        logger.info(f"Chunk complete: {matched}/{len(locations)} matched")
        
        return place_ids
        
    except Exception as e:
        logger.error(f"Chunk geocoding error: {e}", exc_info=True)
        return [""] * len(locations)


#################################################
# BATCH ORCHESTRATION
#################################################

def chunk_list(lst: List[str], chunk_size: int) -> List[List[str]]:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


async def geocode_batch_parallel(locations: List[str]) -> List[str]:
    """
    Orchestrate parallel geocoding across multiple Modal containers.
    
    Strategy:
    1. Split locations into chunks
    2. Dispatch chunks to parallel containers
    3. Collect and merge results maintaining order
    
    Args:
        locations: Full list of locations to geocode
        
    Returns:
        Merged list of place IDs in original order
    """
    if not locations:
        return []
    
    # For small batches, process directly
    if len(locations) <= CHUNK_SIZE:
        return await geocode_chunk.remote.aio(locations)
    
    # Split into chunks for parallel processing
    chunks = chunk_list(locations, CHUNK_SIZE)
    
    # Dispatch all chunks in parallel using Modal's starmap
    # This spawns multiple containers simultaneously
    results = []
    async for chunk_result in geocode_chunk.map.aio(chunks):
        results.append(chunk_result)
    
    # Flatten results maintaining order
    return [place_id for chunk_result in results for place_id in chunk_result]


#################################################
# WEB ENDPOINTS
#################################################

@app.function(
    secrets=[modal.Secret.from_name("reach-secrets")],
    allow_concurrent_inputs=MAX_CONCURRENT_REQUESTS,  # Handle many concurrent HTTP requests
    container_idle_timeout=120,  # Keep container warm for 2 minutes
)
@modal.fastapi_endpoint(method="POST")
async def geocode(
    request: GeocodeRequest,
    token: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> GeocodeResponse:
    """
    Geocode location strings to place IDs.
    
    Accepts a list of location strings and returns their corresponding 
    place IDs from Pakistan's administrative boundary hierarchy.
    
    **Input format matches local API:**
    ```json
    {"locations": ["Islamabad", "Lahore", "Central Sindh"]}
    ```
    
    **Output is a flat list of IDs:**
    ```json
    {
        "place_ids": ["uuid-1", "uuid-2", "uuid-3"],
        "count": 3,
        "matched": 3
    }
    ```
    
    Features:
    - Automatic parallel processing for large batches
    - Fuzzy name matching
    - Directional descriptions (e.g., "Central Sindh")
    - Fallback external geocoding
    
    Args:
        request: GeocodeRequest with locations list
        token: Bearer token for authentication
        
    Returns:
        GeocodeResponse with flat list of place IDs
    """
    # Validate authentication
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key or token.credentials != secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Process with parallel batch orchestration
        place_ids = await geocode_batch_parallel(request.locations)
        
        matched_count = len([id for id in place_ids if id])
        
        return GeocodeResponse(
            place_ids=place_ids,
            count=len(place_ids),
            matched=matched_count,
            errors=None
        )
        
    except Exception as e:
        # Return partial results with error info
        return GeocodeResponse(
            place_ids=[""] * len(request.locations),
            count=len(request.locations),
            matched=0,
            errors=[str(e)]
        )


@app.function()
@modal.fastapi_endpoint(method="GET")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "reach-geocoder",
        "version": "1.0.0",
        "config": {
            "chunk_size": CHUNK_SIZE,
            "max_concurrent_chunks": MAX_CONCURRENT_CHUNKS
        }
    }


#################################################
# CLI ENTRY POINT (for local testing)
#################################################

@app.local_entrypoint()
def main():
    """
    Local testing entrypoint.
    
    Usage:
        modal run geocoding_modal.py
    """
    import asyncio
    
    test_locations = ["Islamabad", "Lahore", "Karachi", "Central Sindh"]
    print(f"Testing geocoding for: {test_locations}")
    
    result = geocode_chunk.remote(test_locations)
    print(f"Results: {result}")
    
    matched = len([id for id in result if id])
    print(f"Matched: {matched}/{len(test_locations)}")
