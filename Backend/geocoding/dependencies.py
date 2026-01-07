from functools import lru_cache
from supabase import create_client, Client
import logging

from .config import get_settings, Settings
from .repositories.places_repository import PlacesRepository
from .services.name_matcher import NameMatcher
from .services.external_geocoder import ExternalGeocoder
from .services.directional_parser import DirectionalParser
from .services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


# ============================================================================
# Supabase Client Dependency
# ============================================================================

@lru_cache()
def get_supabase_client() -> Client:
    """
    Get Supabase client singleton.
    
    Cached to ensure single instance across app lifetime.
    Thread-safe due to lru_cache.
    
    Returns:
        Initialized Supabase client
    """
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    logger.info("Supabase client initialized")
    return client


# ============================================================================
# Repository Layer Dependencies
# ============================================================================

def get_places_repository() -> PlacesRepository:
    """
    Get PlacesRepository instance.
    
    Creates new instance per request but reuses cached Supabase client.
    Lightweight since repository is just a wrapper.
    
    Returns:
        PlacesRepository instance
    """
    client = get_supabase_client()
    return PlacesRepository(client)


# ============================================================================
# Service Layer Dependencies
# ============================================================================

def get_name_matcher() -> NameMatcher:
    """
    Get NameMatcher service instance.
    
    Returns:
        NameMatcher instance with injected repository
    """
    settings = get_settings()
    repo = get_places_repository()
    
    return NameMatcher(
        places_repo=repo,
        threshold=settings.fuzzy_match_threshold,
        prefer_lower_levels=settings.prefer_lower_admin_levels
    )


def get_external_geocoder() -> ExternalGeocoder:
    """
    Get ExternalGeocoder service instance.
    
    Returns:
        ExternalGeocoder with API configuration
    """
    settings = get_settings()
    
    return ExternalGeocoder(
        api_key=settings.locationiq_api_key,
        base_url=settings.locationiq_base_url,
        cache_ttl_days=settings.cache_ttl_days
    )


@lru_cache()
def get_directional_parser() -> DirectionalParser:
    """
    Get DirectionalParser singleton.
    
    Cached because parser is stateless and benefits from LRU cache on parse().
    
    Returns:
        DirectionalParser instance
    """
    return DirectionalParser()


# ============================================================================
# Main Orchestration Service
# ============================================================================

def get_geocoding_service() -> GeocodingService:
    """
    Get main GeocodingService orchestrator.
    
    This is the entry point that FastAPI routes depend on.
    Coordinates all other services via constructor injection.
    
    Dependency Graph:
    GeocodingService
    ├── PlacesRepository
    │   └── Supabase Client
    ├── NameMatcher
    │   └── PlacesRepository
    ├── ExternalGeocoder
    └── DirectionalParser
    
    Returns:
        Fully initialized GeocodingService
    """
    repo = get_places_repository()
    matcher = get_name_matcher()
    geocoder = get_external_geocoder()
    parser = get_directional_parser()
    
    return GeocodingService(
        places_repo=repo,
        name_matcher=matcher,
        external_geocoder=geocoder,
        directional_parser=parser
    )


# ============================================================================
# Lifespan Management (Optional - for cleanup)
# ============================================================================

async def cleanup_services():
    """
    Cleanup function for graceful shutdown.
    
    Called on app shutdown to close connections, flush caches, etc.
    """
    logger.info("Cleaning up services...")
    
    # Clear caches
    get_settings.cache_clear()
    get_supabase_client.cache_clear()
    get_directional_parser.cache_clear()
    
    # Note: Supabase client doesn't need explicit cleanup
    # httpx clients in ExternalGeocoder are context-managed
    
    logger.info("Cleanup complete")
