from typing import List, Dict, Any, Optional, Tuple, Set
from uuid import UUID
import logging
import asyncio
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
            logger.info(f"Geocoding: '{location}'")
            
            # Parse for directional indicators
            direction, place_names = self.parser.parse(location)
            
            logger.debug(f"Parsed: direction={direction}, places={place_names}")
            
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
        
        # Process each location
        for location in locations:
            result = await self.geocode_location(location, options, None)
            results.append(result)
        
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
            logger.info(f"Fuzzy match success: '{place_name}' -> {match['name']}")
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
            
            # Try to get suggestions
            suggestions = await self.suggest_alternatives(place_name, limit=3)
            if suggestions:
                suggestion_names = [s['name'] for s in suggestions]
                error_msg = f"No match found. Did you mean: {', '.join(suggestion_names)}?"
            else:
                error_msg = "No match found in database or external geocoding service"
            
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error=error_msg
            )
        
        # Step 3: Disambiguate if multiple results
        if len(coords) > 1 and batch_context:
            selected_coord = self.geocoder.disambiguate_by_centroid(coords, batch_context)
        else:
            selected_coord = coords[0]
        
        # Step 4: Point-in-polygon lookup
        lon, lat = selected_coord
        logger.info(f"Point-in-polygon lookup for ({lon:.4f}, {lat:.4f})")
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
            logger.error("No place names found after parsing direction")
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error="No place names found after parsing direction"
            )
        
        # Step 1: Match all base places
        base_place_ids = []
        matched_base_names = []
        failed_matches = []
        
        logger.info(f"Matching base places: {place_names}")
        
        for place_name in place_names:
            match = await self.matcher.match(place_name)
            if match:
                # FIX: Handle both string and UUID types
                place_id = match['id']
                if isinstance(place_id, str):
                    place_id = UUID(place_id)
                elif not isinstance(place_id, UUID):
                    place_id = UUID(str(place_id))
                
                base_place_ids.append(place_id)
                matched_base_names.append(match['name'])
                logger.debug(f"  Matched '{place_name}' -> {match['name']} ({place_id})")
            else:
                logger.warning(f"  Could not match base place: '{place_name}'")
                failed_matches.append(place_name)
        
        if not base_place_ids:
            error_msg = f"Could not match any base places: {', '.join(place_names)}"
            logger.error(error_msg)
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                error=error_msg
            )
        
        if failed_matches:
            logger.warning(f"Some base places not matched: {', '.join(failed_matches)}")
        
        # Step 2: Query for places in directional region
        logger.info(f"Querying directional region: {direction.value} of {matched_base_names}")
        directional_places = await self.repo.find_places_in_direction(
            base_place_ids,
            direction.value
        )
        
        logger.info(f"Found {len(directional_places)} places in directional region")
        
        if not directional_places:
            error_msg = f"No places found in {direction.value} region of {', '.join(matched_base_names)}"
            logger.warning(error_msg)
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                regions_processed=list(matched_base_names),
                direction=direction.value,
                error=error_msg
            )
        
        # FIX: Validate that results have required fields
        valid_places = []
        for place in directional_places:
            if not isinstance(place, dict):
                logger.error(f"Invalid place object: {place}")
                continue
            if 'id' not in place or 'name' not in place or 'hierarchy_level' not in place:
                logger.error(f"Place missing required fields: {place}")
                continue
            valid_places.append(place)
        
        if not valid_places:
            logger.error("No valid places after filtering")
            return GeocodeResult(
                input=original_input,
                matched_places=[],
                regions_processed=list(matched_base_names),
                direction=direction.value,
                error="Internal error: invalid results from database"
            )
        
        logger.debug(f"Valid places after filtering: {len(valid_places)}")
        
        # Step 3: Apply hierarchical aggregation
        aggregated_places = await self._aggregate_hierarchy(valid_places)
        
        logger.info(f"After aggregation: {len(aggregated_places)} places")
        
        # Step 4: Convert to MatchedPlace objects
        matched_places = []
        for place in aggregated_places:
            try:
                # FIX: Handle UUID conversion safely
                place_id = place['id']
                if isinstance(place_id, str):
                    place_id = UUID(place_id)
                elif not isinstance(place_id, UUID):
                    place_id = UUID(str(place_id))
                
                matched_place = MatchedPlace(
                    id=place_id,
                    name=place['name'],
                    hierarchy_level=place['hierarchy_level'],
                    match_method='directional_intersection',
                    confidence=None
                )
                matched_places.append(matched_place)
            except Exception as e:
                logger.error(f"Error creating MatchedPlace from {place}: {e}")
                continue
        
        return GeocodeResult(
            input=original_input,
            matched_places=matched_places,
            regions_processed=list(matched_base_names),
            direction=direction.value
        )
    
    async def _aggregate_hierarchy(
        self,
        places: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply hierarchical aggregation to minimize redundant place IDs.
        
        Two-way aggregation logic:
        1. Remove children when ALL children of a parent are present → keep only parent
        2. Remove parents when ANY children are present → keep only the more specific children
        
        This ensures we return the most specific level without redundancy.
        
        Example: If all 5 tehsils of a district are matched, return only the district.
                 If only 3 of 5 tehsils are matched, return those 3 tehsils (not the district).
        
        Time Complexity: O(n + k*d) where:
            n = number of places
            k = number of unique parents to check
            d = database query time (typically O(1) with index)
        
        Args:
            places: List of matched places with hierarchy info
            
        Returns:
            Aggregated list of places (redundant places removed)
        """
        if not places:
            return []
        
        # Validate places have required fields
        valid_places = []
        for place in places:
            if not isinstance(place, dict):
                logger.warning(f"Skipping non-dict place: {place}")
                continue
            if 'id' not in place or 'hierarchy_level' not in place:
                logger.warning(f"Skipping place without required fields: {place}")
                continue
            valid_places.append(place)
        
        if not valid_places:
            logger.error("No valid places to aggregate")
            return []
        
        # Build lookup structures
        place_by_id: Dict[str, Dict[str, Any]] = {}
        for p in valid_places:
            place_id = str(p['id'])
            place_by_id[place_id] = p
        
        # Group places by parent_id
        by_parent: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
        for place in valid_places:
            parent_id = place.get('parent_id')
            parent_key = str(parent_id) if parent_id else None
            by_parent[parent_key].append(place)
        
        # Track which places to remove (either children or parents)
        places_to_remove: Set[str] = set()
        
        # STEP 1: Remove redundant parents (when ANY of their children are present)
        for place in valid_places:
            parent_id = place.get('parent_id')
            if parent_id and str(parent_id) in place_by_id:
                # This place has a parent in the results - mark parent for removal
                places_to_remove.add(str(parent_id))
                logger.debug(f"Removing parent {parent_id} because child {place['id']} is present")
        
        # STEP 2: Check if we should aggregate children UP to parent
        # Get unique parent IDs from all matched places (parents don't need to be in results already)
        unique_parent_ids = set()
        for place in valid_places:
            parent_id = place.get('parent_id')
            if parent_id:
                unique_parent_ids.add(str(parent_id))
        
        # Get actual child counts from database for all parent IDs
        if unique_parent_ids:
            parent_uuids = [UUID(pid) for pid in unique_parent_ids]
            
            # OPTIMIZATION: Batch fetch both child counts AND parent details in parallel
            actual_child_counts, parent_details = await asyncio.gather(
                self.repo.get_children_counts_batch(parent_uuids),
                self.repo.get_by_ids_batch(parent_uuids)
            )
            
            logger.debug(f"Checking aggregation for {len(unique_parent_ids)} parents")
            
            for parent_id in unique_parent_ids:
                # How many children does this parent have in our results?
                children_in_results = by_parent.get(parent_id, [])
                matched_count = len(children_in_results)
                
                # How many children does this parent have in total?
                total_count = actual_child_counts.get(parent_id, 0)
                
                logger.debug(f"Parent {parent_id}: {matched_count}/{total_count} children matched")
                
                # If ALL children are present, aggregate to parent
                if total_count > 0 and matched_count >= total_count:
                    logger.info(f"Aggregating UP: Parent {parent_id} has all {total_count} children - replacing with parent")
                    
                    # Add parent to results if not already there
                    if parent_id not in place_by_id and parent_id in parent_details:
                        place_by_id[parent_id] = parent_details[parent_id]
                        valid_places.append(parent_details[parent_id])
                    
                    # Remove the parent from removal set (we want to keep it)
                    places_to_remove.discard(parent_id)
                    
                    # Mark all children for removal
                    for child in children_in_results:
                        places_to_remove.add(str(child['id']))
        
        # Build final result excluding marked places
        aggregated = []
        for place in valid_places:
            place_id = str(place['id'])
            if place_id not in places_to_remove:
                aggregated.append(place)
        
        logger.info(f"Aggregation: {len(valid_places)} -> {len(aggregated)} places "
                    f"(removed {len(places_to_remove)} redundant places)")
        
        # OPTIMIZATION: Check if we need recursive aggregation
        # Only recurse if we added new parents that might themselves need aggregation
        # This happens when districts aggregate to provinces, which might aggregate to country
        if places_to_remove and len(aggregated) > 1:
            # Check if any newly added parents have parent_ids in the result set
            needs_recursion = False
            for place in aggregated:
                parent_id = place.get('parent_id')
                if parent_id and str(parent_id) in {str(p['id']) for p in aggregated}:
                    needs_recursion = True
                    break
            
            if needs_recursion:
                logger.debug("Recursive aggregation needed - parents have parents in result set")
                return await self._aggregate_hierarchy(aggregated)
        
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