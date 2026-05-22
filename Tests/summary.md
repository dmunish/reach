(venv) PS D:\Danish\Work\Projects\REACH> .\run_all_tests.bat

============================================
REACH Test Suite - Master Runner
============================================

[1/4] Running Backend Unit Tests (Processing Engine)...

======================================================== test session starts =========================================================
platform win32 -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- D:\Danish\Work\Projects\REACH\venv\Scripts\python.exe
cachedir: .pytest_cache
hypothesis profile 'default'
rootdir: D:\Danish\Work\Projects\REACH
configfile: pytest.ini
plugins: anyio-4.12.1, hypothesis-6.151.9, langsmith-0.7.1, asyncio-1.3.0, cov-7.1.0, mock-3.15.1, schemathesis-4.10.2
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 34 items

processing_engine\tests\test_doc_utils.py::TestDocUtilsImageConversion::test_to_base64_from_pil_image PASSED                    [  2%]
processing_engine\tests\test_doc_utils.py::TestDocUtilsPDFProcessing::test_pdf_to_images_validates_bytes_input PASSED           [  5%] 
processing_engine\tests\test_doc_utils.py::TestDocUtilsPDFProcessing::test_pdf_to_images_error_handling PASSED                  [  8%] 
processing_engine\tests\test_doc_utils.py::TestDocUtilsHTTPFetch::test_async_fetch_behavior PASSED                              [ 11%] 
processing_engine\tests\test_doc_utils.py::TestDocUtilsHTTPFetch::test_url_parsing PASSED                                       [ 14%] 
processing_engine\tests\test_doc_utils.py::TestDocUtilsEdgeCases::test_empty_url_list_handling PASSED                           [ 17%]
processing_engine\tests\test_doc_utils.py::TestDocUtilsEdgeCases::test_base64_encoding_roundtrip PASSED                         [ 20%] 
processing_engine\tests\test_doc_utils.py::TestDocUtilsEdgeCases::test_image_format_detection PASSED                            [ 23%]
processing_engine\tests\test_llm_client.py::TestLLMClientConfiguration::test_model_configuration_loading PASSED                 [ 26%]
processing_engine\tests\test_llm_client.py::TestLLMClientConfiguration::test_temperature_parameter_valid_range PASSED           [ 29%]
processing_engine\tests\test_llm_client.py::TestLLMClientConfiguration::test_runtime_kwargs_merge_pattern PASSED                [ 32%]
processing_engine\tests\test_llm_client.py::TestLLMClientConfiguration::test_api_key_from_environment PASSED                    [ 35%]
processing_engine\tests\test_llm_client.py::TestLLMClientResponses::test_valid_json_response_parsing PASSED                     [ 38%] 
processing_engine\tests\test_llm_client.py::TestLLMClientResponses::test_invalid_json_response_error PASSED                     [ 41%] 
processing_engine\tests\test_llm_client.py::TestLLMClientResponses::test_response_field_validation PASSED                       [ 44%]
processing_engine\tests\test_llm_client.py::TestLLMClientErrorHandling::test_timeout_error_detection PASSED                     [ 47%]
processing_engine\tests\test_llm_client.py::TestLLMClientErrorHandling::test_rate_limit_error_detection PASSED                  [ 50%]
processing_engine\tests\test_llm_client.py::TestLLMClientErrorHandling::test_api_key_error_detection PASSED                     [ 52%]
processing_engine\tests\test_llm_client.py::TestLLMClientAsyncPatterns::test_async_call_pattern PASSED                          [ 55%]
processing_engine\tests\test_llm_client.py::TestLLMClientAsyncPatterns::test_multiple_concurrent_calls FAILED                   [ 58%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorValidation::test_valid_json_structure PASSED           [ 61%] 
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorValidation::test_invalid_enum_category_rejected PASSED [ 64%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorValidation::test_required_fields_validation PASSED     [ 67%] 
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorValidation::test_severity_enum_validation PASSED       [ 70%] 
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorValidation::test_alert_type_enum_validation PASSED     [ 73%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorDateHandling::test_iso_date_parsing PASSED             [ 76%] 
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorDateHandling::test_invalid_date_format_rejected PASSED [ 79%] 
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorLocationExtraction::test_single_location_extracted PASSED [ 82%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorLocationExtraction::test_multiple_locations_extracted PASSED [ 85%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorLocationExtraction::test_empty_location_mentions PASSED [ 88%]processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorAlertAreas::test_alert_area_from_locations PASSED      [ 91%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorAlertAreas::test_alert_area_polygon_association PASSED [ 94%] 
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorErrorRecovery::test_partial_validation_failure PASSED  [ 97%]
processing_engine\tests\test_pipeline_processor.py::TestPipelineProcessorErrorRecovery::test_json_encoding_decoding PASSED      [100%] 

============================================================== FAILURES ============================================================== 
_____________________________________ TestLLMClientAsyncPatterns.test_multiple_concurrent_calls ______________________________________ 
processing_engine\tests\test_llm_client.py:169: in test_multiple_concurrent_calls
    mock_call()
E   TypeError: TestLLMClientAsyncPatterns.test_multiple_concurrent_calls.<locals>.mock_call() missing 1 required positional argument: 'call_id'

During handling of the above exception, another exception occurred:
processing_engine\tests\test_llm_client.py:168: in test_multiple_concurrent_calls
    with pytest.raises(Exception, match="Rate limit"):
E   AssertionError: Regex pattern did not match.
E     Expected regex: 'Rate limit'
E     Actual message: "TestLLMClientAsyncPatterns.test_multiple_concurrent_calls.<locals>.mock_call() missing 1 required positional argument: 'call_id'"
====================================================== short test summary info ======================================================= 
FAILED processing_engine\tests\test_llm_client.py::TestLLMClientAsyncPatterns::test_multiple_concurrent_calls - AssertionError: Regex pattern did not match.
  Expected regex: 'Rate limit'
  Actual message: "TestLLMClientAsyncPatterns.test_multiple_concurrent_calls.<locals>.mock_call() missing 1 required positional argument: 'call_id'"
==================================================== 1 failed, 33 passed in 2.00s ==================================================== 
FAILED: Backend unit tests

[2/4] Running Backend Integration Tests...

======================================================== test session starts =========================================================
platform win32 -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- D:\Danish\Work\Projects\REACH\venv\Scripts\python.exe
cachedir: .pytest_cache
hypothesis profile 'default'
rootdir: D:\Danish\Work\Projects\REACH
configfile: pytest.ini
plugins: anyio-4.12.1, hypothesis-6.151.9, langsmith-0.7.1, asyncio-1.3.0, cov-7.1.0, mock-3.15.1, schemathesis-4.10.2
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 9 items

tests\integration\test_validation_error_handling.py::TestAPIValidation::test_validation_empty_locations_rejected PASSED         [ 11%]
tests\integration\test_validation_error_handling.py::TestAPIValidation::test_validation_malformed_options_rejected PASSED       [ 22%] 
tests\integration\test_validation_error_handling.py::TestAPIErrorHandling::test_internal_service_exception_mapped_to_500 PASSED [ 33%] 
tests\integration\test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode PASSED             [ 44%]
tests\integration\test_validation_error_handling.py::TestConcurrency::test_concurrent_requests_stability PASSED                 [ 55%]
tests\integration\test_validation_error_handling.py::TestAPIHealthCheck::test_health_endpoint_availability PASSED               [ 66%]
tests\integration\test_validation_error_handling.py::TestAPIErrorMessages::test_validation_error_message_clarity PASSED         [ 77%] 
tests\integration\test_validation_error_handling.py::TestAPIErrorMessages::test_not_found_error_message PASSED                  [ 88%]
tests\integration\test_validation_error_handling.py::TestDataIntegrity::test_response_schema_validation PASSED                  [100%] 

========================================================== warnings summary ========================================================== 
Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\expressions\parser.py:72: DeprecationWarning: 'enablePackrat' deprecated - use 'enable_packrat'
    ParserElement.enablePackrat()

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\expressions\parser.py:85: DeprecationWarning: 'escChar' argument is deprecated, use 'esc_char'
    quoted_identifier = QuotedString('"', escChar="\\", unquoteResults=True)

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\expressions\parser.py:85: DeprecationWarning: 'unquoteResults' argument is deprecated, use 'unquote_results'
    quoted_identifier = QuotedString('"', escChar="\\", unquoteResults=True)

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:365: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:494: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:498: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:502: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:506: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:538: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:542: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:546: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

Backend/tests/integration/test_validation_error_handling.py::TestCaching::test_cache_integration_on_repeated_geocode
  D:\Danish\Work\Projects\REACH\venv\Lib\site-packages\pyiceberg\table\metadata.py:550: PydanticDeprecatedSince212: Using `@model_validator` with mode='after' on a classmethod is deprecated. Instead, use an instance method. See the documentation at https://docs.pydantic.dev/2.12/concepts/validators/#model-after-validator. Deprecated in Pydantic V2.12 to be removed in V3.0.
    @model_validator(mode="after")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================================================== 9 passed, 12 warnings in 5.62s =================================================== 
PASSED: Backend integration tests

[3/4] Running Frontend Unit Tests...


> reach-frontend@0.0.0 test
> jest --coverage --watchAll=false

FAILED: Frontend unit tests

[4/4] Running Frontend E2E Tests (Cypress)...


Warning: The allowCypressEnv configuration option is enabled. This allows any browser code to read values from Cypress.env(). This is insecure and will be removed in a future major version.

1. Replace Cypress.env() calls with cy.env() (for sensitive values) or Cypress.expose() (for public configuration)
2. Set allowCypressEnv: false in your Cypress configuration to disable Cypress.env()

Learn more: https://on.cypress.io/cypress-env-migration


====================================================================================================

  (Run Starting)

  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ Cypress:        15.14.2                                                                        │
  │ Browser:        Electron 138 (headless)                                                        │
  │ Node Version:   v22.12.0 (C:\Program Files\nodejs\node.exe)                                    │
  │ Specs:          1 found (dashboard.cy.ts)                                                      │
  │ Searched:       cypress/e2e/**/*.cy.ts                                                         │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘


────────────────────────────────────────────────────────────────────────────────────────────────────

  Running:  dashboard.cy.ts                                                                 (1 of 1)


  REACH Dashboard E2E Tests
    ST-001: Dashboard Loading
      1) loads the dashboard and renders the map with alerts
    ST-002: Filter by Category
      √ filters alerts by category after expanding the hidden filters (12998ms)
    ST-003: Filter by Severity
      √ filters alerts by severity with the current single-select control (12090ms)
    ST-004: Search by Location
      √ searches alerts from the merged filter/search panel (12910ms)
      √ restores the full list when the search is cleared (10616ms)
    ST-005: Date Range Filter
      2) filters alerts by date after expanding the hidden advanced controls
      3) shows the empty-state message when the date range matches nothing
    ST-006: View Alert Detail Card
      √ opens and closes the detail card for an alert (12993ms)
    Error Handling
      4) shows an error message when alert loading fails
      5) shows the empty-state message when the RPC returns no alerts


  5 passing (3m)
  5 failing

  1) REACH Dashboard E2E Tests
       ST-001: Dashboard Loading
         loads the dashboard and renders the map with alerts:
     AssertionError: Timed out retrying after 10000ms: expected '<div.w-full.h-full.mapboxgl-map>' to be 'visible'

This element `<div.w-full.h-full.mapboxgl-map>` is not visible because it has CSS property: `position: fixed` and it's being covered by another element:

`<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" 
stroke-linecap="round" stroke-linejoin="round">...</svg>`
      at Context.eval (webpack://reach-frontend/./cypress/e2e/dashboard.cy.ts:246:46)

  2) REACH Dashboard E2E Tests
       ST-005: Date Range Filter
         filters alerts by date after expanding the hidden advanced controls:
     CypressError: Timed out retrying after 10000ms: `cy.wait()` timed out waiting `10000ms` for the 2nd request to the route: `getAlerts`. No request ever occurred.

https://on.cypress.io/wait
      at cypressErr (http://localhost:5173/__cypress/runner/cypress_runner.js:78521:18)
      at Object.errByPath (http://localhost:5173/__cypress/runner/cypress_runner.js:78579:10)
      at checkForXhr (http://localhost:5173/__cypress/runner/cypress_runner.js:139085:84)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:139110:28)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise.attempt.Promise.try (http://localhost:5173/__cypress/runner/cypress_runner.js:4285:29)
      at whenStable (http://localhost:5173/__cypress/runner/cypress_runner.js:152237:70)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:152152:14)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise._settlePromiseFromHandler (http://localhost:5173/__cypress/runner/cypress_runner.js:1489:31)
      at Promise._settlePromise (http://localhost:5173/__cypress/runner/cypress_runner.js:1546:18)
      at Promise._settlePromise0 (http://localhost:5173/__cypress/runner/cypress_runner.js:1591:10)
      at Promise._settlePromises (http://localhost:5173/__cypress/runner/cypress_runner.js:1671:18)
      at Promise._fulfill (http://localhost:5173/__cypress/runner/cypress_runner.js:1615:18)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:5420:46)

  3) REACH Dashboard E2E Tests
       ST-005: Date Range Filter
         shows the empty-state message when the date range matches nothing:
     CypressError: Timed out retrying after 10000ms: `cy.wait()` timed out waiting `10000ms` for the 2nd request to the route: `getAlerts`. No request ever occurred.

https://on.cypress.io/wait
      at cypressErr (http://localhost:5173/__cypress/runner/cypress_runner.js:78521:18)
      at Object.errByPath (http://localhost:5173/__cypress/runner/cypress_runner.js:78579:10)
      at checkForXhr (http://localhost:5173/__cypress/runner/cypress_runner.js:139085:84)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:139110:28)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise.attempt.Promise.try (http://localhost:5173/__cypress/runner/cypress_runner.js:4285:29)
      at whenStable (http://localhost:5173/__cypress/runner/cypress_runner.js:152237:70)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:152152:14)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise._settlePromiseFromHandler (http://localhost:5173/__cypress/runner/cypress_runner.js:1489:31)
      at Promise._settlePromise (http://localhost:5173/__cypress/runner/cypress_runner.js:1546:18)
      at Promise._settlePromise0 (http://localhost:5173/__cypress/runner/cypress_runner.js:1591:10)
      at Promise._settlePromises (http://localhost:5173/__cypress/runner/cypress_runner.js:1671:18)
      at Promise._fulfill (http://localhost:5173/__cypress/runner/cypress_runner.js:1615:18)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:5420:46)

  4) REACH Dashboard E2E Tests
       Error Handling
         shows an error message when alert loading fails:
     CypressError: Timed out retrying after 10050ms: `cy.click()` failed because this element:

          `<button data-testid="user-guide-close" class="p-2 hover:bg-bangladesh-green rounded-full transition-colors group">...</button>`

          has CSS `pointer-events: none`, inherited from this element:

`<div id="user-guide-window" data-testid="user-guide" class="fixed
          inset-4
          sm:left-22 sm:right-4
          sm:top-4 sm:bottom-4
          frosted-glass
          transform transition-all duration-300 ease-in-out z-50
          overflow-hidden
          flex flex-col
          translate-y-10 opacity-0 scale-95 pointer-events-none
        ">...</div>`

          `pointer-events: none` prevents user mouse interaction.

          Fix this problem, or use {force: true} to disable error checking.

https://on.cypress.io/element-cannot-be-interacted-with
      at ensureElDoesNotHaveCSS (http://localhost:5173/__cypress/runner/cypress_runner.js:115231:66)
      at ensureDescendents (http://localhost:5173/__cypress/runner/cypress_runner.js:115339:5)
      at ensureDescendentsAndScroll (http://localhost:5173/__cypress/runner/cypress_runner.js:115347:14)
      at ensureElIsNotCovered (http://localhost:5173/__cypress/runner/cypress_runner.js:115478:5)
      at runAllChecks (http://localhost:5173/__cypress/runner/cypress_runner.js:115677:52)
      at retryActionability (http://localhost:5173/__cypress/runner/cypress_runner.js:115714:16)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise.attempt.Promise.try (http://localhost:5173/__cypress/runner/cypress_runner.js:4285:29)
      at whenStable (http://localhost:5173/__cypress/runner/cypress_runner.js:152237:70)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:152152:14)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise._settlePromiseFromHandler (http://localhost:5173/__cypress/runner/cypress_runner.js:1489:31)
      at Promise._settlePromise (http://localhost:5173/__cypress/runner/cypress_runner.js:1546:18)
      at Promise._settlePromise0 (http://localhost:5173/__cypress/runner/cypress_runner.js:1591:10)
      at Promise._settlePromises (http://localhost:5173/__cypress/runner/cypress_runner.js:1671:18)
      at Promise._fulfill (http://localhost:5173/__cypress/runner/cypress_runner.js:1615:18)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:5420:46)

  5) REACH Dashboard E2E Tests
       Error Handling
         shows the empty-state message when the RPC returns no alerts:
     CypressError: Timed out retrying after 10050ms: `cy.click()` failed because this element:

          `<button data-testid="user-guide-close" class="p-2 hover:bg-bangladesh-green rounded-full transition-colors group">...</button>`

          has CSS `pointer-events: none`, inherited from this element:

`<div id="user-guide-window" data-testid="user-guide" class="fixed
          inset-4
          sm:left-22 sm:right-4
          sm:top-4 sm:bottom-4
          frosted-glass
          transform transition-all duration-300 ease-in-out z-50
          overflow-hidden
          flex flex-col
          translate-y-10 opacity-0 scale-95 pointer-events-none
        ">...</div>`

          `pointer-events: none` prevents user mouse interaction.

          Fix this problem, or use {force: true} to disable error checking.

https://on.cypress.io/element-cannot-be-interacted-with
      at ensureElDoesNotHaveCSS (http://localhost:5173/__cypress/runner/cypress_runner.js:115231:66)
      at ensureDescendents (http://localhost:5173/__cypress/runner/cypress_runner.js:115339:5)
      at ensureDescendentsAndScroll (http://localhost:5173/__cypress/runner/cypress_runner.js:115347:14)
      at ensureElIsNotCovered (http://localhost:5173/__cypress/runner/cypress_runner.js:115478:5)
      at runAllChecks (http://localhost:5173/__cypress/runner/cypress_runner.js:115677:52)
      at retryActionability (http://localhost:5173/__cypress/runner/cypress_runner.js:115714:16)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise.attempt.Promise.try (http://localhost:5173/__cypress/runner/cypress_runner.js:4285:29)
      at whenStable (http://localhost:5173/__cypress/runner/cypress_runner.js:152237:70)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:152152:14)
      at tryCatcher (http://localhost:5173/__cypress/runner/cypress_runner.js:1777:23)
      at Promise._settlePromiseFromHandler (http://localhost:5173/__cypress/runner/cypress_runner.js:1489:31)
      at Promise._settlePromise (http://localhost:5173/__cypress/runner/cypress_runner.js:1546:18)
      at Promise._settlePromise0 (http://localhost:5173/__cypress/runner/cypress_runner.js:1591:10)
      at Promise._settlePromises (http://localhost:5173/__cypress/runner/cypress_runner.js:1671:18)
      at Promise._fulfill (http://localhost:5173/__cypress/runner/cypress_runner.js:1615:18)
      at <unknown> (http://localhost:5173/__cypress/runner/cypress_runner.js:5420:46)




  (Results)

  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ Tests:        10                                                                               │
  │ Passing:      5                                                                                │
  │ Failing:      5                                                                                │
  │ Pending:      0                                                                                │
  │ Skipped:      0                                                                                │
  │ Screenshots:  5                                                                                │
  │ Video:        false                                                                            │
  │ Duration:     3 minutes, 0 seconds                                                             │
  │ Spec Ran:     dashboard.cy.ts                                                                  │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘


  (Screenshots)

  -  D:\Danish\Work\Projects\REACH\Frontend\cypress\screenshots\dashboard.cy.ts\REACH     (1280x720)
      Dashboard E2E Tests -- ST-001 Dashboard Loading -- loads the dashboard and rend
     ers the map with alerts (failed).png
  -  D:\Danish\Work\Projects\REACH\Frontend\cypress\screenshots\dashboard.cy.ts\REACH     (1280x720)
      Dashboard E2E Tests -- ST-005 Date Range Filter -- filters alerts by date after
      expanding the hidden advanced controls (failed).png
  -  D:\Danish\Work\Projects\REACH\Frontend\cypress\screenshots\dashboard.cy.ts\REACH     (1280x720)
      Dashboard E2E Tests -- ST-005 Date Range Filter -- shows the empty-state messag
     e when the date range matches nothing (failed).png
  -  D:\Danish\Work\Projects\REACH\Frontend\cypress\screenshots\dashboard.cy.ts\REACH     (1280x720)
      Dashboard E2E Tests -- Error Handling -- shows an error message when alert load
     ing fails (failed).png
  -  D:\Danish\Work\Projects\REACH\Frontend\cypress\screenshots\dashboard.cy.ts\REACH     (1280x720)
      Dashboard E2E Tests -- Error Handling -- shows the empty-state message when the
      RPC returns no alerts (failed).png


====================================================================================================

  (Run Finished)


       Spec                                              Tests  Passing  Failing  Pending  Skipped
  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ ×  dashboard.cy.ts                          03:00       10        5        5        -        - │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘
    ×  1 of 1 failed (100%)                     03:00       10        5        5        -        -

WARNING: E2E tests skipped (requires running frontend/backend
To run E2E tests manually:
  1. Open 2 terminals
  2. Terminal 1: npm run dev
  3. Terminal 2: python -m uvicorn Backend.app:app --port 8000
  4. Terminal 3: npx cypress run --e2e
PASSED: Frontend E2E tests

============================================
Test Summary
============================================
Passed: 2
Failed: 2

Some tests failed. See details above.