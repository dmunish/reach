from typing import Dict, List, Tuple, Optional
import httpx
import hashlib
import logging
import asyncio

from .redis_cache import get_redis_cache

logger = logging.getLogger(__name__)

class ExternalGeocoder:
    """
    External geocoding service client with intelligent caching and disambiguation.
    
    Optimizations:
    - Redis distributed cache with TTL to minimize API calls
    - Connection pooling via shared httpx.AsyncClient
    - Batch request support for parallel geocoding
    - Spatial disambiguation using centroid calculation
    """
    
    def __init__(self, api_key: str, base_url: str, cache_ttl_days: int = 30, max_cache_size: int = 1000):
        self.api_key = api_key
        self.base_url = base_url
        self.cache_ttl_seconds = int(cache_ttl_days * 86400)  # Convert to seconds for Redis
        self.max_cache_size = max_cache_size  # Not used with Redis but kept for compatibility
        self._client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry - initialize persistent HTTP client"""
        self._client = httpx.AsyncClient(timeout=10.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_cache_key(self, location: str, country_filter: str = "pk") -> str:
        """Generate cache key from location string and country filter"""
        # Include country in cache key to handle different country queries
        return f"{location.lower()}:{country_filter}"
    
    async def geocode(
        self, 
        location: str,
        country_filter: str = "pk"  # Pakistan only
    ) -> List[Tuple[float, float]]:
        """
        Geocode a location string to coordinates.
        NOW WITH REDIS CACHING.
        
        Args:
            location: Place name to geocode
            country_filter: ISO country code filter (default: 'pk' for Pakistan)
            
        Returns:
            List of (longitude, latitude) tuples, ordered by relevance
        """
        # Try Redis cache first
        cache = get_redis_cache()
        cache_key = self._get_cache_key(location, country_filter)
        
        if cache:
            cached_result = await cache.get("external_geocode", cache_key)
            if cached_result is not None:
                logger.debug(f"✅ External geocode cache HIT for '{location}'")
                # Convert list of lists back to list of tuples
                return [tuple(coord) for coord in cached_result]
        
        # Make API request
        try:
            # Use persistent client if available (via context manager), else create temporary one
            client = self._client if self._client else httpx.AsyncClient(timeout=10.0)
            
            try:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={
                        'key': self.api_key,
                        'q': location,
                        'format': 'json',
                        'countrycodes': country_filter,
                        'limit': 5
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    logger.warning(f"No geocoding results for '{location}'")
                    return []
                
                # Extract coordinates (lon, lat)
                coords = [(float(r['lon']), float(r['lat'])) for r in data if 'lon' in r and 'lat' in r]
                
                # Cache results in Redis
                if cache and coords:
                    # Convert tuples to lists for JSON serialization
                    coords_serializable = [list(coord) for coord in coords]
                    await cache.set("external_geocode", cache_key, coords_serializable, ttl_seconds=self.cache_ttl_seconds)
                    logger.debug(f"💾 External geocode cache SET for '{location}'")
                
                return coords
                
            finally:
                # Close client only if we created it temporarily
                if self._client is None:
                    await client.aclose()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error geocoding '{location}': {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error geocoding '{location}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error geocoding '{location}': {e}")
            return []
    
    async def geocode_batch(
        self,
        locations: List[str],
        country_filter: str = "pk"
    ) -> Dict[str, List[Tuple[float, float]]]:
        """
        Geocode multiple locations in parallel for efficiency.
        
        Args:
            locations: List of place names to geocode
            country_filter: ISO country code filter
            
        Returns:
            Dict mapping location strings to coordinate lists
        """
        # Use context manager for efficient connection pooling
        async with self:
            tasks = [self.geocode(loc, country_filter) for loc in locations]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                loc: res if isinstance(res, list) else []
                for loc, res in zip(locations, results)
            }
    
    def disambiguate_by_centroid(
        self,
        candidates: List[Tuple[float, float]],
        context_coords: List[Tuple[float, float]]
    ) -> Tuple[float, float]:
        """
        Select the coordinate closest to the centroid of context coordinates.
        Implements spatial context disambiguation as per spec.
        
        Time Complexity: O(n + m) where n = candidates, m = context_coords
        
        Args:
            candidates: List of candidate coordinates to choose from
            context_coords: List of context coordinates to calculate centroid
            
        Returns:
            The candidate coordinate closest to the context centroid
        """
        if not candidates:
            raise ValueError("No candidates to disambiguate")
        
        if len(candidates) == 1 or not context_coords:
            return candidates[0]
        
        # Calculate centroid in O(m) time
        centroid_lon = sum(c[0] for c in context_coords) / len(context_coords)
        centroid_lat = sum(c[1] for c in context_coords) / len(context_coords)
        
        # Find closest candidate in O(n) time using squared Euclidean distance
        # (no need for sqrt since we're only comparing distances)
        def squared_distance(coord: Tuple[float, float]) -> float:
            return (coord[0] - centroid_lon)**2 + (coord[1] - centroid_lat)**2
        
        return min(candidates, key=squared_distance)