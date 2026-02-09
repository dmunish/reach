from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class NameMatcher:
    def __init__(
        self,
        places_repo,
        threshold: float = 0.85,
        prefer_lower_levels: bool = True
    ):
        self.repo = places_repo
        self.threshold = threshold
        self.prefer_lower_levels = prefer_lower_levels
    
    async def match(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Match a location string to a place using fuzzy matching.
        Returns best match or None.
        """
        # Try fuzzy search via database
        candidates = await self.repo.search_by_fuzzy_name(
            location, 
            self.threshold
        )
        
        if not candidates:
            logger.info(f"No fuzzy matches for '{location}'")
            return None
        
        # Select best candidate
        best_match = self._select_best_candidate(candidates)
        
        return {
            'id': best_match['id'],
            'name': best_match['name'],
            'hierarchy_level': best_match['hierarchy_level'],
            'match_method': 'fuzzy_name' if best_match.get('similarity_score', 1.0) < 1.0 else 'exact_name',
            'confidence': best_match.get('similarity_score')
        }
    
    def _select_best_candidate(
        self, 
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Select best candidate from multiple matches with intelligent hierarchy preference.
        
        Strategy:
        1. For EXACT matches (score = 1.0): Prefer administrative districts (L2) over subdivisions (L3)
           Example: "Karachi" → prefer "East Karachi" (L2) over "New Karachi Town" (L3)
        2. For PARTIAL matches (score < 1.0): Also prefer Level 2 over Level 3
           Reasoning: Users searching for cities want districts, not sub-districts
        
        Exception: Level 1 (provinces) should be avoided unless explicitly requested
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # Check if we have exact matches
        exact_matches = [c for c in candidates if c.get('similarity_score', 0) >= 0.99]
        fuzzy_matches = [c for c in candidates if c.get('similarity_score', 0) < 0.99]
        
        if exact_matches:
            # For exact matches: prefer Level 2 (districts) unless Level 3 is significantly better
            # This handles "Karachi" → "East Karachi" (L2) vs "New Karachi Town" (L3)
            
            # First, try to find Level 2 exact matches
            level_2_matches = [c for c in exact_matches if c['hierarchy_level'] == 2]
            if level_2_matches:
                # Return the first Level 2 exact match (they all have score 1.0)
                return level_2_matches[0]
            
            # If no Level 2, prefer Level 3 over Level 1 (provinces)
            level_3_matches = [c for c in exact_matches if c['hierarchy_level'] == 3]
            if level_3_matches:
                return level_3_matches[0]
            
            # Fall back to any exact match
            return exact_matches[0]
        
        # For fuzzy matches: prefer Level 2 (districts) over Level 3 (tehsils)
        return max(
            candidates,
            key=lambda x: (x.get('similarity_score', 0), -abs(x['hierarchy_level'] - 2))
        )