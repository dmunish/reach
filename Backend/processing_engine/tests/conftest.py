"""
Pytest fixtures for processing engine tests.
Provides mocks for LLM, document fetch, and external dependencies.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image


@pytest.fixture
def mock_llm_client():
    """Mock Gemini Flash API responses"""
    mock_response = {
        "alert_type": "FLOOD",
        "severity": "EXTREME",
        "location_mentions": ["Sindh", "Karachi"],
        "description": "Flash flooding in urban areas"
    }
    with patch('Backend.processing_engine.processor_utils.llm_client.AsyncLLMClient') as mock:
        mock_instance = MagicMock()
        mock_instance.call = MagicMock(return_value=json.dumps(mock_response))
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_document_fetch():
    """Mock HTTP fetch and PDF conversion"""
    with patch('Backend.processing_engine.processor_utils.doc_utils.fetch_file') as mock:
        mock.return_value = b'PDF_MOCK_CONTENT'
        yield mock


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for HTTP calls"""
    with patch('requests.get') as mock:
        mock.return_value.status_code = 200
        mock.return_value.content = b'PDF_MOCK_BYTES'
        mock.return_value.headers = {'content-type': 'application/pdf'}
        yield mock


@pytest.fixture
def sample_pil_image():
    """Create a sample PIL image for testing"""
    img = Image.new('RGB', (100, 100), color='red')
    return img


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF bytes for testing"""
    # Minimal PDF structure
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Page) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000194 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
287
%%EOF"""


@pytest.fixture
def mock_pypdf():
    """Mock PyPDF2 for PDF operations"""
    with patch('Backend.processing_engine.processor_utils.doc_utils.PyPDF2') as mock:
        mock.PdfReader.return_value.pages = [MagicMock()]
        yield mock


@pytest.fixture
def mock_validator():
    """Mock Pydantic validator"""
    with patch('Backend.processing_engine.models.schemas.BaseModel.model_validate') as mock:
        mock.return_value = MagicMock(
            alert_type="FLOOD",
            severity="EXTREME",
            location_mentions=["Sindh"],
            description="Test alert"
        )
        yield mock


@pytest.fixture
def mock_json_schema():
    """Mock JSON schema validation"""
    with patch('json.loads') as mock:
        mock.return_value = {
            "alert_type": "FLOOD",
            "severity": "EXTREME",
            "location_mentions": ["Sindh"],
            "description": "Test alert"
        }
        yield mock


@pytest.fixture
def pipeline_processor_config():
    """Configuration for pipeline processor"""
    return {
        "model": "gemini-1.5-flash",
        "temperature": 0.7,
        "max_tokens": 2048
    }
