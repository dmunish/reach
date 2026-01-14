#!/bin/bash

# Geocoding Microservice - Test Curl Commands
# Run this script to test various geocoding scenarios
#
# Usage:
#   cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests
#   chmod +x test_curl_commands.sh
#   ./test_curl_commands.sh

BASE_URL="http://localhost:8000/api/v1"

echo "=========================================="
echo "Geocoding Microservice - Curl Tests"
echo "=========================================="
echo ""
echo "Make sure the service is running:"
echo "  cd /home/ahmad_shahmeer/reach-geocoding/Backend"
echo "  python -m geocoder"
echo ""
echo "Press Enter to continue..."
read

# Test 1: Simple place name
echo ""
echo "=== Test 1: Simple Place Name - Islamabad ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}' | jq

sleep 1

# Test 2: Simple place name with fuzzy matching
echo ""
echo "=== Test 2: Fuzzy Match - Lahor (typo for Lahore) ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Lahor"]}' | jq

sleep 1

# Test 3: Directional - Northern Region
echo ""
echo "=== Test 3: Directional - Northern Gilgit Baltistan ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Northern Gilgit Baltistan"]}' | jq

sleep 1

# Test 4: Directional - Central Region
echo ""
echo "=== Test 4: Directional - Central Sindh ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Sindh"]}' | jq

sleep 1

# Test 5: Directional - Eastern Region
echo ""
echo "=== Test 5: Directional - Eastern Punjab ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Eastern Punjab"]}' | jq

sleep 1

# Test 6: Directional - South-Western
echo ""
echo "=== Test 6: Directional - South-Western Balochistan ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["South-Western Balochistan"]}' | jq

sleep 1

# Test 7: Directional - North-Eastern
echo ""
echo "=== Test 7: Directional - North-Eastern Khyber Pakhtunkhwa ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["North-Eastern Khyber Pakhtunkhwa"]}' | jq

sleep 1

# Test 8: Multiple locations (batch)
echo ""
echo "=== Test 8: Batch Processing - Multiple Locations ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Islamabad",
      "Karachi",
      "Northern Punjab",
      "Central Sindh"
    ]
  }' | jq

sleep 1

# Test 9: Province-level query
echo ""
echo "=== Test 9: Province-level - Sindh ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Sindh"]}' | jq

sleep 1

# Test 10: District-level query
echo ""
echo "=== Test 10: District-level - Swat ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Swat"]}' | jq

sleep 1

# Test 11: GET endpoint (if available)
echo ""
echo "=== Test 11: GET Endpoint - Single Location ==="
curl -X GET "$BASE_URL/geocode/Lahore" | jq

sleep 1

# Test 12: Suggestions endpoint
echo ""
echo "=== Test 12: Suggestions - Typo 'Islmabad' ==="
curl -X GET "$BASE_URL/suggest/Islmabad?limit=5" | jq

sleep 1

# Test 13: Health check
echo ""
echo "=== Test 13: Health Check ==="
curl -X GET "$BASE_URL/health" | jq

sleep 1

# Test 14: Multiple directional queries
echo ""
echo "=== Test 14: Multiple Directional Queries ==="
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Southern Sindh",
      "Northern Gilgit Baltistan",
      "Western Balochistan",
      "Eastern Punjab"
    ]
  }' | jq

sleep 1

# Test 15: Hierarchical aggregation test - all districts
echo ""
echo "=== Test 15: Test Hierarchical Aggregation ==="
echo "This should show aggregated results (parent if all children matched)"
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Punjab"]}' | jq

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
