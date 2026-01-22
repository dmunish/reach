from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from ..models import GeocodeRequest, GeocodeResponse, GeocodeResult
from ..services.geocoding_service import GeocodingService
from ..dependencies import get_geocoding_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["geocoding"]
)


@router.post(
    "/geocode",
    response_model=GeocodeResponse,
    status_code=status.HTTP_200_OK,
    summary="Geocode location strings to place IDs",
    description="""
    Convert location references (place names, directional descriptions) into 
    standardized place IDs from Pakistan's administrative boundary hierarchy.
    
    **Examples:**
    - Simple: "Islamabad" → Returns place ID for Islamabad
    - Directional: "Central Sindh" → Returns place IDs in central region of Sindh
    - Multiple: "Northern Gilgit-Baltistan and KPK" → Returns places in northern regions
    
    **Match Methods:**
    - `exact_name`: Perfect string match
    - `fuzzy_name`: Close match using trigram similarity
    - `point_in_polygon`: Matched via coordinates lookup
    - `directional_intersection`: Matched via spatial intersection with directional grid
    """
)
async def geocode_locations(
    request: GeocodeRequest,
    service: GeocodingService = Depends(get_geocoding_service)
) -> GeocodeResponse:
    """
    Geocode one or more location strings.
    
    Args:
        request: GeocodeRequest with locations list and options
        service: Injected GeocodingService instance
        
    Returns:
        GeocodeResponse with results for each location
        
    Raises:
        HTTPException: If validation fails or internal error occurs
    """
    try:
        logger.info(f"Geocoding request for {len(request.locations)} location(s)")
        
        # Process batch of locations
        results = await service.geocode_batch(
            request.locations,
            request.options
        )
        
        # Separate errors from results
        errors = []
        for result in results:
            if result.error and not result.matched_places:
                errors.append(f"{result.input}: {result.error}")
        
        # Log summary
        success_count = len([r for r in results if r.matched_places])
        logger.info(
            f"Geocoding complete: {success_count}/{len(results)} successful, "
            f"{len(errors)} errors"
        )
        
        return GeocodeResponse(
            results=results,
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"Geocoding request failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during geocoding"
        )


@router.get(
    "/geocode/{location}",
    response_model=GeocodeResponse,
    status_code=status.HTTP_200_OK,
    summary="Geocode a single location (GET method)",
    description="Simple GET endpoint for geocoding a single location. For batch processing, use POST."
)
async def geocode_single_location(
    location: str,
    prefer_lower_admin_levels: bool = True,
    include_confidence_scores: bool = False,
    service: GeocodingService = Depends(get_geocoding_service)
) -> GeocodeResponse:
    """
    Geocode a single location via GET request.
    
    Args:
        location: Location string to geocode
        prefer_lower_admin_levels: Prefer more specific places when scores are similar
        include_confidence_scores: Include confidence scores in response
        service: Injected GeocodingService instance
        
    Returns:
        GeocodeResponse with single result
    """
    try:
        from ..models import GeocodeOptions
        
        options = GeocodeOptions(
            prefer_lower_admin_levels=prefer_lower_admin_levels,
            include_confidence_scores=include_confidence_scores
        )
        
        logger.info(f"GET geocoding request for: {location}")
        
        result = await service.geocode_location(location, options, None)
        
        errors = []
        if result.error and not result.matched_places:
            errors.append(f"{result.input}: {result.error}")
        
        return GeocodeResponse(
            results=[result],
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"Single geocoding request failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during geocoding"
        )


@router.get(
    "/suggest/{location}",
    summary="Get alternative suggestions for a location",
    description="Useful when a location fails to match - returns similar place names."
)
async def suggest_locations(
    location: str,
    limit: int = 3,
    service: GeocodingService = Depends(get_geocoding_service)
):
    """
    Get alternative suggestions for a location string.
    
    Args:
        location: Location string to find suggestions for
        limit: Maximum number of suggestions to return
        service: Injected GeocodingService instance
        
    Returns:
        List of suggested places with similarity scores
    """
    try:
        suggestions = await service.suggest_alternatives(location, limit)
        
        return {
            "input": location,
            "suggestions": [
                {
                    "name": s['name'],
                    "hierarchy_level": s['hierarchy_level'],
                    "similarity_score": s.get('similarity_score')
                }
                for s in suggestions
            ]
        }
        
    except Exception as e:
        logger.error(f"Suggestion request failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error fetching suggestions"
        )


@router.get(
    "/health",
    summary="Health check endpoint",
    description="Check if the geocoding service is running and healthy."
)
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": "geocoding-microservice",
        "version": "1.0.0"
    }
