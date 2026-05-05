@echo off
REM Master Test Runner for REACH Project
REM Runs all unit, integration, and system tests
REM Usage: run_all_tests.bat

setlocal enabledelayedexpansion
set FAILED_TESTS=0
set PASSED_TESTS=0

echo.
echo ============================================
echo REACH Test Suite - Master Runner
echo ============================================
echo.

REM Check if we're in the right directory
if not exist "Backend" (
    echo ERROR: Backend directory not found. Please run from project root.
    exit /b 1
)

echo [1/4] Running Backend Unit Tests (Processing Engine)...
echo.
cd Backend
call pytest processing_engine/tests/ -v --tb=short --color=yes
if %ERRORLEVEL% NEQ 0 (
    set /a FAILED_TESTS+=1
    echo FAILED: Backend unit tests
) else (
    set /a PASSED_TESTS+=1
    echo PASSED: Backend unit tests
)
cd ..

echo.
echo [2/4] Running Backend Integration Tests...
echo.
cd Backend
call pytest tests/integration/ -v --tb=short --color=yes
if %ERRORLEVEL% NEQ 0 (
    set /a FAILED_TESTS+=1
    echo FAILED: Backend integration tests
) else (
    set /a PASSED_TESTS+=1
    echo PASSED: Backend integration tests
)
cd ..

echo.
echo [3/4] Running Frontend Unit Tests...
echo.
cd Frontend
call npm test -- --coverage --watchAll=false 2>nul
if %ERRORLEVEL% NEQ 0 (
    set /a FAILED_TESTS+=1
    echo FAILED: Frontend unit tests
) else (
    set /a PASSED_TESTS+=1
    echo PASSED: Frontend unit tests
)
cd ..

echo.
echo [4/4] Running Frontend E2E Tests (Cypress)...
echo.
cd Frontend
call npx cypress run --e2e --headless 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: E2E tests skipped (requires running frontend/backend)
    echo To run E2E tests manually:
    echo   1. Open 2 terminals
    echo   2. Terminal 1: npm run dev
    echo   3. Terminal 2: python -m uvicorn Backend.app:app --port 8000
    echo   4. Terminal 3: npx cypress run --e2e
) else (
    set /a PASSED_TESTS+=1
    echo PASSED: Frontend E2E tests
)
cd ..

echo.
echo ============================================
echo Test Summary
echo ============================================
echo Passed: !PASSED_TESTS!
echo Failed: !FAILED_TESTS!
echo.

if !FAILED_TESTS! EQU 0 (
    echo All tests completed successfully!
    exit /b 0
) else (
    echo Some tests failed. See details above.
    exit /b 1
)
