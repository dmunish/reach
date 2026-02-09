from typing import List, Optional, Dict, Any, cast
from uuid import UUID
from supabase import Client
import logging
import hashlib
import json
from functools import lru_cache

from ..services.redis_cache import get_redis_cache

logger = logging.getLogger(__name__)

class PlacesRepository:
    """
    Repository for database operations on the places table.
    Provides abstraction over Supabase client with proper type handling.
    Now includes Redis caching for expensive queries.
    """
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
        # In-memory LRU cache for frequently accessed places (500 most recent)
        self._place_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_maxsize = 500
    
    async def search_by_fuzzy_name(
        self, 
        name: str, 
        threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Search places using fuzzy name matching via PostgreSQL function.
        Uses trigram similarity for efficient fuzzy matching.
        NOW WITH REDIS CACHING AND DYNAMIC THRESHOLD FOR SHORT STRINGS.
        
        Args:
            name: Location name to search for
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of matching places with similarity scores
        """
        # Dynamic threshold adjustment for short strings
        # Short strings need lower thresholds to handle 1-char typos
        # Examples: "Multn" → "Multan", "Peshwar" → "Peshawar", "Islmabad" → "Islamabad"
        adjusted_threshold = threshold
        if len(name) <= 5:
            # Very short strings (≤5): aggressive reduction for 1-char typos
            adjusted_threshold = max(0.40, threshold - 0.30)  # e.g., 0.85 → 0.55
            logger.debug(f"Very short string '{name}' - adjusted threshold: {threshold} -> {adjusted_threshold}")
        elif len(name) <= 8:
            # Short strings (6-8): more lenient for missing/wrong characters
            adjusted_threshold = max(0.50, threshold - 0.30)  # e.g., 0.85 → 0.55 or 0.50 min
            logger.debug(f"Short string '{name}' - adjusted threshold: {threshold} -> {adjusted_threshold}")
        
        # Try Redis cache first
        cache = get_redis_cache()
        if cache:
            cache_key = f"fuzzy:{name}:{adjusted_threshold}"
            cached_result = await cache.get("fuzzy_search", cache_key)
            if cached_result is not None:
                return cached_result
        
        try:
            result = self.client.rpc(
                'search_places_fuzzy',
                {
                    'search_name': name,
                    'similarity_threshold': adjusted_threshold
                }
            ).execute()
            
            # Type guard: ensure result.data is a list
            if result.data and isinstance(result.data, list):
                data = cast(List[Dict[str, Any]], result.data)
                
                # Cache the result
                if cache:
                    from ..config import get_settings
                    settings = get_settings()
                    cache_key = f"fuzzy:{name}:{adjusted_threshold}"
                    await cache.set("fuzzy_search", cache_key, data, ttl_seconds=settings.redis_ttl_fuzzy)
                
                return data
            return []
        except Exception as e:
            logger.error(f"Fuzzy search failed for '{name}': {e}")
            return []
    
    async def find_by_coordinates(
        self, 
        longitude: float, 
        latitude: float
    ) -> Optional[Dict[str, Any]]:
        """
        Find place containing a point using PostGIS ST_Contains.
        Returns the most specific (highest hierarchy level) place.
        
        Args:
            longitude: Longitude coordinate
            latitude: Latitude coordinate
            
        Returns:
            Place dict or None if no match found
        """
        try:
            result = self.client.rpc(
                'find_place_by_point',
                {'lon': longitude, 'lat': latitude}
            ).execute()
            
            # Type guard: ensure result.data is a list and return first element
            if result.data and isinstance(result.data, list) and len(result.data) > 0:
                return cast(Dict[str, Any], result.data[0])
            return None
        except Exception as e:
            logger.error(f"Point lookup failed for ({longitude}, {latitude}): {e}")
            return None
    
    async def get_by_id(self, place_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get place by ID with in-memory LRU caching.
        
        Args:
            place_id: UUID of the place
            
        Returns:
            Place dict or None if not found
        """
        place_id_str = str(place_id)
        
        # Check in-memory cache first (fastest)
        if place_id_str in self._place_cache:
            return self._place_cache[place_id_str]
        
        try:
            result = self.client.table('places')\
                .select('*')\
                .eq('id', place_id_str)\
                .single()\
                .execute()
            
            # Type guard for single result
            if result.data and isinstance(result.data, dict):
                place_data = cast(Dict[str, Any], result.data)
                
                # Add to in-memory cache
                self._add_to_cache(place_id_str, place_data)
                
                return place_data
            return None
        except Exception as e:
            logger.error(f"Get by ID failed for {place_id}: {e}")
            return None
    
    def _add_to_cache(self, place_id: str, place_data: Dict[str, Any]):
        """Add place to in-memory cache with LRU eviction."""
        if len(self._place_cache) >= self._cache_maxsize:
            # Remove oldest entry (first key)
            oldest_key = next(iter(self._place_cache))
            del self._place_cache[oldest_key]
        
        self._place_cache[place_id] = place_data
    
    async def get_children(
        self, 
        parent_id: UUID, 
        level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all children of a place, optionally filtered by hierarchy level.
        
        Args:
            parent_id: UUID of parent place
            level: Optional hierarchy level to filter by
            
        Returns:
            List of child places
        """
        try:
            query = self.client.table('places')\
                .select('*')\
                .eq('parent_id', str(parent_id))
            
            if level is not None:
                query = query.eq('hierarchy_level', level)
            
            result = query.execute()
            
            # Type guard: ensure result.data is a list
            if result.data and isinstance(result.data, list):
                return cast(List[Dict[str, Any]], result.data)
            return []
        except Exception as e:
            logger.error(f"Get children failed for {parent_id}: {e}")
            return []
    
    async def find_places_in_direction(
    self,
    base_place_ids: List[UUID],
    direction: str
    ) -> List[Dict[str, Any]]:
        """
        Find all places in a directional region using PostgreSQL function.
        NOW WITH REDIS CACHING for massive performance boost.
        
        Args:
            base_place_ids: Base place IDs defining the region
            direction: Directional indicator (e.g., 'north', 'central')
            
        Returns:
            List of places in the directional grid intersection
        """
        # Try Redis cache first
        cache = get_redis_cache()
        if cache:
            # Sort IDs for consistent cache key
            sorted_ids = sorted(str(pid) for pid in base_place_ids)
            cache_key = f"{','.join(sorted_ids)}:{direction}"
            
            cached_result = await cache.get("directional", cache_key)
            if cached_result is not None:
                logger.info(f"✅ Directional cache HIT: {direction} ({len(cached_result)} places)")
                return cached_result
        
        try:
            logger.info(f"Calling find_places_in_direction with ids: {base_place_ids}, direction: {direction}")
            
            result = self.client.rpc(
                'find_places_in_direction',
                {
                    'base_place_ids': [str(pid) for pid in base_place_ids],
                    'direction': direction.lower()
                }
            ).execute()
            
            # Type guard: ensure result.data is a list
            if result.data and isinstance(result.data, list):
                result_data = cast(List[Dict[str, Any]], result.data)
                
                # Cache the result
                if cache:
                    from ..config import get_settings
                    settings = get_settings()
                    sorted_ids = sorted(str(pid) for pid in base_place_ids)
                    cache_key = f"{','.join(sorted_ids)}:{direction}"
                    await cache.set("directional", cache_key, result_data, ttl_seconds=settings.redis_ttl_directional)
                    logger.info(f"💾 Directional cache SET: {direction} ({len(result_data)} places)")
                
                return result_data
            return []
        except Exception as e:
            logger.error(f"Directional search failed for {direction}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def get_children_count(self, parent_id: UUID) -> int:
        """
        Get the total number of direct children for a parent place.
        
        Args:
            parent_id: UUID of parent place
            
        Returns:
            Count of direct children
        """
        try:
            result = self.client.table('places')\
                .select('id')\
                .eq('parent_id', str(parent_id))\
                .execute()
            
            # Count result rows
            if result.data and isinstance(result.data, list):
                return len(result.data)
            return 0
        except Exception as e:
            logger.error(f"Get children count failed for {parent_id}: {e}")
            return 0
    
    async def get_children_counts_batch(
        self, 
        parent_ids: List[UUID]
    ) -> Dict[str, int]:
        """
        Batch get children counts for multiple parents.
        
        More efficient than calling get_children_count multiple times.
        Uses a single query.
        
        Args:
            parent_ids: List of parent UUIDs
            
        Returns:
            Dict mapping parent_id (as string) to child count
        """
        if not parent_ids:
            return {}
        
        try:
            result = self.client.table('places')\
                .select('parent_id')\
                .in_('parent_id', [str(pid) for pid in parent_ids])\
                .execute()
            
            # Count occurrences of each parent_id
            counts: Dict[str, int] = {}
            if result.data and isinstance(result.data, list):
                for row in result.data:
                    if isinstance(row, dict):
                        parent = row.get('parent_id')
                        if parent and isinstance(parent, str):
                            counts[parent] = counts.get(parent, 0) + 1
            
            return counts
        except Exception as e:
            logger.error(f"Batch children count failed: {e}")
            return {}
    
    async def get_by_ids_batch(self, place_ids: List[UUID]) -> Dict[str, Dict[str, Any]]:
        """
        Batch get places by IDs with in-memory caching.
        
        Much more efficient than calling get_by_id multiple times.
        Uses a single query with .in_() filter + checks in-memory cache first.
        
        Args:
            place_ids: List of place UUIDs to fetch
            
        Returns:
            Dict mapping place_id (as string) to place data
        """
        if not place_ids:
            return {}
        
        # Check in-memory cache first
        places_dict: Dict[str, Dict[str, Any]] = {}
        uncached_ids: List[UUID] = []
        
        for place_id in place_ids:
            place_id_str = str(place_id)
            if place_id_str in self._place_cache:
                places_dict[place_id_str] = self._place_cache[place_id_str]
            else:
                uncached_ids.append(place_id)
        
        # Only query database for uncached IDs
        if uncached_ids:
            try:
                result = self.client.table('places')\
                    .select('*')\
                    .in_('id', [str(pid) for pid in uncached_ids])\
                    .execute()
                
                # Build lookup dict and add to cache
                if result.data and isinstance(result.data, list):
                    for place in result.data:
                        if isinstance(place, dict) and 'id' in place:
                            place_id_str = str(place['id'])
                            places_dict[place_id_str] = place
                            self._add_to_cache(place_id_str, place)
            except Exception as e:
                logger.error(f"Batch get by IDs failed: {e}")
        
        return places_dict