#!/bin/bash

# Quick start script for the geocoding microservice

echo "=========================================="
echo "Geocoding Microservice - Quick Start"
echo "=========================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r ../requirements.txt

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "Error: .env file not found in Backend directory"
    echo "Please create .env with required variables"
    exit 1
fi

# Run database setup tests
echo ""
echo "Running database setup tests..."
python test_setup.py --all

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Setup complete!"
    echo "=========================================="
    echo ""
    echo "To start the service:"
    echo "  python -m geocoding.main"
    echo ""
    echo "Or with uvicorn directly:"
    echo "  uvicorn geocoding.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo "API Documentation will be available at:"
    echo "  http://localhost:8000/docs"
else
    echo ""
    echo "✗ Setup tests failed. Please fix errors before starting service."
    exit 1
fi
