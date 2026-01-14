"""
Geocoder - FastAPI Application

Main entry point for the geocoding microservice.
This module can be run from the Backend directory.

Usage:
    python -m geocoder
    or
    uvicorn geocoder:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from geocoding.api import router
from geocoding.dependencies import cleanup_services
from geocoding.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Startup:
    - Log configuration
    - Verify settings loaded
    
    Shutdown:
    - Cleanup services
    - Clear caches
    """
    # Startup
    logger.info("Starting Geocoding Microservice...")
    settings = get_settings()
    logger.info(f"Supabase URL: {settings.supabase_url}")
    logger.info(f"LocationIQ API configured: {'Yes' if settings.locationiq_api_key else 'No'}")
    logger.info(f"Fuzzy match threshold: {settings.fuzzy_match_threshold}")
    logger.info("Service ready to accept requests")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Geocoding Microservice...")
    await cleanup_services()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Geocoding Microservice",
    description="""
    Geocoding service for converting location references from disaster alerts into 
    standardized place IDs from Pakistan's administrative boundary hierarchy.
    
    ## Features
    
    * **Simple name resolution**: Fuzzy matching for place names
    * **Directional processing**: Handle descriptions like "Central Sindh"
    * **Fallback geocoding**: External API integration for unknown places
    * **Hierarchical aggregation**: Optimize results by parent-child relationships
    
    ## Match Methods
    
    * `exact_name`: Perfect string match
    * `fuzzy_name`: Trigram similarity matching (pg_trgm)
    * `point_in_polygon`: PostGIS spatial lookup
    * `directional_intersection`: Spatial grid intersection
    
    ## Performance
    
    * O(log n) database queries via GIN/GIST indexes
    * Multi-level caching (in-memory LRU)
    * Async/await for non-blocking I/O
    * Connection pooling for external APIs
    
    ## Simple Batch Interface
    
    Use `GeocodingService.geocode_batch_simple()` for a simple list-to-list interface:
    ```python
    from geocoding import get_geocoding_service
    
    service = get_geocoding_service()
    place_names = ["Islamabad", "Lahore", "Karachi"]
    place_ids = await service.geocode_batch_simple(place_names)
    # Returns: ["uuid-1", "uuid-2", "uuid-3"]
    ```
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with service information.
    """
    return {
        "service": "Geocoding Microservice",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested endpoint does not exist",
            "docs": "/docs"
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Custom 500 handler"""
    logger.error(f"Internal error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn
    uvicorn.run(
        "geocoder:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Disable in production
        log_level="info"
    )
