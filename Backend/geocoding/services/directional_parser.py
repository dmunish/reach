import re
from typing import Tuple, Optional
from enum import Enum
from functools import lru_cache

class Direction(Enum):
    """Directional indicators for geographic parsing"""
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    CENTRAL = "central"
    NORTHEAST = "north-eastern"
    NORTHWEST = "north-western"
    SOUTHEAST = "south-eastern"
    SOUTHWEST = "south-western"
    
    @classmethod
    def to_sql_value(cls, direction: 'Direction') -> str:
        """Convert direction enum to SQL-compatible string"""
        return direction.value

class DirectionalParser:
    """
    Parser for extracting directional indicators and place names from location strings.
    
    Design Note:
    - This parser handles SINGLE place names only (e.g., "Central Sindh")
    - For multiple regions, send separate queries: ["Central Sindh", "Central Balochistan"]
    - No conjunction splitting (user will not send "Sindh and Balochistan")
    
    Optimizations:
    - Pre-compiled regex patterns for O(1) pattern lookup
    - LRU cache for repeated parse operations
    - Compound directions checked before simple ones (priority order)
    - Single-pass regex matching
    """
    
    # Pre-compile regex patterns for better performance (O(1) lookup)
    # Order matters: check compound directions first (more specific)
    _DIRECTION_PATTERNS = [
        (Direction.NORTHEAST, re.compile(r'\b(north[\s-]?east(?:ern)?)\b', re.IGNORECASE)),
        (Direction.NORTHWEST, re.compile(r'\b(north[\s-]?west(?:ern)?)\b', re.IGNORECASE)),
        (Direction.SOUTHEAST, re.compile(r'\b(south[\s-]?east(?:ern)?)\b', re.IGNORECASE)),
        (Direction.SOUTHWEST, re.compile(r'\b(south[\s-]?west(?:ern)?)\b', re.IGNORECASE)),
        (Direction.NORTH, re.compile(r'\b(north(?:ern)?)\b', re.IGNORECASE)),
        (Direction.SOUTH, re.compile(r'\b(south(?:ern)?)\b', re.IGNORECASE)),
        (Direction.EAST, re.compile(r'\b(east(?:ern)?)\b', re.IGNORECASE)),
        (Direction.WEST, re.compile(r'\b(west(?:ern)?)\b', re.IGNORECASE)),
        (Direction.CENTRAL, re.compile(r'\b(central|middle)\b', re.IGNORECASE)),
    ]
    
    @lru_cache(maxsize=256)
    def parse(self, location_string: str) -> Tuple[Optional[Direction], Tuple[str, ...]]:
        """
        Parse directional description into direction and single place name.
        
        Time Complexity: O(n) where n is string length (single-pass regex)
        Space Complexity: O(1) - returns single place name
        
        Args:
            location_string: Raw location text (e.g., "Central Sindh")
            
        Returns:
            (direction, (place_name,)) or (None, (location_string,)) if no direction found
            Returns tuple for caching compatibility
        
        Examples:
            "Central Sindh" -> (Direction.CENTRAL, ("Sindh",))
            "North-Eastern KPK" -> (Direction.NORTHEAST, ("KPK",))
            "Islamabad" -> (None, ("Islamabad",))
        """
        if not location_string or not location_string.strip():
            return None, ()
        
        location_string = location_string.strip()
        
        # Check for directional indicators (single pass through pattern list)
        detected_direction: Optional[Direction] = None
        cleaned_string = location_string
        
        for direction, pattern in self._DIRECTION_PATTERNS:
            match = pattern.search(cleaned_string)
            if match:
                detected_direction = direction
                # Remove matched direction from string
                cleaned_string = pattern.sub('', cleaned_string).strip()
                break  # Stop after first match (compound directions matched first)
        
        if not detected_direction:
            return None, (location_string,)
        
        # Return single place name (no conjunction splitting)
        cleaned_place = cleaned_string.strip()
        if not cleaned_place:
            return detected_direction, ()
        
        return detected_direction, (cleaned_place,)
    
    def clear_cache(self):
        """Clear the LRU cache (useful for testing or memory management)"""
        self.parse.cache_clear()