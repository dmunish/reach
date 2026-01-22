from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class NameMatcher:
    """
    Service for matching location strings to places using fuzzy name matching.
    
    Design Philosophy:
    - Delegates fuzzy matching to PostgreSQL (pg_trgm) for efficiency
    - Implements business logic for candidate selection
    - Prefers more specific (higher hierarchy level) places when scores are similar
    
    Time Complexity: O(n log n) where n is number of candidates (for sorting)
    """
    
    def __init__(
        self,
        places_repo,
        threshold: float = 0.85,
        prefer_lower_levels: bool = True,
        similarity_tolerance: float = 0.05
    ):
        """
        Initialize name matcher.
        
        Args:
            places_repo: PlacesRepository instance for database access
            threshold: Minimum similarity score for fuzzy matching (0-1)
            prefer_lower_levels: Prefer more specific places (higher hierarchy numbers)
            similarity_tolerance: Score difference within which to prefer lower levels
        """
        self.repo = places_repo
        self.threshold = threshold
        self.prefer_lower_levels = prefer_lower_levels
        self.similarity_tolerance = similarity_tolerance
    
    async def match(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Match a location string to a place using fuzzy matching.
        
        Algorithm:
        1. Query database with pg_trgm similarity (O(log n) with GIN index)
        2. Select best candidate using business rules (O(n log n))
        
        Args:
            location: Location name to match
            
        Returns:
            Dict with matched place info or None if no match found
            Contains: id, name, hierarchy_level, match_method, confidence
        """
        if not location or not location.strip():
            logger.warning("Empty location string provided")
            return None
        
        location = location.strip()
        
        # Try fuzzy search via database (pg_trgm handles the heavy lifting)
        candidates = await self.repo.search_by_fuzzy_name(
            location, 
            self.threshold
        )
        
        if not candidates:
            logger.info(f"No fuzzy matches for '{location}' above threshold {self.threshold}")
            return None
        
        logger.debug(f"Found {len(candidates)} candidates for '{location}'")
        
        # Select best candidate using business rules
        best_match = self._select_best_candidate(candidates)
        
        # Determine match method based on similarity score
        similarity = best_match.get('similarity_score', 1.0)
        match_method = 'exact_name' if similarity >= 0.99 else 'fuzzy_name'
        
        return {
            'id': best_match['id'],
            'name': best_match['name'],
            'hierarchy_level': best_match['hierarchy_level'],
            'match_method': match_method,
            'confidence': similarity
        }
    
    async def match_multiple(
        self,
        locations: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Match multiple locations efficiently.
        
        Note: Currently processes sequentially, but database connection pooling
        helps. Could be parallelized further if needed.
        
        Args:
            locations: List of location names to match
            
        Returns:
            Dict mapping location strings to match results
        """
        results = {}
        for location in locations:
            results[location] = await self.match(location)
        return results
    
    def _select_best_candidate(
        self, 
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Select best candidate from multiple matches using business rules.
        
        Rules:
        1. If prefer_lower_levels is True:
           - Select highest similarity score
           - Among similar scores (within tolerance), prefer higher hierarchy level
        2. Otherwise:
           - Simply select highest similarity score
        
        Time Complexity: O(n) with single-pass max comparison
        
        Args:
            candidates: List of candidate places with similarity scores
            
        Returns:
            Best matching candidate
        """
        if len(candidates) == 1:
            return candidates[0]
        
        if not self.prefer_lower_levels:
            # Simple case: just return highest similarity
            return max(candidates, key=lambda x: x.get('similarity_score', 0))
        
        # Complex case: balance similarity and hierarchy level
        # Find the best similarity score
        best_similarity = max(c.get('similarity_score', 0) for c in candidates)
        
        # Filter candidates within tolerance of best similarity
        top_candidates = [
            c for c in candidates
            if best_similarity - c.get('similarity_score', 0) <= self.similarity_tolerance
        ]
        
        # Among top candidates, prefer higher hierarchy level (more specific)
        return max(top_candidates, key=lambda x: x.get('hierarchy_level', 0))
    
    def get_closest_suggestions(
        self,
        candidates: List[Dict[str, Any]],
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get top N closest matches for error messages/suggestions.
        
        Args:
            candidates: List of candidate matches
            limit: Maximum number of suggestions to return
            
        Returns:
            Top N candidates sorted by similarity score
        """
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x.get('similarity_score', 0),
            reverse=True
        )
        return sorted_candidates[:limit]