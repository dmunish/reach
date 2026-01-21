#!/bin/bash

# Geocoding Microservice - Comprehensive Test Suite
#
# This script runs 15 different test scenarios and tracks execution time for each.
# Tests include:
#   - Simple place names (Islamabad, Lahore)
#   - Fuzzy matching (typo handling)
#   - Directional queries (8 compass directions)
#   - Province and district level queries
#   - Batch processing
#   - Hierarchical aggregation
#   - GET/Suggestions endpoints
#   - Health check
#
# Output:
#   - Formatted results showing place names and hierarchy levels
#   - Execution time summary table at the end
#   - Total execution time
#
# Performance Expectations:
#   - First run (cold cache): ~3-5 minutes
#   - Second run (warm cache): ~5-10 seconds (20-50x faster with Redis)
#
# Usage:
#   cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests
#   chmod +x test_curl_commands.sh
#   ./test_curl_commands.sh
#
# Prerequisites:
#   - Service must be running: python -m geocoder (from Backend directory)
#   - jq must be installed: sudo apt install jq
#   - bc must be installed: sudo apt install bc (for timing calculations)

BASE_URL="http://localhost:8000/api/v1"

# Arrays to track test timings
declare -a test_names
declare -a test_durations

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
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Islamabad"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 1: Simple Place Name")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 2: Simple place name with fuzzy matching
echo ""
echo "=== Test 2: Fuzzy Match - Lahor (typo for Lahore) ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Lahor"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 2: Fuzzy Match")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 3: Directional - Northern Region
echo ""
echo "=== Test 3: Directional - Northern Gilgit Baltistan ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Northern Gilgit Baltistan"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 3: Directional - Northern")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 4: Directional - Central Region
echo ""
echo "=== Test 4: Directional - Central Sindh ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Sindh"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 4: Directional - Central")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 5: Directional - Eastern Region
echo ""
echo "=== Test 5: Directional - Eastern Punjab ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Eastern Punjab"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 5: Directional - Eastern")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 6: Directional - South-Western
echo ""
echo "=== Test 6: Directional - South-Western Balochistan ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["South-Western Balochistan"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 6: Directional - South-Western")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 7: Directional - North-Eastern
echo ""
echo "=== Test 7: Directional - North-Eastern Khyber Pakhtunkhwa ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["North-Eastern Khyber Pakhtunkhwa"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 7: Directional - North-Eastern")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 8: Multiple locations (batch)
echo ""
echo "=== Test 8: Batch Processing - Multiple Locations ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Islamabad",
      "Karachi",
      "Northern Punjab",
      "Central Sindh"
    ]
  }' | jq '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 8: Batch Processing")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 9: Province-level query
echo ""
echo "=== Test 9: Province-level - Sindh ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Sindh"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 9: Province-level")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 10: District-level query
echo ""
echo "=== Test 10: District-level - Swat ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Swat"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 10: District-level")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 11: GET endpoint (if available)
echo ""
echo "=== Test 11: GET Endpoint - Single Location ==="
start=$(date +%s.%N)
curl -X GET "$BASE_URL/geocode/Lahore" | jq '.matched_places[]? | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 11: GET Endpoint")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 12: Suggestions endpoint
echo ""
echo "=== Test 12: Suggestions - Typo 'Islmabad' ==="
start=$(date +%s.%N)
curl -X GET "$BASE_URL/suggest/Islmabad?limit=5" | jq '.suggestions[]? | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 12: Suggestions")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 13: Health check
echo ""
echo "=== Test 13: Health Check ==="
start=$(date +%s.%N)
curl -X GET "$BASE_URL/health" | jq
end=$(date +%s.%N)
test_names+=("Test 13: Health Check")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 14: Multiple directional queries
echo ""
echo "=== Test 14: Multiple Directional Queries ==="
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      "Southern Sindh",
      "Northern Gilgit Baltistan",
      "Western Balochistan",
      "Eastern Punjab"
    ]
  }' | jq '.results[] | .matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 14: Multiple Directional")
test_durations+=($(echo "$end - $start" | bc))

sleep 1

# Test 15: Hierarchical aggregation test - all districts
echo ""
echo "=== Test 15: Test Hierarchical Aggregation ==="
echo "This should show aggregated results (parent if all children matched)"
start=$(date +%s.%N)
curl -X POST "$BASE_URL/geocode" \
  -H "Content-Type: application/json" \
  -d '{"locations": ["Central Punjab"]}' | jq '.results[0].matched_places[] | "\(.name) (Level \(.hierarchy_level))"'
end=$(date +%s.%N)
test_names+=("Test 15: Hierarchical Aggregation")
test_durations+=($(echo "$end - $start" | bc))

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
echo ""
echo "=========================================="
echo "Test Execution Summary"
echo "=========================================="
printf "%-40s %s\n" "Test Category" "Execution Time (s)"
echo "----------------------------------------------------------"

# Print each test with its duration
for i in "${!test_names[@]}"; do
  printf "%-40s %s\n" "${test_names[$i]}" "${test_durations[$i]}"
done

echo "----------------------------------------------------------"

# Calculate total time
total=0
for duration in "${test_durations[@]}"; do
  total=$(echo "$total + $duration" | bc)
done

printf "%-40s %s\n" "TOTAL" "$total"
echo "=========================================="
