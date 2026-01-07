from typing import List, Optional, Dict, Any, cast
from uuid import UUID
from supabase import Client
import logging

logger = logging.getLogger(__name__)

class PlacesRepository:
    """
    Repository for database operations on the places table.
    Provides abstraction over Supabase client with proper type handling.
    """
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    async def search_by_fuzzy_name(
        self, 
        name: str, 
        threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Search places using fuzzy name matching via PostgreSQL function.
        Uses trigram similarity for efficient fuzzy matching.
        
        Args:
            name: Location name to search for
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of matching places with similarity scores
        """
        try:
            result = self.client.rpc(
                'search_places_fuzzy',
                {
                    'search_name': name,
                    'similarity_threshold': threshold
                }
            ).execute()
            
            # Type guard: ensure result.data is a list
            if result.data and isinstance(result.data, list):
                return cast(List[Dict[str, Any]], result.data)
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
        Get place by ID.
        
        Args:
            place_id: UUID of the place
            
        Returns:
            Place dict or None if not found
        """
        try:
            result = self.client.table('places')\
                .select('*')\
                .eq('id', str(place_id))\
                .single()\
                .execute()
            
            # Type guard for single result
            if result.data and isinstance(result.data, dict):
                return cast(Dict[str, Any], result.data)
            return None
        except Exception as e:
            logger.error(f"Get by ID failed for {place_id}: {e}")
            return None
    
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
        Find places in a directional region relative to base places.
        Uses the PostGIS find_places_in_direction function.
        
        Args:
            base_place_ids: UUIDs of base places to define region
            direction: Directional indicator (e.g., 'northern', 'central')
            
        Returns:
            List of places intersecting the directional grid
        """
        try:
            result = self.client.rpc(
                'find_places_in_direction',
                {
                    'base_place_ids': [str(pid) for pid in base_place_ids],
                    'direction': direction.lower()
                }
            ).execute()
            
            # Type guard: ensure result.data is a list
            if result.data and isinstance(result.data, list):
                return cast(List[Dict[str, Any]], result.data)
            return []
        except Exception as e:
            logger.error(f"Directional search failed for {direction}: {e}")
            return []