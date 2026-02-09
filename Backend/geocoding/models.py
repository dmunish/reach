from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from uuid import UUID

class GeocodeOptions(BaseModel):
    prefer_lower_admin_levels: bool = True
    include_confidence_scores: bool = False

class GeocodeRequest(BaseModel):
    locations: List[str] = Field(..., min_items=1)
    options: GeocodeOptions = GeocodeOptions()

class MatchedPlace(BaseModel):
    id: UUID
    name: str
    hierarchy_level: int
    match_method: Literal["exact_name", "fuzzy_name", "point_in_polygon", 
                          "directional_intersection"]
    confidence: Optional[float] = None

class GeocodeResult(BaseModel):
    input: str
    matched_places: List[MatchedPlace]
    regions_processed: Optional[List[str]] = None
    direction: Optional[str] = None
    error: Optional[str] = None

class GeocodeResponse(BaseModel):
    results: List[GeocodeResult]
    errors: List[str] = []