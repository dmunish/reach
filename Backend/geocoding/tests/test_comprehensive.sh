#!/bin/bash

# ============================================================================
# COMPREHENSIVE GEOCODING ACCURACY TEST SUITE - FINAL VALIDATION
# ============================================================================
#
# This script combines all test cases from test_curl_commands.sh and 
# test_curl_commands_2.sh, plus additional edge cases to stress-test the
# geocoder's accuracy, hierarchy logic, and spatial boundary handling.
#
# Test Categories:
#   1. Simple Place Names (exact matches)
#   2. Fuzzy Matching (typo tolerance)
#   3. Directional Queries (8 compass directions + combinations)
#   4. Cross-Border Boundary Tests (province locking)
#   5. Hierarchy Precision (Level 2 vs Level 3 disambiguation)
#   6. Enclave & Sub-division Handling (tehsils, towns)
#   7. Batch Processing (multiple locations, aggregation)
#   8. GET/Suggestions Endpoints
#   9. Health Check
#
# Output:
#   - Color-coded test results with countdown timers
#   - Place names with hierarchy levels
#   - Count of results per test
#   - Execution time summary table
#   - Final results exported to test_results.txt
#
# Performance Expectations:
#   - First run (cold cache): ~5-8 minutes (40+ tests)
#   - Second run (warm cache): ~15-25 seconds (Redis caching)
#
# Usage:
#   cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding/tests
#   chmod +x test_comprehensive.sh
#   ./test_comprehensive.sh
#
# Prerequisites:
#   - Service running: python -m geocoding (from Backend directory)
#   - jq installed: sudo apt install jq
#   - bc installed: sudo apt install bc
# ============================================================================

BASE_URL="http://localhost:8000/api/v1"
RESULTS_FILE="test_results.txt"

# Color codes (basic, no emojis)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Arrays to track test results
declare -a test_names
declare -a test_durations
declare -a test_result_counts

# Initialize results file
echo "============================================================================" > "$RESULTS_FILE"
echo "GEOCODING MICROSERVICE - COMPREHENSIVE TEST RESULTS" >> "$RESULTS_FILE"
echo "Test Date: $(date)" >> "$RESULTS_FILE"
echo "============================================================================" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Function to run a test and capture results
run_test() {
    local test_num=$1
    local test_name=$2
    local curl_command=$3
    local test_type=${4:-"POST"} # POST, GET, or SUGGEST
    
    echo "" | tee -a "$RESULTS_FILE"
    echo -e "${BLUE}=== Test #$test_num: $test_name ===${NC}" | tee -a "$RESULTS_FILE"
    
    start=$(date +%s.%N)
    
    # Execute curl and capture output
    if [[ "$test_type" == "HEALTH" ]]; then
        response=$(eval "$curl_command")
        echo "$response" | jq '.' | tee -a "$RESULTS_FILE"
        result_count=1
    else
        response=$(eval "$curl_command")
        
        # Extract and format results
        if [[ "$test_type" == "SUGGEST" ]]; then
            results=$(echo "$response" | jq -r '.suggestions[]? | "\(.name) (Level \(.hierarchy_level))"' 2>/dev/null)
            result_count=$(echo "$response" | jq '.suggestions | length' 2>/dev/null || echo 0)
        elif [[ "$test_type" == "GET" ]]; then
            # GET endpoint returns same structure as POST: .results[].matched_places[]
            results=$(echo "$response" | jq -r '.results[]? | .matched_places[]? | "\(.name) (Level \(.hierarchy_level))"' 2>/dev/null)
            result_count=$(echo "$response" | jq '[.results[]? | .matched_places[]?] | length' 2>/dev/null || echo 0)
        else
            # POST endpoint - can have multiple results
            results=$(echo "$response" | jq -r '.results[]? | .matched_places[]? | "\(.name) (Level \(.hierarchy_level))"' 2>/dev/null)
            result_count=$(echo "$response" | jq '[.results[]? | .matched_places[]?] | length' 2>/dev/null || echo 0)
        fi
        
        # Display results
        if [[ -n "$results" ]]; then
            echo -e "${GREEN}$results${NC}" | tee -a "$RESULTS_FILE"
        else
            echo -e "${RED}No results returned${NC}" | tee -a "$RESULTS_FILE"
            result_count=0
        fi
    fi
    
    end=$(date +%s.%N)
    duration=$(echo "$end - $start" | bc)
    
    # Display result count
    echo -e "${YELLOW}Result Count: $result_count places${NC}" | tee -a "$RESULTS_FILE"
    
    # Store for summary
    test_names+=("$test_name")
    test_durations+=("$duration")
    test_result_counts+=("$result_count")
    
    sleep 1
}

# ============================================================================
# HEADER
# ============================================================================
clear
echo "============================================================================"
echo "     GEOCODING MICROSERVICE - COMPREHENSIVE ACCURACY TEST SUITE"
echo "============================================================================"
echo ""
echo "Total Tests: 42"
echo "Estimated Time: 5-8 minutes (cold cache), 15-25 seconds (warm cache)"
echo ""
echo "Make sure the service is running:"
echo "  cd /home/ahmad_shahmeer/reach-geocoding/Backend"
echo "  python -m geocoding"
echo ""
echo "Results will be saved to: $RESULTS_FILE"
echo ""
echo "Press Enter to begin testing..."
read

# ============================================================================
# SECTION 1: SIMPLE PLACE NAMES (Exact Matches)
# ============================================================================
echo ""
echo "==========================================================================="
echo -e "${BLUE}SECTION 1: SIMPLE PLACE NAMES (Exact Match Tests)${NC}"
echo "==========================================================================="
echo ""

run_test 1 "Simple - Islamabad" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Islamabad"]}'"'"'' \
  "POST"

run_test 2 "Simple - Karachi" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Karachi"]}'"'"'' \
  "POST"

run_test 3 "Simple - Lahore" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Lahore"]}'"'"'' \
  "POST"

run_test 4 "Simple - Peshawar (Popularity vs Precision)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Peshawar"]}'"'"'' \
  "POST"

run_test 5 "Simple - Quetta" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Quetta"]}'"'"'' \
  "POST"

run_test 6 "Simple - Multan" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Multan"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 2: FUZZY MATCHING (Typo Tolerance)
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 2: FUZZY MATCHING (Typo Tolerance Tests)${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 7 "Fuzzy - Lahor (typo for Lahore)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Lahor"]}'"'"'' \
  "POST"

run_test 8 "Fuzzy - Multn (typo for Multan)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Multn"]}'"'"'' \
  "POST"

run_test 9 "Fuzzy - Peshwar (typo for Peshawar)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Peshwar"]}'"'"'' \
  "POST"

run_test 10 "Fuzzy - Islmabad (typo for Islamabad)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Islmabad"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 3: DIRECTIONAL QUERIES (8 Compass Directions)
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 3: DIRECTIONAL QUERIES (Spatial Boundary Tests)${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 11 "Directional - Northern Gilgit Baltistan" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Northern Gilgit Baltistan"]}'"'"'' \
  "POST"

run_test 12 "Directional - Southern Punjab" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Southern Punjab"]}'"'"'' \
  "POST"

run_test 13 "Directional - Eastern Punjab" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Eastern Punjab"]}'"'"'' \
  "POST"

run_test 14 "Directional - Western Punjab" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Western Punjab"]}'"'"'' \
  "POST"

run_test 15 "Directional - Central Sindh" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Central Sindh"]}'"'"'' \
  "POST"

run_test 16 "Directional - South-Eastern Sindh" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["South-Eastern Sindh"]}'"'"'' \
  "POST"

run_test 17 "Directional - Central Balochistan" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Central Balochistan"]}'"'"'' \
  "POST"

run_test 18 "Directional - South-Western Balochistan" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["South-Western Balochistan"]}'"'"'' \
  "POST"

run_test 19 "Directional - North-Western Balochistan" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["North-Western Balochistan"]}'"'"'' \
  "POST"

run_test 20 "Directional - North-Eastern Khyber Pakhtunkhwa" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["North-Eastern Khyber Pakhtunkhwa"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 4: CROSS-BORDER BOUNDARY TESTS (Edge Cases)
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 4: CROSS-BORDER TESTS (Province Locking Validation)${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 21 "Cross-Border - Northern Sindh (should NOT return Punjab districts)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Northern Sindh"]}'"'"'' \
  "POST"

run_test 22 "Cross-Border - Western Khyber Pakhtunkhwa (should NOT return Balochistan)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Western Khyber Pakhtunkhwa"]}'"'"'' \
  "POST"

run_test 23 "Cross-Border - Eastern Balochistan (should NOT return Punjab)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Eastern Balochistan"]}'"'"'' \
  "POST"

run_test 24 "Cross-Border - Western Sindh (should NOT return Balochistan)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Western Sindh"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 5: HIERARCHY PRECISION TESTS (Level 2 vs Level 3)
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 5: HIERARCHY PRECISION (District vs Tehsil Disambiguation)${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 25 "Hierarchy - Quetta City vs Quetta (should return L3 for 'Quetta City')" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Quetta City"]}'"'"'' \
  "POST"

run_test 26 "Hierarchy - Swat District" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Swat"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 6: ENCLAVE & SUB-DIVISION HANDLING
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 6: ENCLAVE & SUB-DIVISION TESTS${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 27 "Enclave - Orangi (Karachi subdivision without 'Karachi' in query)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Orangi"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 7: BATCH PROCESSING & AGGREGATION
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 7: BATCH PROCESSING & AGGREGATION TESTS${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 28 "Batch - Multiple Cities" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Islamabad", "Karachi", "Northern Punjab", "Central Sindh"]}'"'"'' \
  "POST"

run_test 29 "Batch - Different Province Combo" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Peshawar", "Quetta", "Western Sindh", "Northern Punjab"]}'"'"'' \
  "POST"

run_test 30 "Batch - Multiple Directional" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Southern Sindh", "Northern Gilgit Baltistan", "Western Balochistan", "Eastern Punjab"]}'"'"'' \
  "POST"

run_test 31 "Batch - All Major Cities" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Islamabad", "Lahore", "Karachi", "Peshawar", "Quetta", "Multan", "Faisalabad"]}'"'"'' \
  "POST"

run_test 32 "Aggregation - Central Punjab (should show aggregated districts)" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Central Punjab"]}'"'"'' \
  "POST"

run_test 33 "Aggregation - Southern Sindh" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Southern Sindh"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 8: PROVINCE-LEVEL QUERIES
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 8: PROVINCE-LEVEL QUERIES${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 34 "Province - Punjab" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Punjab"]}'"'"'' \
  "POST"

run_test 35 "Province - Sindh" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Sindh"]}'"'"'' \
  "POST"

run_test 36 "Province - Khyber Pakhtunkhwa" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Khyber Pakhtunkhwa"]}'"'"'' \
  "POST"

run_test 37 "Province - Balochistan" \
  'curl -s -X POST "$BASE_URL/geocode" -H "Content-Type: application/json" -d '"'"'{"locations": ["Balochistan"]}'"'"'' \
  "POST"

# ============================================================================
# SECTION 9: GET & SUGGESTIONS ENDPOINTS
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 9: GET & SUGGESTIONS ENDPOINTS${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 38 "GET - Lahore" \
  'curl -s -X GET "$BASE_URL/geocode/Lahore"' \
  "GET"

run_test 39 "GET - Karachi" \
  'curl -s -X GET "$BASE_URL/geocode/Karachi"' \
  "GET"

run_test 40 "Suggestions - Islmabad (typo)" \
  'curl -s -X GET "$BASE_URL/suggest/Islmabad?limit=5"' \
  "SUGGEST"

run_test 41 "Suggestions - Peshwar (typo)" \
  'curl -s -X GET "$BASE_URL/suggest/Peshwar?limit=5"' \
  "SUGGEST"

# ============================================================================
# SECTION 10: HEALTH CHECK
# ============================================================================
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}SECTION 10: HEALTH CHECK${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

run_test 42 "Health Check" \
  'curl -s -X GET "$BASE_URL/health"' \
  "HEALTH"

# ============================================================================
# FINAL SUMMARY TABLE
# ============================================================================
echo "" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}===========================================================================${NC}" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}All tests completed!${NC}" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}===========================================================================${NC}" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"
echo "===========================================================================" | tee -a "$RESULTS_FILE"
echo "Test Execution Summary" | tee -a "$RESULTS_FILE"
echo "===========================================================================" | tee -a "$RESULTS_FILE"
printf "%-60s %-10s %-15s\n" "Test Name" "Results" "Time (s)" | tee -a "$RESULTS_FILE"
echo "---------------------------------------------------------------------------" | tee -a "$RESULTS_FILE"

# Calculate totals
total_time=0
total_results=0

for i in "${!test_names[@]}"; do
    # Truncate test name if too long
    test_name="${test_names[$i]}"
    if [ ${#test_name} -gt 60 ]; then
        test_name="${test_name:0:57}..."
    fi
    printf "%-60s %-10s %-15s\n" "$test_name" "${test_result_counts[$i]}" "${test_durations[$i]}" | tee -a "$RESULTS_FILE"
    total_time=$(echo "$total_time + ${test_durations[$i]}" | bc)
    total_results=$(echo "$total_results + ${test_result_counts[$i]}" | bc)
done

echo "---------------------------------------------------------------------------" | tee -a "$RESULTS_FILE"
printf "%-60s %-10s %-15s\n" "TOTAL" "$total_results" "$total_time" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

# Performance metrics
avg_time=$(echo "scale=3; $total_time / ${#test_names[@]}" | bc)
echo -e "${YELLOW}Performance Metrics:${NC}" | tee -a "$RESULTS_FILE"
echo "  Total Tests: ${#test_names[@]}" | tee -a "$RESULTS_FILE"
echo "  Total Results: $total_results places" | tee -a "$RESULTS_FILE"
echo "  Total Execution Time: ${total_time}s" | tee -a "$RESULTS_FILE"
echo "  Average Time per Test: ${avg_time}s" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

echo -e "${GREEN}===========================================================================${NC}" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}All ${#test_names[@]} tests completed successfully!${NC}" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}Results saved to: $RESULTS_FILE${NC}" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}===========================================================================${NC}" | tee -a "$RESULTS_FILE"
