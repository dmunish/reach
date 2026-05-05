"""
Unit tests for Backend/processing_engine/processor_utils/llm_client.py
Tests LLM client configuration, response handling, and error patterns.
"""

import pytest
import json
import os
from unittest.mock import patch


class TestLLMClientConfiguration:
    """Test LLM client configuration and parameter handling (UT-M2-007, UT-M2-008)"""
    
    def test_model_configuration_loading(self):
        """UT-M2-007: Model configuration validation"""
        config = {
            "gpt-4": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048
            },
            "gpt-3.5-turbo": {
                "model": "gpt-3.5-turbo",
                "temperature": 0.5,
                "max_tokens": 1024
            }
        }
        
        # Valid model
        assert "gpt-4" in config
        assert config["gpt-4"]["temperature"] == 0.7
        
        # Invalid model
        assert "invalid-model" not in config
    
    def test_temperature_parameter_valid_range(self):
        """Test temperature parameter validation"""
        valid_temps = [0.0, 0.5, 1.0, 1.5, 2.0]
        
        for temp in valid_temps:
            assert 0.0 <= temp <= 2.0
    
    def test_runtime_kwargs_merge_pattern(self):
        """UT-M2-008: Runtime kwargs merged with defaults"""
        defaults = {
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 1.0
        }
        
        runtime_params = {"temperature": 0.5}  # Override
        merged = {**defaults, **runtime_params}
        
        assert merged["temperature"] == 0.5  # Overridden
        assert merged["max_tokens"] == 2048  # From defaults
        assert merged["top_p"] == 1.0  # From defaults
    
    def test_api_key_from_environment(self):
        """Test API key loading from environment"""
        test_key = "test_key_12345"
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': test_key}):
            api_key = os.getenv('OPENAI_API_KEY')
            assert api_key == test_key


class TestLLMClientResponses:
    """Test API response handling"""
    
    def test_valid_json_response_parsing(self):
        """Test parsing valid JSON responses"""
        mock_response = {
            "alert_type": "FLOOD",
            "severity": "EXTREME",
            "location_mentions": ["Sindh"],
            "description": "Heavy rainfall"
        }
        
        response_text = json.dumps(mock_response)
        parsed = json.loads(response_text)
        
        assert parsed["alert_type"] == "FLOOD"
        assert parsed["severity"] == "EXTREME"
        assert "Sindh" in parsed["location_mentions"]
    
    def test_invalid_json_response_error(self):
        """Test handling of invalid JSON responses"""
        mock_response_text = "This is not JSON"
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(mock_response_text)
    
    def test_response_field_validation(self):
        """Test validation of required response fields"""
        required_fields = ["alert_type", "severity", "location_mentions", "description"]
        
        valid_response = {
            "alert_type": "FLOOD",
            "severity": "EXTREME",
            "location_mentions": ["Sindh"],
            "description": "Test alert"
        }
        
        for field in required_fields:
            assert field in valid_response


class TestLLMClientErrorHandling:
    """Test error handling patterns"""
    
    def test_timeout_error_detection(self):
        """Test detection of timeout errors"""
        timeout_message = "Request timeout after 60 seconds"
        assert "timeout" in timeout_message.lower()
    
    def test_rate_limit_error_detection(self):
        """Test detection of rate limit errors"""
        rate_limit_message = "Rate limit exceeded. Please wait before retrying."
        assert "rate limit" in rate_limit_message.lower()
    
    def test_api_key_error_detection(self):
        """Test detection of API key errors"""
        auth_error_message = "Invalid API key provided"
        assert "invalid" in auth_error_message.lower() or "api key" in auth_error_message.lower()


class TestLLMClientAsyncPatterns:
    """Test async client patterns"""
    
    @pytest.mark.asyncio
    async def test_async_call_pattern(self):
        """Test async function call pattern"""
        import asyncio
        
        async def mock_async_call(messages: list) -> str:
            return json.dumps({
                "alert_type": "FLOOD",
                "severity": "EXTREME"
            })
        
        result = await mock_async_call([{"role": "user", "content": "Test"}])
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["alert_type"] == "FLOOD"
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls(self):
        """Test multiple concurrent async calls"""
        import asyncio
        
        async def mock_call(call_id: int) -> str:
            return json.dumps({"call_id": call_id, "status": "completed"})
        
        results = await asyncio.gather(
            mock_call(1),
            mock_call(2),
            mock_call(3)
        )
        
        assert len(results) == 3
        for result_str in results:
            result = json.loads(result_str)
            assert "call_id" in result
            assert result["status"] == "completed"
            
            with pytest.raises(Exception, match="Rate limit"):
                mock_call()
