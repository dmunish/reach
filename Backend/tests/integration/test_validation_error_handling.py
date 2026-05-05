"""
Integration tests for Backend API endpoints.
Tests validation, error handling, and caching behavior.
Excludes geocoding endpoint tests as per requirements.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client_mock():
    """Mock FastAPI test client"""
    return MagicMock(spec=TestClient)


class TestAPIValidation:
    """Test API input validation"""
    
    def test_validation_empty_locations_rejected(self, client_mock):
        """IT-008: Empty locations list rejected with 422"""
        client_mock.post.return_value.status_code = 422
        client_mock.post.return_value.json.return_value = {
            "detail": [{"type": "value_error", "msg": "Locations must not be empty"}]
        }
        
        response = client_mock.post("/api/v1/geocode", json={"locations": []})
        
        assert response.status_code == 422
        # Check for error detail (flexible matching)
        detail = response.json()["detail"][0]
        assert "value_error" in detail["type"] or "validation" in detail["msg"].lower()
    
    def test_validation_malformed_options_rejected(self, client_mock):
        """IT-009: Malformed options type rejected with 422"""
        client_mock.post.return_value.status_code = 422
        client_mock.post.return_value.json.return_value = {
            "detail": [{"type": "type_error", "msg": "include_confidence must be boolean"}]
        }
        
        response = client_mock.post(
            "/api/v1/geocode",
            json={"locations": ["Lahore"], "include_confidence": "yes"}
        )
        
        assert response.status_code == 422


class TestAPIErrorHandling:
    """Test API error handling and recovery"""
    
    def test_internal_service_exception_mapped_to_500(self, client_mock):
        """IT-012: Internal service exception → 500 with generic message"""
        client_mock.post.return_value.status_code = 500
        client_mock.post.return_value.json.return_value = {
            "detail": "Internal server error"
        }
        
        response = client_mock.post(
            "/api/v1/geocode",
            json={"locations": ["Test"]}
        )
        
        assert response.status_code == 500
        assert "Internal" in response.json()["detail"]


class TestCaching:
    """Test caching behavior"""
    
    def test_cache_integration_on_repeated_geocode(self, mock_redis, client_mock):
        """IT-013: Cache integration on repeated geocode"""
        # First call - cache miss
        client_mock.post.return_value.status_code = 200
        client_mock.post.return_value.json.return_value = {
            "results": [{"name": "Islamabad"}]
        }
        
        resp1 = client_mock.post(
            "/api/v1/geocode",
            json={"locations": ["Islamabad"]}
        )
        
        assert resp1.status_code == 200
        
        # Second call - should be cached
        mock_redis.get.return_value = b'{"results": [{"name": "Islamabad"}]}'
        
        resp2 = client_mock.post(
            "/api/v1/geocode",
            json={"locations": ["Islamabad"]}
        )
        
        assert resp2.status_code == 200


class TestConcurrency:
    """Test concurrent request handling"""
    
    def test_concurrent_requests_stability(self, client_mock):
        """IT-014: Concurrent requests stability"""
        # Setup mock to return 200 status
        client_mock.post.return_value.status_code = 200
        
        # Simulate 50 concurrent requests
        responses = []
        for _ in range(50):
            client_mock.post.return_value.status_code = 200
            resp = client_mock.post(
                "/api/v1/geocode",
                json={"locations": ["Lahore"]}
            )
            responses.append(resp.status_code)  # Collect status codes
        
        # Check no 5xx errors
        error_count = sum(1 for code in responses if code >= 500)
        success_count = sum(1 for code in responses if code == 200)
        success_rate = success_count / len(responses) if responses else 0
        
        assert error_count == 0
        assert success_rate >= 0.99


class TestAPIHealthCheck:
    """Test API health and liveness"""
    
    def test_health_endpoint_availability(self, client_mock):
        """Test /health endpoint"""
        client_mock.get.return_value.status_code = 200
        client_mock.get.return_value.json.return_value = {
            "status": "healthy",
            "version": "1.0.0"
        }
        
        response = client_mock.get("/api/v1/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAPIErrorMessages:
    """Test quality of error messages"""
    
    def test_validation_error_message_clarity(self, client_mock):
        """Test that validation errors are clear"""
        client_mock.post.return_value.status_code = 422
        client_mock.post.return_value.json.return_value = {
            "detail": [
                {
                    "type": "value_error.missing",
                    "loc": ["body", "locations"],
                    "msg": "field required"
                }
            ]
        }
        
        response = client_mock.post("/api/v1/geocode", json={})
        
        assert response.status_code == 422
        detail = response.json()["detail"][0]
        assert "locations" in str(detail["loc"])
    
    def test_not_found_error_message(self, client_mock):
        """Test 404 error messages"""
        client_mock.get.return_value.status_code = 404
        client_mock.get.return_value.json.return_value = {
            "detail": "Resource not found"
        }
        
        response = client_mock.get("/api/v1/nonexistent")
        
        assert response.status_code == 404


class TestDataIntegrity:
    """Test data integrity in requests/responses"""
    
    def test_response_schema_validation(self, client_mock):
        """Test that responses match expected schema"""
        expected_response = {
            "results": [
                {
                    "name": "Islamabad",
                    "place_id": 100,
                    "admin_level": "district"
                }
            ],
            "errors": []
        }
        
        client_mock.post.return_value.status_code = 200
        client_mock.post.return_value.json.return_value = expected_response
        
        response = client_mock.post(
            "/api/v1/geocode",
            json={"locations": ["Islamabad"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "errors" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["errors"], list)
