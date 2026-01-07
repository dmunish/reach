from typing import Dict, List, Tuple, Optional
import httpx
import hashlib
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

class ExternalGeocoder:
    """
    External geocoding service client with intelligent caching and disambiguation.
    
    Optimizations:
    - In-memory LRU-style cache with TTL to minimize API calls
    - Connection pooling via shared httpx.AsyncClient
    - Batch request support for parallel geocoding
    - Spatial disambiguation using centroid calculation
    """
    
    def __init__(self, api_key: str, base_url: str, cache_ttl_days: int = 30, max_cache_size: int = 1000):
        self.api_key = api_key
        self.base_url = base_url
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, Tuple[List[Tuple[float, float]], datetime]] = {}
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
        cache_input = f"{location.lower()}:{country_filter}"
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def _evict_old_cache_entries(self):
        """Evict expired cache entries and maintain max cache size (LRU-style)"""
        now = datetime.now()
        
        # Remove expired entries
        expired_keys = [
            key for key, (_, cached_at) in self._cache.items()
            if now - cached_at >= self.cache_ttl
        ]
        for key in expired_keys:
            del self._cache[key]
        
        # If still over limit, remove oldest entries
        if len(self._cache) > self.max_cache_size:
            # Sort by timestamp and keep only newest max_cache_size entries
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1][1],  # Sort by timestamp
                reverse=True
            )
            self._cache = dict(sorted_items[:self.max_cache_size])
    
    async def geocode(
        self, 
        location: str,
        country_filter: str = "pk"  # Pakistan only
    ) -> List[Tuple[float, float]]:
        """
        Geocode a location string to coordinates.
        
        Args:
            location: Place name to geocode
            country_filter: ISO country code filter (default: 'pk' for Pakistan)
            
        Returns:
            List of (longitude, latitude) tuples, ordered by relevance
        """
        # Check cache
        cache_key = self._get_cache_key(location, country_filter)
        if cache_key in self._cache:
            coords, cached_at = self._cache[cache_key]
            if datetime.now() - cached_at < self.cache_ttl:
                logger.debug(f"Cache hit for '{location}'")
                return coords
        
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
                
                # Cache results
                self._cache[cache_key] = (coords, datetime.now())
                
                # Periodic cache maintenance
                if len(self._cache) > self.max_cache_size * 1.2:
                    self._evict_old_cache_entries()
                
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