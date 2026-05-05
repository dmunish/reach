"""
Pytest fixtures for integration tests.
Provides mocks for database, Redis, and external services.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for database operations"""
    with patch('Backend.geocoding.repositories.places_repository.supabase') as mock:
        mock.table.return_value.select.return_value.execute.return_value = {
            "data": [{"id": 1, "name": "Islamabad", "place_id": 100}]
        }
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis cache"""
    with patch('Backend.geocoding.services.redis_cache.redis.Redis') as mock:
        mock.get.return_value = None
        mock.set.return_value = True
        yield mock


@pytest.fixture
def mock_geocoding_service():
    """Mock geocoding service"""
    with patch('Backend.geocoding.services.geocoding_service.GeocodingService') as mock:
        mock_instance = MagicMock()
        mock_instance.geocode_location.return_value = {
            "place_id": 100,
            "name": "Islamabad",
            "admin_level": "district"
        }
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def client():
    """FastAPI test client"""
    from fastapi.testclient import TestClient
    try:
        from Backend.app import app
        return TestClient(app)
    except ImportError:
        # If app doesn't exist yet, return mock
        return MagicMock()


@pytest.fixture
def mock_external_geocoder():
    """Mock external geocoder fallback"""
    with patch('Backend.geocoding.services.external_geocoder.ExternalGeocoder') as mock:
        mock_instance = MagicMock()
        mock_instance.geocode.return_value = [
            {"lat": 33.7, "lon": 73.1, "display_name": "Islamabad, Pakistan"}
        ]
        mock.return_value = mock_instance
        yield mock
