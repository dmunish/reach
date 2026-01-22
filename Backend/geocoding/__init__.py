"""
Geocoding Microservice

A FastAPI-based microservice for geocoding location strings in Pakistan.
Supports fuzzy matching, directional queries, and hierarchical aggregation.
"""

# Core models
from .models import (
    GeocodeOptions,
    GeocodeRequest,
    MatchedPlace,
    GeocodeResult,
    GeocodeResponse
)

# Configuration
from .config import get_settings, Settings

# Services
from .services import (
    GeocodingService,
    NameMatcher,
    ExternalGeocoder,
    DirectionalParser,
    Direction
)

# Repositories
from .repositories import PlacesRepository

# API
from .api import router

# Dependencies
from .dependencies import (
    get_supabase_client,
    get_places_repository,
    get_name_matcher,
    get_external_geocoder,
    get_directional_parser,
    get_geocoding_service,
    cleanup_services
)

__version__ = "1.0.0"

__all__ = [
    # Models
    'GeocodeOptions',
    'GeocodeRequest',
    'MatchedPlace',
    'GeocodeResult',
    'GeocodeResponse',
    
    # Config
    'get_settings',
    'Settings',
    
    # Services
    'GeocodingService',
    'NameMatcher',
    'ExternalGeocoder',
    'DirectionalParser',
    'Direction',
    
    # Repositories
    'PlacesRepository',
    
    # API
    'router',
    
    # Dependencies
    'get_supabase_client',
    'get_places_repository',
    'get_name_matcher',
    'get_external_geocoder',
    'get_directional_parser',
    'get_geocoding_service',
    'cleanup_services',
]
