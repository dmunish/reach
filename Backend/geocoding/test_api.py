"""
Example usage and testing guide for the geocoding microservice.

Run this script to test the service manually or as integration tests.
"""

import asyncio
import httpx
import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path


BASE_URL = "http://localhost:8000"
RESULTS_FILE = Path(__file__).parent / "test_results.json"


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


def save_results_to_file(all_results: Dict[str, Any]):
    """
    Save test results to a JSON file with proper formatting.
    
    Args:
        all_results: Dictionary containing all test results
    """
    try:
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\n📝 Results saved to: {RESULTS_FILE}")
    except Exception as e:
        print(f"\n⚠️  Failed to save results: {e}")


async def run_all_tests():
    """Run all tests sequentially and save results."""
    print("Starting integration tests...")
    print("Make sure the service is running: python -m geocoding.main")
    
    # Store all results
    all_results = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL
        },
        "tests": {}
    }
    
    try:
        # Run each test and collect results
        all_results["tests"]["health"] = await test_health()
        all_results["tests"]["simple_place"] = await test_simple_place()
        all_results["tests"]["directional"] = await test_directional()
        all_results["tests"]["batch"] = await test_batch()
        all_results["tests"]["get_endpoint"] = await test_get_endpoint()
        all_results["tests"]["suggestions"] = await test_suggestions()
        
        all_results["summary"] = {
            "status": "success",
            "total_tests": len(all_results["tests"]),
            "message": "All tests completed successfully"
        }
        
        print("\n" + "="*70)
        print("✓ All tests completed!")
        print("="*70)
        
    except Exception as e:
        all_results["summary"] = {
            "status": "failed",
            "error": str(e),
            "message": "Test execution failed"
        }
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Save results to file
    save_results_to_file(all_results)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
