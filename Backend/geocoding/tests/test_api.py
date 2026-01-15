"""
Geocoding Microservice - Integration Tests

Run this script to test the service with formatted terminal output.
All results are displayed directly in the terminal (no file output).

Usage:
    python test_api.py
"""

import asyncio
import httpx
import json
import time
from typing import Dict, List, Any, Union
from datetime import datetime


BASE_URL = "http://localhost:8000"

# Terminal colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_json(data: Union[Dict[str, Any], List[Any], Any], indent: int = 0):
    """Pretty print JSON data with colors."""
    indent_str = "  " * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{indent_str}{Colors.CYAN}{key}{Colors.RESET}:")
                print_json(value, indent + 1)
            else:
                print(f"{indent_str}{Colors.CYAN}{key}{Colors.RESET}: {Colors.GREEN}{value}{Colors.RESET}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                print(f"{indent_str}[{i}]:")
                print_json(item, indent + 1)
            else:
                print(f"{indent_str}[{i}]: {Colors.GREEN}{item}{Colors.RESET}")
    else:
        print(f"{indent_str}{Colors.GREEN}{data}{Colors.RESET}")


async def test_simple_place():
    """Test simple place name geocoding."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Test 1: Simple Place Name - Islamabad{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
    
    start_time = time.time()
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
        
        status_color = Colors.GREEN if response.status_code == 200 else Colors.RED
        print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_color}{response.status_code}{Colors.RESET}")
        
        result = response.json()
        print(f"\n{Colors.BOLD}Response:{Colors.RESET}")
        print_json(result)
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.BOLD}{Colors.CYAN}⏱  Time taken: {elapsed:.2f} seconds{Colors.RESET}")
        
        return result


async def test_directional():
    """Test directional description (single region only - no conjunctions)."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Test 2: Directional Description - Central Sindh{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/geocode",
            json={
                "locations": ["Central Sindh"],
                "options": {
                    "prefer_lower_admin_levels": True,
                    "include_confidence_scores": False
                }
            }
        )
        
        status_color = Colors.GREEN if response.status_code == 200 else Colors.RED
        print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_color}{response.status_code}{Colors.RESET}")
        
        result = response.json()
        print(f"\n{Colors.BOLD}Response:{Colors.RESET}")
        print_json(result)
        
        print(f"\n{Colors.YELLOW}Note: Results should show hierarchical aggregation{Colors.RESET}")
        print(f"{Colors.YELLOW}      (parent instead of all children if all present){Colors.RESET}")
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.BOLD}{Colors.CYAN}⏱  Time taken: {elapsed:.2f} seconds{Colors.RESET}")
        
        return result


async def test_batch():
    """Test batch geocoding with multiple directional queries."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Test 3: Batch Geocoding - Multiple Locations{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
    
    start_time = time.time()
    # Use longer timeout for batch processing (60 seconds for multiple directional queries)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/geocode",
            json={
                "locations": [
                    "Islamabad",
                    "Northern Punjab",
                    "Karachi",
                    "South-Eastern Khyber Pakhtunkhwa",
                    "Central Sindh",
                    "Western Balochistan"
                ],
                "options": {
                    "prefer_lower_admin_levels": True,
                    "include_confidence_scores": True
                }
            }
        )
        
        status_color = Colors.GREEN if response.status_code == 200 else Colors.RED
        print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_color}{response.status_code}{Colors.RESET}")
        
        result = response.json()
        print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Total locations: {Colors.GREEN}{len(result['results'])}{Colors.RESET}")
        print(f"  Errors: {Colors.RED if result['errors'] else Colors.GREEN}{len(result['errors'])}{Colors.RESET}")
        
        print(f"\n{Colors.BOLD}Results by Location:{Colors.RESET}")
        for r in result['results']:
            print(f"\n  {Colors.CYAN}{r['input']}{Colors.RESET}:")
            print(f"    Matches: {Colors.GREEN}{len(r['matched_places'])}{Colors.RESET}")
            print(f"    Direction: {Colors.YELLOW}{r.get('direction', 'N/A')}{Colors.RESET}")
            if r['matched_places']:
                first = r['matched_places'][0]
                print(f"    First: {Colors.GREEN}{first['name']}{Colors.RESET} (Level {first['hierarchy_level']})")
                if len(r['matched_places']) > 1:
                    last = r['matched_places'][-1]
                    print(f"    Last: {Colors.GREEN}{last['name']}{Colors.RESET} (Level {last['hierarchy_level']})")
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.BOLD}{Colors.CYAN}⏱  Time taken: {elapsed:.2f} seconds{Colors.RESET}")
        
        return result


async def test_get_endpoint():
    """Test GET endpoint for single location."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Test 4: GET Endpoint - Single Location{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/geocode/Lahore",
            params={"include_confidence_scores": True}
        )
        
        status_color = Colors.GREEN if response.status_code == 200 else Colors.RED
        print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_color}{response.status_code}{Colors.RESET}")
        
        result = response.json()
        print(f"\n{Colors.BOLD}Response:{Colors.RESET}")
        print_json(result)
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.BOLD}{Colors.CYAN}⏱  Time taken: {elapsed:.2f} seconds{Colors.RESET}")
        
        return result


async def test_suggestions():
    """Test suggestions endpoint."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Test 5: Suggestions - Typo 'Islmabad'{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/suggest/Islmabad",
            params={"limit": 5}
        )
        
        status_color = Colors.GREEN if response.status_code == 200 else Colors.RED
        print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_color}{response.status_code}{Colors.RESET}")
        
        result = response.json()
        print(f"\n{Colors.BOLD}Suggestions:{Colors.RESET}")
        print_json(result)
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.BOLD}{Colors.CYAN}⏱  Time taken: {elapsed:.2f} seconds{Colors.RESET}")
        
        return result


async def test_health():
    """Test health check."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Test 6: Health Check{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/health")
        
        status_color = Colors.GREEN if response.status_code == 200 else Colors.RED
        print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_color}{response.status_code}{Colors.RESET}")
        
        result = response.json()
        print(f"\n{Colors.BOLD}Health Status:{Colors.RESET}")
        print_json(result)
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.BOLD}{Colors.CYAN}⏱  Time taken: {elapsed:.2f} seconds{Colors.RESET}")
        
        return result


async def run_all_tests():
    """Run all tests sequentially with formatted output."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  Geocoding Microservice - Integration Tests{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"\n{Colors.YELLOW}Base URL:{Colors.RESET} {BASE_URL}")
    print(f"{Colors.YELLOW}Timestamp:{Colors.RESET} {datetime.now().isoformat()}")
    print(f"\n{Colors.YELLOW}Make sure the service is running:{Colors.RESET}")
    print(f"  cd /home/ahmad_shahmeer/reach-geocoding/Backend")
    print(f"  python -m geocoder")
    
    try:
        # Run each test
        await test_health()
        await asyncio.sleep(0.5)
        
        await test_simple_place()
        await asyncio.sleep(0.5)
        
        await test_directional()
        await asyncio.sleep(0.5)
        
        await test_batch()
        await asyncio.sleep(0.5)
        
        await test_get_endpoint()
        await asyncio.sleep(0.5)
        
        await test_suggestions()
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}  ✓ All Tests Completed Successfully!{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.RESET}\n")
        
    except httpx.ConnectError:
        print(f"\n{Colors.BOLD}{Colors.RED}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}  ✗ Connection Error{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}{'='*70}{Colors.RESET}")
        print(f"\n{Colors.RED}Could not connect to {BASE_URL}{Colors.RESET}")
        print(f"{Colors.YELLOW}Make sure the service is running:{Colors.RESET}")
        print(f"  cd /home/ahmad_shahmeer/reach-geocoding/Backend")
        print(f"  python -m geocoder\n")
        
    except Exception as e:
        print(f"\n{Colors.BOLD}{Colors.RED}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}  ✗ Test Failed{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}{'='*70}{Colors.RESET}")
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())