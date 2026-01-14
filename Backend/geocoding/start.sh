#!/bin/bash

# Geocoding Microservice - Quick Start Script
#
# This script:
# 1. Creates/activates Python virtual environment
# 2. Installs dependencies
# 3. Runs setup validation tests
# 4. Provides instructions to start the service
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
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Install dependencies
echo ""
echo "Installing/updating dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r ../requirements.txt

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo ""
    echo "⚠️  Warning: .env file not found in Backend directory"
    echo ""
    echo "Please create Backend/.env with the following variables:"
    echo "  SUPABASE_URL=your_supabase_url"
    echo "  SUPABASE_KEY=your_supabase_key"
    echo "  LOCATIONIQ_API_KEY=your_locationiq_key"
    echo "  LOCATIONIQ_BASE_URL=https://us1.locationiq.com/v1"
    echo "  FUZZY_MATCH_THRESHOLD=0.85"
    echo ""
    exit 1
fi

# Run database setup tests
echo ""
echo "Running setup validation tests..."
echo "This will check database connectivity, SQL functions, and services."
echo ""
python tests/test_setup.py --all

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Setup Complete!"
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
    echo "2. Test with curl commands:"
    echo "   cd geocoding"
    echo "   chmod +x tests/test_curl_commands.sh"
    echo "   ./tests/test_curl_commands.sh"
    echo ""
    echo "3. View API Documentation:"
    echo "   http://localhost:8000/docs"
    echo ""
    echo "4. Run integration tests:"
    echo "   cd geocoding"
    echo "   python tests/test_api.py"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "✗ Setup Tests Failed"
    echo "=========================================="
    echo ""
    echo "Please fix the errors above before starting the service."
    echo ""
    echo "Common issues:"
    echo "  - Database SQL functions not created (run db_queries.sql in Supabase)"
    echo "  - Missing PostgreSQL extensions (pg_trgm, postgis)"
    echo "  - Incorrect .env credentials"
    echo ""
    exit 1
fi
