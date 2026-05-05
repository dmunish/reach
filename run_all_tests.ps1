# Master Test Runner for REACH Project (PowerShell)
# Runs all unit, integration, and system tests
# Usage: .\run_all_tests.ps1

param(
    [switch]$Unit,
    [switch]$Integration,
    [switch]$E2E,
    [switch]$Performance,
    [switch]$All,
    [switch]$Coverage
)

# If no flags specified, run all by default
if (-not $Unit -and -not $Integration -and -not $E2E -and -not $Performance) {
    $All = $true
}

$testResults = @{
    Passed = @()
    Failed = @()
}

function Test-Backend-Unit {
    Write-Host "`n[1/4] Running Backend Unit Tests (Processing Engine)..." -ForegroundColor Cyan
    Write-Host "=" * 60
    
    Push-Location Backend
    
    if ($Coverage) {
        pytest processing_engine/tests/ -v --cov=processing_engine --cov-report=html --tb=short
    } else {
        pytest processing_engine/tests/ -v --tb=short
    }
    
    if ($LASTEXITCODE -eq 0) {
        $testResults.Passed += "Backend Unit Tests"
        Write-Host "✓ PASSED: Backend unit tests" -ForegroundColor Green
    } else {
        $testResults.Failed += "Backend Unit Tests"
        Write-Host "✗ FAILED: Backend unit tests" -ForegroundColor Red
    }
    
    Pop-Location
}

function Test-Backend-Integration {
    Write-Host "`n[2/4] Running Backend Integration Tests..." -ForegroundColor Cyan
    Write-Host "=" * 60
    
    Push-Location Backend
    pytest tests/integration/ -v --tb=short
    
    if ($LASTEXITCODE -eq 0) {
        $testResults.Passed += "Backend Integration Tests"
        Write-Host "✓ PASSED: Backend integration tests" -ForegroundColor Green
    } else {
        $testResults.Failed += "Backend Integration Tests"
        Write-Host "✗ FAILED: Backend integration tests" -ForegroundColor Red
    }
    
    Pop-Location
}

function Test-Frontend-Unit {
    Write-Host "`n[3/4] Running Frontend Unit Tests..." -ForegroundColor Cyan
    Write-Host "=" * 60
    
    Push-Location Frontend
    
    if ($Coverage) {
        npm test -- --coverage --watchAll=false
    } else {
        npm test -- --watchAll=false
    }
    
    if ($LASTEXITCODE -eq 0) {
        $testResults.Passed += "Frontend Unit Tests"
        Write-Host "✓ PASSED: Frontend unit tests" -ForegroundColor Green
    } else {
        $testResults.Failed += "Frontend Unit Tests"
        Write-Host "✗ FAILED: Frontend unit tests" -ForegroundColor Red
    }
    
    Pop-Location
}

function Test-Frontend-E2E {
    Write-Host "`n[4/4] Running Frontend E2E Tests (Cypress)..." -ForegroundColor Cyan
    Write-Host "=" * 60
    
    Push-Location Frontend
    
    # Check if backend and frontend are running
    $backendRunning = Test-NetConnection localhost -Port 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded
    $frontendRunning = Test-NetConnection localhost -Port 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded
    
    if (-not $backendRunning -or -not $frontendRunning) {
        Write-Host "⚠ WARNING: E2E tests require running services" -ForegroundColor Yellow
        Write-Host "To run E2E tests manually:" -ForegroundColor Yellow
        Write-Host "  1. Open 2 terminals" -ForegroundColor Yellow
        Write-Host "  2. Terminal 1: npm run dev" -ForegroundColor Yellow
        Write-Host "  3. Terminal 2: cd Backend && python -m uvicorn app:app --port 8000" -ForegroundColor Yellow
        Write-Host "  4. Terminal 3: cd Frontend && npx cypress run --e2e" -ForegroundColor Yellow
    } else {
        npx cypress run --e2e --headless
        
        if ($LASTEXITCODE -eq 0) {
            $testResults.Passed += "Frontend E2E Tests"
            Write-Host "✓ PASSED: Frontend E2E tests" -ForegroundColor Green
        } else {
            $testResults.Failed += "Frontend E2E Tests"
            Write-Host "✗ FAILED: Frontend E2E tests" -ForegroundColor Red
        }
    }
    
    Pop-Location
}

function Test-Performance {
    Write-Host "`n[5/5] Running Performance Tests (k6)..." -ForegroundColor Cyan
    Write-Host "=" * 60
    
    $backendRunning = Test-NetConnection localhost -Port 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded
    $frontendRunning = Test-NetConnection localhost -Port 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded
    
    if (-not $backendRunning -or -not $frontendRunning) {
        Write-Host "⚠ WARNING: Performance tests require running services" -ForegroundColor Yellow
        Write-Host "To run performance tests manually:" -ForegroundColor Yellow
        Write-Host "  1. Terminal 1: npm run dev" -ForegroundColor Yellow
        Write-Host "  2. Terminal 2: cd Backend && python -m uvicorn app:app --port 8000" -ForegroundColor Yellow
        Write-Host "  3. Terminal 3: k6 run Tests/performance/load.js" -ForegroundColor Yellow
    } else {
        k6 run Tests/performance/load.js
        
        if ($LASTEXITCODE -eq 0) {
            $testResults.Passed += "Performance Tests"
            Write-Host "✓ PASSED: Performance tests" -ForegroundColor Green
        } else {
            $testResults.Failed += "Performance Tests"
            Write-Host "✗ FAILED: Performance tests" -ForegroundColor Red
        }
    }
}

# Main execution
Write-Host "`n" -NoNewline
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "REACH Test Suite - Master Runner" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

# Check if we're in the right directory
if (-not (Test-Path "Backend")) {
    Write-Host "ERROR: Backend directory not found. Please run from project root." -ForegroundColor Red
    exit 1
}

# Run selected tests
if ($All -or $Unit) {
    Test-Backend-Unit
}

if ($All -or $Integration) {
    Test-Backend-Integration
}

if ($All -or $Unit) {
    Test-Frontend-Unit
}

if ($All -or $E2E) {
    Test-Frontend-E2E
}

if ($Performance) {
    Test-Performance
}

# Print summary
Write-Host "`n" -NoNewline
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Test Summary" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

Write-Host "Passed: $($testResults.Passed.Count)" -ForegroundColor Green
foreach ($test in $testResults.Passed) {
    Write-Host "  ✓ $test" -ForegroundColor Green
}

Write-Host "Failed: $($testResults.Failed.Count)" -ForegroundColor Red
foreach ($test in $testResults.Failed) {
    Write-Host "  ✗ $test" -ForegroundColor Red
}

if ($Coverage) {
    Write-Host "`nCoverage reports generated:" -ForegroundColor Cyan
    Write-Host "  - Backend: Backend\htmlcov\index.html" -ForegroundColor Cyan
    Write-Host "  - Frontend: Frontend\coverage\lcov-report\index.html" -ForegroundColor Cyan
}

Write-Host "`n"

if ($testResults.Failed.Count -eq 0) {
    Write-Host "All tests completed successfully!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some tests failed. See details above." -ForegroundColor Red
    exit 1
}
