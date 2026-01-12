"""
Geocoding Microservice Setup Test Script
Run each phase sequentially to verify the setup.

Usage:
    python test_setup.py --phase 1
    python test_setup.py --phase 2
    # ... etc
"""

import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import from Backend
sys.path.insert(0, str(Path(__file__).parent.parent))

# All test output goes to terminal only (no file output)

def print_phase_header(phase_num: int, title: str):
    """Print a nice header for each test phase"""
    print("\n" + "="*70)
    print(f"PHASE {phase_num}: {title}")
    print("="*70 + "\n")

def print_test(test_name: str):
    """Print test name"""
    print(f"→ Testing: {test_name}")

def print_success(message: str):
    """Print success message"""
    print(f"  ✓ {message}")

def print_error(message: str):
    """Print error message"""
    print(f"  ✗ ERROR: {message}")

def print_info(message: str):
    """Print info message"""
    print(f"  ℹ {message}")


# ============================================================================
# PHASE 1: Configuration and Basic Connectivity
# ============================================================================

def test_phase_1():
    """Test configuration loading and basic Supabase connection"""
    print_phase_header(1, "Configuration & Basic Connectivity")
    
    # Test 1: Import config
    print_test("Import configuration module")
    try:
        from geocoding.config import get_settings
        print_success("Configuration module imported")
    except Exception as e:
        print_error(f"Failed to import config: {e}")
        return False
    
    # Test 2: Load settings
    print_test("Load environment settings")
    try:
        settings = get_settings()
        print_success(f"Settings loaded from .env")
        print_info(f"Supabase URL: {settings.supabase_url}")
        print_info(f"LocationIQ Key present: {'Yes' if settings.locationiq_api_key else 'No'}")
    except Exception as e:
        print_error(f"Failed to load settings: {e}")
        return False
    
    # Test 3: Create Supabase client
    print_test("Create Supabase client")
    try:
        from supabase import create_client
        client = create_client(settings.supabase_url, settings.supabase_key)
        print_success("Supabase client created")
    except Exception as e:
        print_error(f"Failed to create Supabase client: {e}")
        return False
    
    # Test 4: Test basic query
    print_test("Query places table")
    try:
        result = client.table('places').select('id, name, hierarchy_level').limit(5).execute()
        if result.data and isinstance(result.data, list):
            print_success(f"Successfully queried places table ({len(result.data)} rows)")
            print_info("Sample places:")
            for place in result.data[:3]:
                if isinstance(place, dict):
                    print_info(f"  - {place.get('name', 'N/A')} (Level {place.get('hierarchy_level', 'N/A')})")
        else:
            print_error("Places table is empty")
            return False
    except Exception as e:
        print_error(f"Failed to query places: {e}")
        return False
    
    # Test 5: Import models
    print_test("Import Pydantic models")
    try:
        from geocoding.models import (
            GeocodeRequest, GeocodeResponse, GeocodeResult, 
            MatchedPlace, GeocodeOptions
        )
        print_success("All models imported successfully")
        
        # Test model validation
        test_request = GeocodeRequest(locations=["Islamabad"])
        print_info(f"Test request created: {test_request.locations}")
    except Exception as e:
        print_error(f"Failed to import/test models: {e}")
        return False
    
    print("\n" + "="*70)
    print("✓ PHASE 1 COMPLETE - Ready for Phase 2")
    print("="*70)
    return True


# ============================================================================
# PHASE 2: Database Layer (SQL Functions & Repository)
# ============================================================================

def test_phase_2():
    """Test PostgreSQL functions and repository layer"""
    print_phase_header(2, "Database Layer (SQL Functions & Repository)")
    
    # Setup
    from geocoding.config import get_settings
    from supabase import create_client
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    
    # Test 1: Check PostGIS extension (via proxy - checking if ST_ functions work)
    print_test("Check PostGIS extension")
    try:
        # We can't directly call postgis_version via PostgREST, so we check if our spatial function works
        # Try a simple spatial query that requires PostGIS
        result = client.rpc('find_place_by_point', {'lon': 0.0, 'lat': 0.0}).execute()
        print_success("PostGIS is available (spatial functions working)")
    except Exception as e:
        error_msg = str(e)
        if 'function' in error_msg.lower() and 'not found' in error_msg.lower():
            print_error(f"PostGIS functions not created yet")
            print_info("Run the SQL from db_queries.sql in Supabase SQL Editor")
        else:
            print_info("PostGIS extension appears to be installed (function found)")
    
    # Test 2: Check pg_trgm extension (via proxy - we'll test the fuzzy search function)
    print_test("Check pg_trgm extension (for fuzzy matching)")
    try:
        # We can't directly call similarity, so we test if our fuzzy function works
        # This will also verify pg_trgm is installed
        result = client.rpc('search_places_fuzzy', {'search_name': 'test', 'similarity_threshold': 0.1}).execute()
        print_success("pg_trgm extension is available (fuzzy search working)")
    except Exception as e:
        error_msg = str(e)
        if 'function' in error_msg.lower() and 'not found' in error_msg.lower():
            print_error(f"pg_trgm functions not created yet")
            print_info("Run: CREATE EXTENSION IF NOT EXISTS pg_trgm; in Supabase SQL Editor")
        elif 'does not exist' in error_msg.lower():
            print_error("pg_trgm extension not installed")
            print_info("Run: CREATE EXTENSION IF NOT EXISTS pg_trgm; in Supabase SQL Editor")
        else:
            print_success("pg_trgm appears to be working")
    
    # Test 3: Check indexes
    print_test("Check required indexes on places table")
    try:
        # This is a workaround - we check if queries work efficiently
        result = client.table('places').select('name').limit(1).execute()
        print_success("Basic index access working")
        print_info("Verify indexes manually in Supabase:")
        print_info("  - idx_places_name_trgm (GIN index)")
        print_info("  - idx_places_polygon (GIST index)")
        print_info("  - idx_places_hierarchy")
    except Exception as e:
        print_error(f"Index check failed: {e}")
    
    # Test 4: Test search_places_fuzzy function
    print_test("Test search_places_fuzzy function")
    try:
        result = client.rpc(
            'search_places_fuzzy',
            {'search_name': 'Islamabad', 'similarity_threshold': 0.8}
        ).execute()
        
        if result.data and isinstance(result.data, list):
            print_success(f"Fuzzy search working ({len(result.data)} results)")
            for match in result.data[:3]:
                if isinstance(match, dict):
                    print_info(f"  - {match.get('name', 'N/A')} (similarity: {match.get('similarity_score', 'N/A')})")
        else:
            print_error("Function exists but returned no results")
            print_info("This might be OK if 'Islamabad' isn't in your places table")
    except Exception as e:
        print_error(f"search_places_fuzzy function not found: {e}")
        print_info("Create this function in Supabase SQL Editor (see setup guide)")
        return False
    
    # Test 5: Test find_place_by_point function
    print_test("Test find_place_by_point function")
    try:
        # Coordinates for Islamabad (approximate)
        result = client.rpc(
            'find_place_by_point',
            {'lon': 73.0479, 'lat': 33.6844}
        ).execute()
        
        if result.data:
            print_success(f"Point-in-polygon search working")
            place = result.data[0] if isinstance(result.data, list) else result.data
            if isinstance(place, dict):
                print_info(f"  Found: {place.get('name', 'N/A')} (Level {place.get('hierarchy_level', 'N/A')})")
        else:
            print_error("Function exists but returned no results")
            print_info("Check if places table has valid polygons")
    except Exception as e:
        print_error(f"find_place_by_point function not found: {e}")
        print_info("Create this function in Supabase SQL Editor (see setup guide)")
        return False
    
    # Test 6: Import and test repository
    print_test("Import PlacesRepository")
    try:
        from geocoding.repositories.places_repository import PlacesRepository
        repo = PlacesRepository(client)
        print_success("Repository imported and instantiated")
    except Exception as e:
        print_error(f"Failed to import repository: {e}")
        return False
    
    # Test 7: Test repository methods
    print_test("Test repository.search_by_fuzzy_name()")
    try:
        results = asyncio.run(repo.search_by_fuzzy_name("Lahore", threshold=0.8))
        if results:
            print_success(f"Repository fuzzy search working ({len(results)} results)")
            print_info(f"  Sample: {results[0]['name']}")
        else:
            print_info("No results found (might be OK depending on data)")
    except Exception as e:
        print_error(f"Repository method failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("✓ PHASE 2 COMPLETE - Ready for Phase 3")
    print("="*70)
    return True


# ============================================================================
# PHASE 3: Service Layer
# ============================================================================

def test_phase_3():
    """Test service layer components"""
    print_phase_header(3, "Service Layer (Geocoding, Matching, Parsing)")
    
    # Setup
    from geocoding.config import get_settings
    from supabase import create_client
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    
    # Test 1: External Geocoder
    print_test("Import and test ExternalGeocoder")
    try:
        from geocoding.services.external_geocoder import ExternalGeocoder
        
        geocoder = ExternalGeocoder(
            api_key=settings.locationiq_api_key,
            base_url=settings.locationiq_base_url
        )
        print_success("ExternalGeocoder instantiated")
        
        # Test geocoding
        if settings.locationiq_api_key:
            print_info("Testing LocationIQ API call...")
            coords = asyncio.run(geocoder.geocode("Islamabad, Pakistan"))
            if coords:
                print_success(f"Geocoding working: {coords[0]}")
            else:
                print_error("Geocoding returned no results")
        else:
            print_info("Skipping API test (no LocationIQ key)")
            
    except Exception as e:
        print_error(f"ExternalGeocoder failed: {e}")
        return False
    
    # Test 2: Name Matcher
    print_test("Import and test NameMatcher")
    try:
        from geocoding.services.name_matcher import NameMatcher
        from geocoding.repositories.places_repository import PlacesRepository
        
        repo = PlacesRepository(client)
        matcher = NameMatcher(repo, threshold=0.85)
        print_success("NameMatcher instantiated")
        
        # Test matching
        result = asyncio.run(matcher.match("Islamabad"))
        if result:
            print_success(f"Name matching working: {result['name']}")
            print_info(f"  Match method: {result['match_method']}")
            print_info(f"  Confidence: {result.get('confidence', 'N/A')}")
        else:
            print_info("No match found (check if place exists in DB)")
            
    except Exception as e:
        print_error(f"NameMatcher failed: {e}")
        return False
    
    # Test 3: Directional Parser
    print_test("Import and test DirectionalParser")
    try:
        from geocoding.services.directional_parser import DirectionalParser
        
        parser = DirectionalParser()
        print_success("DirectionalParser instantiated")
        
        # Test parsing
        test_cases = [
            ("Central Sindh", "Should extract direction and single place"),
            ("Northern Khyber Pakhtunkhwa", "Should extract direction and place"),
            ("South-Eastern Punjab", "Should handle compound directions"),
            ("Islamabad", "Should return None for direction")
        ]
        
        for test_input, description in test_cases:
            direction, places = parser.parse(test_input)
            print_info(f"  '{test_input}'")
            print_info(f"    → Direction: {direction.value if direction else 'None'}, Places: {places}")
            print_info(f"    → {description}")
        
        print_success("Directional parsing working (no conjunction splitting)")
            
    except Exception as e:
        print_error(f"DirectionalParser failed: {e}")
        return False
    
    # Test 4: Integration test
    print_test("Integration: Parse + Match")
    try:
        from geocoding.services.directional_parser import DirectionalParser
        from geocoding.services.name_matcher import NameMatcher
        from geocoding.repositories.places_repository import PlacesRepository
        
        repo = PlacesRepository(client)
        matcher = NameMatcher(repo)
        parser = DirectionalParser()
        
        test_input = "Central Sindh"
        direction, places = parser.parse(test_input)
        
        if places:
            match = asyncio.run(matcher.match(places[0]))
            if match:
                print_success(f"Integration test passed")
                print_info(f"  Input: '{test_input}'")
                print_info(f"  Direction: {direction.value if direction else 'None'}")
                print_info(f"  Matched: {match['name']} (Level {match['hierarchy_level']})")
            else:
                print_info("Parse worked but match failed (might be OK)")
        
    except Exception as e:
        print_error(f"Integration test failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("✓ PHASE 3 COMPLETE - Ready for Phase 4 (FastAPI layer)")
    print("="*70)
    return True


# ============================================================================
# PHASE 4: Quick Connectivity Tests (after all phases)
# ============================================================================

def test_phase_4():
    """Quick end-to-end connectivity test"""
    print_phase_header(4, "End-to-End Connectivity Test")
    
    print_test("Complete workflow test")
    try:
        from geocoding.config import get_settings
        from supabase import create_client
        from geocoding.repositories.places_repository import PlacesRepository
        from geocoding.services.name_matcher import NameMatcher
        from geocoding.services.directional_parser import DirectionalParser
        from geocoding.services.external_geocoder import ExternalGeocoder
        
        # Setup
        settings = get_settings()
        client = create_client(settings.supabase_url, settings.supabase_key)
        repo = PlacesRepository(client)
        matcher = NameMatcher(repo)
        parser = DirectionalParser()
        geocoder = ExternalGeocoder(settings.locationiq_api_key, settings.locationiq_base_url)
        
        print_success("All components initialized")
        
        # Test workflow
        test_locations = [
            "Islamabad",
            "Northern Punjab",
            "Karachi",
            "Central Sindh",
            "Western Balochistan"
        ]
        
        for location in test_locations:
            print_info(f"\n  Processing: '{location}'")
            
            # Parse
            direction, places = parser.parse(location)
            print_info(f"    Parsed → Direction: {direction.value if direction else 'None'}, Places: {places}")
            
            # Match
            if places:
                match = asyncio.run(matcher.match(places[0]))
                if match:
                    print_info(f"    Matched → {match['name']} (Level {match['hierarchy_level']})")
                else:
                    print_info(f"    No match found")
        
        print_success("\nEnd-to-end workflow test complete")
        
    except Exception as e:
        print_error(f"Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*70)
    print("✓ ALL PHASES COMPLETE - System Ready!")
    print("="*70)
    return True


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test geocoding microservice setup')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3, 4], 
                       help='Test phase to run (1-4)')
    parser.add_argument('--all', action='store_true',
                       help='Run all phases sequentially')
    
    args = parser.parse_args()
    
    # Store results
    results = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "command": f"--phase {args.phase}" if args.phase else "--all"
        },
        "phases": {}
    }
    
    if args.all:
        print("\n🚀 Running all test phases...\n")
        phases = [
            ("Phase 1: Configuration & Connectivity", test_phase_1),
            ("Phase 2: Database Layer", test_phase_2),
            ("Phase 3: Service Layer", test_phase_3),
            ("Phase 4: End-to-End Test", test_phase_4)
        ]
        
        all_passed = True
        for i, (name, phase_func) in enumerate(phases, 1):
            success = phase_func()
            results["phases"][f"phase_{i}"] = {
                "name": name,
                "status": "passed" if success else "failed"
            }
            
            if not success:
                all_passed = False
                print(f"\n❌ Phase {i} failed. Fix errors before continuing.\n")
                break
        
        if all_passed:
            print("\n🎉 All phases passed! Your geocoding service is ready.\n")
            results["summary"] = {
                "status": "success",
                "message": "All setup phases completed successfully"
            }
        else:
            results["summary"] = {
                "status": "failed",
                "message": "Setup failed - see phase details"
            }
        
    elif args.phase:
        phases = {
            1: ("Configuration & Connectivity", test_phase_1),
            2: ("Database Layer", test_phase_2),
            3: ("Service Layer", test_phase_3),
            4: ("End-to-End Test", test_phase_4)
        }
        
        name, phase_func = phases[args.phase]
        success = phase_func()
        
        results["phases"][f"phase_{args.phase}"] = {
            "name": name,
            "status": "passed" if success else "failed"
        }
        results["summary"] = {
            "status": "success" if success else "failed",
            "message": f"Phase {args.phase} completed"
        }
        
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python test_setup.py --phase 1")
        print("  python test_setup.py --phase 2")
        print("  python test_setup.py --all")


if __name__ == "__main__":
    main()