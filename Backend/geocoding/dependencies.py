from functools import lru_cache
from supabase import create_client, Client
from supabase._async.client import create_client as create_async_client, AsyncClient
import logging
import asyncio

from .config import get_settings, Settings
from .repositories.places_repository import PlacesRepository
from .services.name_matcher import NameMatcher
from .services.external_geocoder import ExternalGeocoder
from .services.directional_parser import DirectionalParser
from .services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)

# Global async client instance (managed per event loop)
_async_client: AsyncClient | None = None
_async_client_lock = asyncio.Lock()


# ============================================================================
# Supabase Client Dependency
# ============================================================================

@lru_cache()
def get_supabase_client() -> Client:
    """
    Get Supabase sync client singleton.
    
    Cached to ensure single instance across app lifetime.
    Thread-safe due to lru_cache.
    
    Returns:
        Initialized Supabase client
    """
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    logger.info("Supabase sync client initialized")
    return client


async def get_async_supabase_client() -> AsyncClient:
    """
    Get Supabase async client singleton.
    
    Creates a single async client instance per process/container.
    Thread-safe via asyncio lock.
    
    Returns:
        Initialized async Supabase client
    """
    global _async_client
    
    async with _async_client_lock:
        if _async_client is None:
            settings = get_settings()
            _async_client = await create_async_client(
                settings.supabase_url, 
                settings.supabase_key
            )
            logger.info("Supabase async client initialized")
        return _async_client


# ============================================================================
# Repository Layer Dependencies
# ============================================================================

def get_places_repository() -> PlacesRepository:
    """
    Get PlacesRepository instance with sync client.
    
    Creates new instance per request but reuses cached Supabase client.
    Lightweight since repository is just a wrapper.
    
    Returns:
        PlacesRepository instance
    """
    client = get_supabase_client()
    return PlacesRepository(client)


async def get_async_places_repository() -> PlacesRepository:
    """
    Get PlacesRepository instance with async client.
    
    For use in async contexts (Modal, FastAPI routes, etc.)
    
    Returns:
        PlacesRepository instance with async client
    """
    client = await get_async_supabase_client()
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


async def get_async_name_matcher() -> NameMatcher:
    """
    Get NameMatcher service instance with async repository.
    
    Returns:
        NameMatcher instance with async Supabase client
    """
    settings = get_settings()
    repo = await get_async_places_repository()
    
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
    Get main GeocodingService orchestrator (sync version).
    
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


async def get_async_geocoding_service() -> GeocodingService:
    """
    Get main GeocodingService orchestrator (async version).
    
    Uses async Supabase client for better performance in async contexts.
    Ideal for Modal.com deployments and high-concurrency scenarios.
    
    Dependency Graph:
    GeocodingService
    ├── PlacesRepository (async client)
    │   └── Async Supabase Client
    ├── NameMatcher (async client)
    │   └── PlacesRepository
    ├── ExternalGeocoder
    └── DirectionalParser
    
    Returns:
        Fully initialized GeocodingService with async clients
    """
    repo = await get_async_places_repository()
    matcher = await get_async_name_matcher()
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
    global _async_client
    
    logger.info("Cleaning up services...")
    
    # Close async client if it exists
    if _async_client is not None:
        try:
            await _async_client.auth.sign_out()
        except Exception:
            pass  # Ignore errors on cleanup
        _async_client = None
    
    # Clear caches
    get_settings.cache_clear()
    get_supabase_client.cache_clear()
    get_directional_parser.cache_clear()
    
    # Note: Supabase client doesn't need explicit cleanup
    # httpx clients in ExternalGeocoder are context-managed
    
    logger.info("Cleanup complete")
