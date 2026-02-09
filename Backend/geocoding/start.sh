#!/bin/bash

# Geocoding Microservice - Quick Start Script
#
# This script:
# 1. Creates/activates Python virtual environment
# 2. Installs/updates dependencies
# 3. Validates .env configuration
# 4. Runs setup validation tests (4 phases)
# 5. Provides instructions to start the service
#
# Safe to run multiple times - it's idempotent:
#   - Skips venv creation if already exists
#   - Updates packages only if needed
#   - Re-runs validation to ensure everything still works
#
# Usage:
#   cd /home/ahmad_shahmeer/reach-geocoding/Backend/geocoding
#   chmod +x start.sh
#   ./start.sh

echo "=========================================="
echo "Geocoding Microservice - Quick Start"
echo "=========================================="

# Ensure we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

echo "Python version: $(python3 --version)"

# Check if virtual environment exists in Backend directory
VENV_PATH="../../venv"
if [ ! -d "$VENV_PATH" ]; then
    echo ""
    echo "Creating virtual environment in Backend/venv..."
    cd ../..
    python3 -m venv venv
    cd geocoding
else
    echo ""
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Install dependencies
echo ""
echo "Installing/updating dependencies..."
echo "(This may take a moment if packages need updating)"
pip install --upgrade pip --quiet
pip install -r ../requirements.txt --quiet

echo "✓ Dependencies ready"

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo ""
    echo "⚠️  Warning: .env file not found in Backend directory"
    echo ""
    echo "Please create Backend/.env with the following variables:"
    echo "  SUPABASE_URL=your_supabase_url"
    echo "  SUPABASE_KEY=your_supabase_key"
    echo "  LOCATION_IQ_KEY=your_locationiq_key"
    echo "  FUZZY_MATCH_THRESHOLD=0.85"
    echo ""
    echo "Optional Redis configuration:"
    echo "  REDIS_ENABLED=true"
    echo "  REDIS_HOST=localhost"
    echo "  REDIS_PORT=6379"
    echo ""
    exit 1
else
    echo ""
    echo "✓ .env file found"
fi

# Run database setup tests
echo ""
echo "=========================================="
echo "Running Setup Validation (4 phases)"
echo "=========================================="
echo "This validates:"
echo "  Phase 1: Configuration & Connectivity"
echo "  Phase 2: Database Layer (SQL functions, indexes)"
echo "  Phase 3: Service Layer (parsers, cache, geocoder)"
echo "  Phase 4: End-to-End Integration"
echo ""
python tests/test_setup.py --all

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Setup Complete! All Tests Passed"
    echo "=========================================="
    echo ""
    echo "📋 Next Steps:"
    echo ""
    echo "1. Start the service:"
    echo "   cd /home/ahmad_shahmeer/reach-geocoding/Backend"
    echo "   python -m geocoder"
    echo ""
    echo "   Or with uvicorn directly:"
    echo "   uvicorn geocoder:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo "2. View API Documentation:"
    echo "   http://localhost:8000/docs"
    echo ""
    echo "3. Test with curl commands (2 comprehensive test suites):"
    echo "   cd geocoding/tests"
    echo "   chmod +x test_curl_commands.sh test_curl_commands_2.sh"
    echo "   ./test_curl_commands.sh     # Original test suite"
    echo "   ./test_curl_commands_2.sh   # Alternative test suite"
    echo ""
    echo "4. Run Python integration tests:"
    echo "   cd geocoding/tests"
    echo "   python test_api.py"
    echo ""
    echo "📚 Documentation:"
    echo "   - geocoding/GEOCODING.md - Comprehensive user guide"
    echo "   - geocoding/ARCHITECTURE.md - System architecture"
    echo "   - geocoding/tests/README.md - Testing guide"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "✗ Setup Validation Failed"
    echo "=========================================="
    echo ""
    echo "Please fix the errors above before starting the service."
    echo ""
    echo "Common issues:"
    echo "  - Database SQL functions not created (run db_queries.sql in Supabase)"
    echo "  - Missing PostgreSQL extensions (pg_trgm, postgis)"
    echo "  - Incorrect .env credentials"
    echo "  - Redis not running (if REDIS_ENABLED=true)"
    echo ""
    echo "For detailed troubleshooting, see:"
    echo "  geocoding/GEOCODING.md#troubleshooting"
    echo ""
    exit 1
fi
