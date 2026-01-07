"""
Custom exceptions for the geocoding microservice.

These provide semantic error handling and better debugging.
"""


class GeocodingError(Exception):
    """Base exception for all geocoding errors."""
    pass


class PlaceNotFoundError(GeocodingError):
    """Raised when a place cannot be found in the database or external service."""
    
    def __init__(self, location: str, suggestions=None):
        self.location = location
        self.suggestions = suggestions or []
        message = f"Place not found: {location}"
        if suggestions:
            message += f". Did you mean: {', '.join(s['name'] for s in suggestions[:3])}?"
        super().__init__(message)


class DirectionalParsingError(GeocodingError):
    """Raised when directional parsing fails."""
    pass


class ExternalGeocodingError(GeocodingError):
    """Raised when external geocoding API fails."""
    
    def __init__(self, location: str, reason: str):
        self.location = location
        self.reason = reason
        super().__init__(f"External geocoding failed for '{location}': {reason}")


class DatabaseError(GeocodingError):
    """Raised when database operations fail."""
    
    def __init__(self, operation: str, details: str):
        self.operation = operation
        self.details = details
        super().__init__(f"Database error during {operation}: {details}")


class ConfigurationError(GeocodingError):
    """Raised when configuration is invalid."""
    pass
