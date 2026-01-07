"""
Example usage and testing guide for the geocoding microservice.

Run this script to test the service manually or as integration tests.
"""

import asyncio
import httpx
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


async def test_simple_place():
    """Test simple place name geocoding."""
    print("\n=== Test 1: Simple Place Name ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/geocode",
            json={
                "locations": ["Islamabad"],
                "options": {
                    "prefer_lower_admin_levels": True,
                    "include_confidence_scores": True
                }
            }
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Results: {result}")
        
        return result


async def test_directional():
    """Test directional description."""
    print("\n=== Test 2: Directional Description ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/geocode",
            json={
                "locations": ["Central Sindh and Balochistan"],
                "options": {
                    "prefer_lower_admin_levels": True,
                    "include_confidence_scores": False
                }
            }
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Results: {result}")
        
        return result


async def test_batch():
    """Test batch geocoding."""
    print("\n=== Test 3: Batch Geocoding ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/geocode",
            json={
                "locations": [
                    "Islamabad",
                    "Northern Punjab",
                    "Karachi",
                    "South-Eastern KPK"
                ],
                "options": {
                    "prefer_lower_admin_levels": True,
                    "include_confidence_scores": True
                }
            }
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Total locations: {len(result['results'])}")
        print(f"Errors: {len(result['errors'])}")
        
        for r in result['results']:
            print(f"\n  {r['input']}:")
            print(f"    Matches: {len(r['matched_places'])}")
            if r['matched_places']:
                print(f"    First match: {r['matched_places'][0]['name']}")
        
        return result


async def test_get_endpoint():
    """Test GET endpoint for single location."""
    print("\n=== Test 4: GET Endpoint ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/geocode/Lahore",
            params={
                "include_confidence_scores": True
            }
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Results: {result}")
        
        return result


async def test_suggestions():
    """Test suggestions endpoint."""
    print("\n=== Test 5: Suggestions ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/suggest/Islmabad",  # Typo
            params={"limit": 5}
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Suggestions for 'Islmabad': {result}")
        
        return result


async def test_health():
    """Test health check."""
    print("\n=== Test 6: Health Check ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/health")
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Health: {result}")
        
        return result


async def run_all_tests():
    """Run all tests sequentially."""
    print("Starting integration tests...")
    print("Make sure the service is running: python -m geocoding.main")
    
    try:
        await test_health()
        await test_simple_place()
        await test_directional()
        await test_batch()
        await test_get_endpoint()
        await test_suggestions()
        
        print("\n" + "="*70)
        print("✓ All tests completed!")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
