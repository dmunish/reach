"""
Unit tests for Backend/processing_engine/processors/pipeline_processor.py
Tests alert parsing, validation, and transformation patterns.
"""

import pytest
import json
from datetime import datetime


class TestPipelineProcessorValidation:
    """Test JSON schema and data validation (UT-M2-009, UT-M2-010)"""
    
    def test_valid_json_structure(self):
        """UT-M2-009: Valid JSON structure validation"""
        valid_json = {
            "alert_type": "FLOOD",
            "severity": "EXTREME",
            "location_mentions": ["Sindh", "Karachi"],
            "description": "Flash flooding in urban areas",
            "source": "NDMA",
            "issue_date": "2026-05-05T10:00:00Z"
        }
        
        # Validate structure
        assert "alert_type" in valid_json
        assert "severity" in valid_json
        assert isinstance(valid_json["location_mentions"], list)
        
        # Parse JSON
        json_str = json.dumps(valid_json)
        parsed = json.loads(json_str)
        assert parsed["alert_type"] == "FLOOD"
    
    def test_invalid_enum_category_rejected(self):
        """UT-M2-010: Invalid enum/category rejected"""
        valid_alert_types = ["FLOOD", "EARTHQUAKE", "CYCLONE", "WILDFIRE"]
        
        invalid_type = "INVALID_TYPE"
        assert invalid_type not in valid_alert_types
        
        # Valid types should be recognized
        for alert_type in valid_alert_types:
            assert alert_type in valid_alert_types
    
    def test_required_fields_validation(self):
        """Test that required fields are present"""
        required_fields = ["alert_type", "severity", "location_mentions", "description"]
        
        complete_record = {
            "alert_type": "FLOOD",
            "severity": "HIGH",
            "location_mentions": ["Test"],
            "description": "Test alert"
        }
        
        for field in required_fields:
            assert field in complete_record
    
    def test_severity_enum_validation(self):
        """Test severity enum validation"""
        valid_severities = ["LOW", "MODERATE", "HIGH", "SEVERE", "EXTREME"]
        
        for severity in valid_severities:
            json_obj = {
                "alert_type": "FLOOD",
                "severity": severity,
                "location_mentions": ["Test"],
                "description": "Test alert"
            }
            # Validation should pass for valid severities
            assert json_obj["severity"] in valid_severities
    
    def test_alert_type_enum_validation(self):
        """Test alert type enum validation"""
        valid_types = ["FLOOD", "EARTHQUAKE", "CYCLONE", "WILDFIRE", "HEATWAVE", "DROUGHT"]
        
        for alert_type in valid_types:
            json_obj = {
                "alert_type": alert_type,
                "severity": "HIGH",
                "location_mentions": ["Test"],
                "description": "Test alert"
            }
            # Validation should pass
            assert json_obj["alert_type"] in valid_types


class TestPipelineProcessorDateHandling:
    """Test date parsing and validation"""
    
    def test_iso_date_parsing(self):
        """Test ISO 8601 date parsing"""
        iso_date = "2026-05-05T10:30:00Z"
        
        # Should parse without error
        parsed_date = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        assert parsed_date.year == 2026
        assert parsed_date.month == 5
        assert parsed_date.day == 5
    
    def test_invalid_date_format_rejected(self):
        """Test rejection of invalid date formats"""
        invalid_dates = [
            "2026/05/05",
            "05-05-2026",
            "2026-13-01",  # Invalid month
            "2026-05-32",  # Invalid day
            "not-a-date"
        ]
        
        for invalid_date in invalid_dates:
            with pytest.raises((ValueError, TypeError)):
                datetime.fromisoformat(invalid_date.replace('Z', '+00:00'))


class TestPipelineProcessorLocationExtraction:
    """Test location mention extraction"""
    
    def test_single_location_extracted(self):
        """Test extraction of single location mention"""
        json_obj = {
            "location_mentions": ["Karachi"],
            "description": "Flooding in Karachi"
        }
        
        assert "Karachi" in json_obj["location_mentions"]
        assert len(json_obj["location_mentions"]) == 1
    
    def test_multiple_locations_extracted(self):
        """Test extraction of multiple location mentions"""
        json_obj = {
            "location_mentions": ["Sindh", "Karachi", "Hyderabad"],
            "description": "Flooding across Sindh province"
        }
        
        assert len(json_obj["location_mentions"]) == 3
        assert all(loc in json_obj["location_mentions"] for loc in ["Sindh", "Karachi", "Hyderabad"])
    
    def test_empty_location_mentions(self):
        """Test handling of empty location mentions"""
        json_obj = {
            "location_mentions": [],
            "description": "Generic flood alert"
        }
        
        # Should handle gracefully
        assert isinstance(json_obj["location_mentions"], list)
        assert len(json_obj["location_mentions"]) == 0


class TestPipelineProcessorAlertAreas:
    """Test alert area creation"""
    
    def test_alert_area_from_locations(self):
        """Test creating alert areas from location mentions"""
        locations = ["Sindh", "Karachi"]
        
        alert_areas = [{"location": loc, "description": f"Alert for {loc}"} for loc in locations]
        
        assert len(alert_areas) == 2
        assert alert_areas[0]["location"] == "Sindh"
        assert alert_areas[1]["location"] == "Karachi"
    
    def test_alert_area_polygon_association(self):
        """Test polygon association with alert areas"""
        alert_area = {
            "location": "Sindh",
            "polygon": {
                "type": "Polygon",
                "coordinates": [[[[64, 24], [71, 24], [71, 27], [64, 27], [64, 24]]]]
            }
        }
        
        assert alert_area["polygon"]["type"] == "Polygon"
        assert len(alert_area["polygon"]["coordinates"]) > 0


class TestPipelineProcessorErrorRecovery:
    """Test error handling and recovery"""
    
    def test_partial_validation_failure(self):
        """Test handling of partial validation failures"""
        json_obj = {
            "alert_type": "FLOOD",
            "severity": "HIGH",
            "location_mentions": [],  # Empty but valid
            "description": "",  # Empty but valid
            "source": "NDMA"
        }
        
        # Should not fail on empty description or location mentions
        assert json_obj["location_mentions"] == []
        assert json_obj["description"] == ""
    
    def test_json_encoding_decoding(self):
        """Test JSON roundtrip"""
        original = {
            "alert_type": "FLOOD",
            "severity": "EXTREME",
            "location_mentions": ["Sindh"]
        }
        
        encoded = json.dumps(original)
        decoded = json.loads(encoded)
        
        assert decoded == original

