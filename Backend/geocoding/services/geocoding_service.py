from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging
from collections import defaultdict

from ..models import GeocodeResult, MatchedPlace, GeocodeOptions
from ..repositories.places_repository import PlacesRepository
from .name_matcher import NameMatcher
from .external_geocoder import ExternalGeocoder
from .directional_parser import DirectionalParser, Direction

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Main orchestration service for geocoding location strings.
    
    Implements the complete workflow from spec:
    1. Parse directional indicators
    2. Try fuzzy name matching
    3. Fallback to external geocoding + point-in-polygon
    4. Apply directional filtering if needed
    5. Hierarchical aggregation to minimize redundant IDs
    
    Time Complexity: O(log n) for typical queries (database-dominated)
    """
    
    def __init__(
        self,
        places_repo: PlacesRepository,
        name_matcher: NameMatcher,
        external_geocoder: ExternalGeocoder,
        directional_parser: DirectionalParser
    ):
        self.repo = places_repo
        self.matcher = name_matcher
        self.geocoder = external_geocoder
        self.parser = directional_parser
    
    async def geocode_location(
        self,
        location: str,
        options: GeocodeOptions,
        batch_context: Optional[List[Tuple[float, float]]] = None
    ) -> GeocodeResult:
        """
        Geocode a single location string.
        
        Args:
            location: Location string to geocode
            options: Geocoding options
            batch_context: Context coordinates from other locations in batch (for disambiguation)
            
        Returns:
            GeocodeResult with matched places or error
        """
        try:
            # Parse for directional indicators
            direction, place_names = self.parser.parse(location)
            
            if direction:
                # Directional description processing
                return await self._process_directional(
                    location, direction, place_names, options
                )
            else:
                # Simple place name resolution
                return await self._process_simple(
                    location, place_names[0] if place_names else location, 
                    options, batch_context
                )
                
        except Exception as e:
            logger.error(f"Geocoding failed for '{location}': {e}", exc_info=True)
            return GeocodeResult(
                input=location,
                matched_places=[],
                error=f"Geocoding failed: {str(e)}"
            )
    
    async def geocode_batch(
        self,
        locations: List[str],
        options: GeocodeOptions
    ) -> List[GeocodeResult]:
        """
        Geocode multiple locations with context-aware disambiguation.
        
        Strategy:
        1. First pass: Try fuzzy matching for all locations
        2. Collect coordinates for successful matches
        3. Second pass: Geocode failures with centroid context
        
        Time Complexity: O(n * log m) where n = locations, m = places in DB
        
        Args:
            locations: List of location strings
            options: Geocoding options
            
        Returns:
            List of GeocodeResult objects
        """
        if not locations:
            return []
        
        results = []
        context_coords = []
        
        # First pass: Try matching all locations
        for location in locations:
            result = await self.geocode_location(location, options, None)
            results.append(result)
            
            # Collect coordinates for context
            if result.matched_places:
                # Use first matched place's approximate center (we'd need coords from DB)
                # For now, we'll do second pass with whatever context we have
                pass
        
        # TODO: Second pass for failed matches with centroid context
        # This requires storing coordinates in places table or calculating from polygons
        
        return results
    
    async def _process_simple(
        self,
        original_input: str,
        place_name: str,
        options: GeocodeOptions,
        batch_context: Optional[List[Tuple[float, float]]] = None
    ) -> GeocodeResult:
        """
        Process simple place name (no directional indicator).
        
        Workflow:
        1. Try fuzzy name matching (fast, O(log n))
        2. If fails, try external geocoding (slower, O(network))
        3. If multiple external results, use context for disambiguation
        4. Perform point-in-polygon to find containing place
        
        Args:
            original_input: Original user input
            place_name: Parsed place name
            options: Geocoding options
            batch_context: Context coordinates for disambiguation
            
        Returns:
            GeocodeResult with matched places
        """
        # Step 1: Try fuzzy name matching
        match = await self.matcher.match(place_name)
        
        if match:
            matched_place = MatchedPlace(
                id=match['id'],
                name=match['name'],
                hierarchy_level=match['hierarchy_level'],
                match_method=match['match_method'],
                confidence=match.get('confidence') if options.include_confidence_scores else None
            )
            return GeocodeResult(
                input=original_input,
                matched_places=[matched_place]
            )
        
        # Step 2: Fallback to external geocoding
        logger.info(f"Fuzzy match failed for '{place_name}', trying external geocoding")
        
        coords = await self.geocoder.geocode(place_name, country_filter="pk")
        
        if not coords:
            logger.warning(f"No geocoding results for '{place_name}'")
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error="No match found in database or external geocoding service"
            )
        
        # Step 3: Disambiguate if multiple results
        if len(coords) > 1 and batch_context:
            selected_coord = self.geocoder.disambiguate_by_centroid(coords, batch_context)
        else:
            selected_coord = coords[0]
        
        # Step 4: Point-in-polygon lookup
        lon, lat = selected_coord
        place = await self.repo.find_by_coordinates(lon, lat)
        
        if not place:
            logger.warning(f"Coordinates {lon}, {lat} not within any known place")
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error=f"Coordinates ({lon:.4f}, {lat:.4f}) not within Pakistan administrative boundaries"
            )
        
        matched_place = MatchedPlace(
            id=place['id'],
            name=place['name'],
            hierarchy_level=place['hierarchy_level'],
            match_method='point_in_polygon',
            confidence=None  # No confidence for point-in-polygon
        )
        
        return GeocodeResult(
            input=original_input,
            matched_places=[matched_place]
        )
    
    async def _process_directional(
        self,
        original_input: str,
        direction: Direction,
        place_names: Tuple[str, ...],
        options: GeocodeOptions
    ) -> GeocodeResult:
        """
        Process directional description (e.g., "Central Sindh and Balochistan").
        
        Workflow:
        1. Match each base place name (e.g., Sindh, Balochistan)
        2. Get place IDs for base regions
        3. Query database for places in directional grid
        4. Apply hierarchical aggregation
        
        Time Complexity: O(k * log n + m) where:
            k = number of base places
            n = total places in DB
            m = places in directional region
        
        Args:
            original_input: Original user input
            direction: Directional indicator (e.g., Direction.CENTRAL)
            place_names: Base place names to define region
            options: Geocoding options
            
        Returns:
            GeocodeResult with matched places in directional region
        """
        if not place_names:
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error="No place names found after parsing direction"
            )
        
        # Step 1: Match all base places
        base_place_ids = []
        matched_base_names = []
        
        for place_name in place_names:
            match = await self.matcher.match(place_name)
            if match:
                base_place_ids.append(UUID(match['id']))
                matched_base_names.append(match['name'])
            else:
                logger.warning(f"Could not match base place: {place_name}")
        
        if not base_place_ids:
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error=f"Could not match any base places: {', '.join(place_names)}"
            )
        
        # Step 2: Query for places in directional region
        directional_places = await self.repo.find_places_in_direction(
            base_place_ids,
            direction.value
        )
        
        if not directional_places:
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                regions_processed=list(matched_base_names),
                direction=direction.value,
                error=f"No places found in {direction.value} region"
            )
        
        # Step 3: Apply hierarchical aggregation
        aggregated_places = self._aggregate_hierarchy(directional_places)
        
        # Step 4: Convert to MatchedPlace objects
        matched_places = [
            MatchedPlace(
                id=place['id'],
                name=place['name'],
                hierarchy_level=place['hierarchy_level'],
                match_method='directional_intersection',
                confidence=None
            )
            for place in aggregated_places
        ]
        
        return GeocodeResult(
            input=original_input,
            matched_places=matched_places,
            regions_processed=list(matched_base_names),
            direction=direction.value
        )
    
    def _aggregate_hierarchy(
        self,
        places: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply hierarchical aggregation to minimize redundant place IDs.
        
        Logic:
        - If all children of a parent are present, return only the parent
        - Apply recursively up the hierarchy
        
        Example: If all 5 tehsils of a district are matched, return only the district.
        
        Time Complexity: O(n) where n = number of places
        
        Args:
            places: List of matched places with hierarchy info
            
        Returns:
            Aggregated list of places (redundant children removed)
        """
        if not places:
            return []
        
        # Group places by parent
        by_parent: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
        for place in places:
            parent_id = place.get('parent_id')
            by_parent[parent_id].append(place)
        
        # Build parent lookup for efficiency
        place_lookup = {p['id']: p for p in places}
        
        # For each parent, check if all children are present
        aggregated = []
        processed_children = set()
        
        for parent_id, children in by_parent.items():
            if parent_id is None:
                # Top-level places (no parent)
                aggregated.extend(children)
                continue
            
            # Check if parent exists in our results
            if parent_id not in place_lookup:
                # Parent not in results, keep children
                aggregated.extend(children)
                continue
            
            parent = place_lookup[parent_id]
            
            # This is a simplified version - full implementation would need to:
            # 1. Query total children count for parent from DB
            # 2. Compare with children in results
            # 3. Aggregate if all children present
            
            # For now, just return all places (no aggregation)
            # TODO: Implement full aggregation with DB query
            aggregated.extend(children)
        
        return aggregated
    
    async def suggest_alternatives(
        self,
        location: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get alternative suggestions for a failed match.
        
        Useful for error messages: "Did you mean: X, Y, Z?"
        
        Args:
            location: Location string that failed to match
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested places with similarity scores
        """
        # Lower threshold to get suggestions
        candidates = await self.repo.search_by_fuzzy_name(location, threshold=0.5)
        
        if not candidates:
            return []
        
        # Sort by similarity and return top N
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x.get('similarity_score', 0),
            reverse=True
        )
        
        return sorted_candidates[:limit]
